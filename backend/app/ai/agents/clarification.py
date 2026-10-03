import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.services.appliance_resolution import (
    MULTIPLE_MATCHES,
    NO_MATCH,
    SINGLE_MATCH,
    resolve_appliance_reference,
)
from app.services.clarification_workflow import (
    ClarificationWorkflowError,
    complete_pending_clarification,
    persist_clarification,
)
from app.services.datetime_resolver import (
    resolve_relative_date,
    resolve_relative_datetime,
)


_REPAIR_WORDS = (
    "repair",
    "repaired",
    "repairing",
    "service",
    "serviced",
    "servicing",
    "fix",
    "fixed",
    "fixing",
    "technician",
)


# Appliance nouns that can safely establish that a maintenance issue refers
# to an appliance even when the specialist leaves appliance_id empty.
# Existing database matching still decides which concrete appliance row is
# plausible; this list only extracts the human-readable reference.
_ISSUE_APPLIANCE_TERMS = (
    "air conditioner",
    "air conditioning",
    "washing machine",
    "water heater",
    "microwave oven",
    "dishwasher",
    "refrigerator",
    "fridge",
    "geyser",
    "washer",
    "microwave",
    "television",
    "tv",
    "ac",
    "fan",
    "oven",
    "stove",
    "dryer",
    "freezer",
    "purifier",
    "ro",
    "vacuum",
    "chimney",
)

_NEW_APPLIANCE_RESPONSES = {
    "new",
    "new one",
    "add new",
    "add a new one",
    "add a new appliance",
    "another",
    "another one",
    "different one",
    "none",
    "none of these",
    "none of them",
}

_CONFIRM_EXISTING_RESPONSES = {
    "yes",
    "y",
    "yeah",
    "yep",
    "correct",
    "that's it",
    "thats it",
    "that one",
    "use it",
    "use that",
    "existing",
    "existing one",
}

_APPLIANCE_REFERENCE_STOPWORDS = {
    "a",
    "an",
    "the",
    "my",
    "our",
    "please",
    "task",
    "schedule",
    "scheduled",
    "create",
    "add",
    "log",
    "record",
    "for",
    "to",
    "on",
    "at",
    "by",
    "today",
    "tomorrow",
    "yesterday",
    "this",
    "next",
    "morning",
    "afternoon",
    "evening",
    "night",
}


def _normalize_choice_text(value: Any) -> str:
    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            str(value or "").casefold(),
        ).split()
    )


def _looks_like_uuid(value: Any) -> bool:
    raw = str(value or "").strip()
    return bool(
        re.fullmatch(
            r"[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}",
            raw,
        )
    )


def _has_explicit_time(value: Any) -> bool:
    raw = str(value or "").strip().casefold()

    if not raw or raw == "none":
        return False

    if re.search(
        r"\b\d{1,2}:\d{2}\b",
        raw,
    ):
        return True

    if re.search(
        r"\bt\d{2}:\d{2}",
        raw,
    ):
        return True

    return any(
        token in raw
        for token in (
            "am",
            "pm",
            "clock",
            "morning",
            "evening",
            "noon",
        )
    )


def _calendar_duration_minutes(value: Any) -> Optional[int]:
    """Return an explicit calendar duration in minutes.

    Duration is calendar-specific rather than date parsing, so it stays here
    while all date/time interpretation remains in datetime_resolver.py.
    """

    raw = " ".join(
        str(value or "").strip().casefold().split()
    )

    if not raw:
        return None

    if re.search(
        r"\bfor\s+(?:an|a|one)\s+hour\b",
        raw,
    ):
        return 60

    if re.search(
        r"\bfor\s+half\s+(?:an?\s+)?hour\b",
        raw,
    ):
        return 30

    hour_match = re.search(
        r"\bfor\s+(\d+(?:\.\d+)?)\s+"
        r"(?:hour|hours|hr|hrs)\b",
        raw,
    )

    if hour_match:
        minutes = int(
            float(hour_match.group(1)) * 60
        )
        return minutes if minutes > 0 else None

    minute_match = re.search(
        r"\bfor\s+(\d+)\s+"
        r"(?:minute|minutes|min|mins)\b",
        raw,
    )

    if minute_match:
        minutes = int(
            minute_match.group(1)
        )
        return minutes if minutes > 0 else None

    return None


def _repair_related_task(
    args: Dict[str, Any],
    current_action: Dict[str, Any],
) -> bool:
    context = " ".join(
        [
            str(args.get("title") or ""),
            str(args.get("description") or ""),
            str(current_action.get("intent") or ""),
            str(current_action.get("description") or ""),
        ]
    ).casefold()

    return any(
        re.search(
            r"\b{}\b".format(
                re.escape(word)
            ),
            context,
        )
        for word in _REPAIR_WORDS
    )


def _clean_appliance_reference(value: Any) -> str:
    """Normalize a value that is already expected to be an appliance label."""

    normalized = _normalize_choice_text(value)

    if not normalized:
        return ""

    repair_words = set(
        _REPAIR_WORDS
    )

    kept = [
        token
        for token in normalized.split()
        if (
            token not in repair_words
            and token
            not in _APPLIANCE_REFERENCE_STOPWORDS
            and token not in {
                "s",
                "was",
                "were",
                "is",
                "are",
                "be",
                "been",
                "being",
            }
            and not re.fullmatch(
                r"\d{1,2}",
                token,
            )
            and not re.fullmatch(
                r"\d{4}",
                token,
            )
        )
    ]

    return " ".join(kept)


_APPLIANCE_CLAUSE_BOUNDARIES = {
    "at",
    "by",
    "cost",
    "costing",
    "dated",
    "from",
    "on",
    "today",
    "tomorrow",
    "yesterday",
}

_APPLIANCE_CURRENCY_WORDS = {
    "inr",
    "rs",
    "rupee",
    "rupees",
    "usd",
    "dollar",
    "dollars",
}

_APPLIANCE_AUXILIARY_WORDS = {
    "be",
    "been",
    "being",
    "get",
    "gets",
    "got",
    "has",
    "have",
    "had",
    "is",
    "are",
    "was",
    "were",
}

_APPLIANCE_COMMAND_WORDS = {
    "add",
    "create",
    "log",
    "record",
    "schedule",
    "task",
}


def _trim_appliance_phrase_tokens(
    tokens: List[str],
) -> List[str]:
    """Remove grammar/action noise without stripping appliance descriptors."""

    cleaned = list(tokens)

    while cleaned and (
        cleaned[0]
        in _APPLIANCE_REFERENCE_STOPWORDS
        or cleaned[0]
        in _APPLIANCE_COMMAND_WORDS
        or cleaned[0] == "s"
    ):
        cleaned.pop(0)

    while cleaned and (
        cleaned[-1]
        in _APPLIANCE_REFERENCE_STOPWORDS
        or cleaned[-1]
        in _APPLIANCE_AUXILIARY_WORDS
        or cleaned[-1] == "s"
    ):
        cleaned.pop()

    return cleaned


def _extract_appliance_reference_from_text(
    value: Any,
) -> str:
    """Extract the appliance phrase nearest a repair/service/fix expression.

    This deliberately ignores later provider, price and date clauses instead
    of flattening the complete sentence into one bag of remaining words.
    """

    normalized = _normalize_choice_text(
        value
    )

    if not normalized:
        return ""

    tokens = normalized.split()
    repair_words = set(
        _REPAIR_WORDS
    )

    for index, token in enumerate(
        tokens
    ):
        if token not in repair_words:
            continue

        # Prefer a subject immediately before the repair word:
        # "Samsung AC was repaired ..." / "Log fridge repair ..."
        left = list(
            tokens[:index]
        )

        while left and (
            left[-1]
            in _APPLIANCE_AUXILIARY_WORDS
        ):
            left.pop()

        left = _trim_appliance_phrase_tokens(
            left
        )

        # Remove temporal/action noise that can remain before the subject,
        # e.g. "log today s fridge repair".
        left = [
            item
            for item in left
            if (
                item
                not in _APPLIANCE_COMMAND_WORDS
                and item
                not in {
                    "today",
                    "tomorrow",
                    "yesterday",
                    "s",
                }
            )
        ]

        if left:
            candidate = _clean_appliance_reference(
                " ".join(left)
            )

            if candidate:
                return candidate

        # Otherwise support command-first wording:
        # "repair geyser" / "service the bedroom AC".
        right = list(
            tokens[index + 1:]
        )

        while right and right[0] in {
            "for",
            "of",
            "the",
            "my",
            "our",
        }:
            right.pop(0)

        phrase = []

        for item in right:
            if (
                item
                in _APPLIANCE_CLAUSE_BOUNDARIES
                or item
                in _APPLIANCE_CURRENCY_WORDS
                or re.fullmatch(
                    r"\d+(?:\.\d+)?",
                    item,
                )
            ):
                break

            phrase.append(
                item
            )

        phrase = _trim_appliance_phrase_tokens(
            phrase
        )

        if phrase:
            candidate = _clean_appliance_reference(
                " ".join(phrase)
            )

            if candidate:
                return candidate

    return ""


def _extract_issue_appliance_reference_from_text(
    value: Any,
) -> str:
    """Return an explicit appliance noun from issue text, if present.

    This deliberately does not infer generic household fixtures such as walls,
    doors or plumbing as appliances. If no appliance noun is present, a
    report_issue action remains valid without appliance_id.
    """

    normalized = _normalize_choice_text(value)

    if not normalized:
        return ""

    for term in sorted(
        _ISSUE_APPLIANCE_TERMS,
        key=lambda item: (-len(item), item),
    ):
        pattern = (
            r"(?<!\w)"
            + r"\s+".join(
                re.escape(part)
                for part in term.split()
            )
            + r"(?!\w)"
        )

        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            return term

    return ""


def _appliance_reference_for_call(
    tool_name: str,
    args: Dict[str, Any],
    current_action: Dict[str, Any],
    message: str,
) -> str:
    raw_appliance = str(
        args.get("appliance_id")
        or ""
    ).strip()

    # A human-readable value supplied in appliance_id is treated only as a
    # reference to resolve.  A UUID-looking value is not trusted as confirmed
    # identity merely because it appeared in a model-produced tool call.
    if (
        raw_appliance
        and raw_appliance != "None"
        and not _looks_like_uuid(
            raw_appliance
        )
    ):
        cleaned = _clean_appliance_reference(
            raw_appliance
        )
        if cleaned:
            return cleaned

    # Issue wording usually describes a symptom rather than using
    # repair/service/fix verbs. Extract only an explicit appliance noun here.
    if tool_name == "report_issue":
        issue_sources = [
            args.get("description"),
            message,
            current_action.get(
                "description"
            ),
        ]

        for source in issue_sources:
            reference = (
                _extract_issue_appliance_reference_from_text(
                    source
                )
            )

            if reference:
                return reference

        return ""

    # Inspect independent sources in priority order. Do not concatenate them:
    # the same user request is often repeated in the action description.
    if tool_name == "create_task":
        sources = [
            args.get("title"),
            args.get("description"),
            current_action.get(
                "description"
            ),
            message,
        ]
    else:
        sources = [
            message,
            current_action.get(
                "description"
            ),
            args.get("notes"),
        ]

    for source in sources:
        reference = (
            _extract_appliance_reference_from_text(
                source
            )
        )

        if reference:
            return reference

    return ""


def _candidate_dict(candidate: Any) -> Dict[str, Any]:
    return {
        "appliance_id": str(
            getattr(
                candidate,
                "appliance_id",
                "",
            )
            or ""
        ),
        "display_label": str(
            getattr(
                candidate,
                "display_label",
                "",
            )
            or ""
        ),
        "name": str(
            getattr(
                candidate,
                "name",
                "",
            )
            or ""
        ),
        "brand": (
            str(
                getattr(
                    candidate,
                    "brand",
                    "",
                )
                or ""
            ).strip()
            or None
        ),
        "model": (
            str(
                getattr(
                    candidate,
                    "model",
                    "",
                )
                or ""
            ).strip()
            or None
        ),
    }


def _candidate_tokens(
    candidate: Dict[str, Any],
) -> set:
    values = [
        candidate.get(
            "display_label"
        ),
        candidate.get("name"),
        candidate.get("brand"),
        candidate.get("model"),
    ]

    return set(
        _normalize_choice_text(
            " ".join(
                str(value or "")
                for value in values
            )
        ).split()
    )


def _select_candidate_from_reply(
    reply: str,
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    normalized = _normalize_choice_text(
        reply
    )

    if not normalized:
        return None

    number_match = re.search(
        r"\b(?:option\s*)?(\d+)\b",
        normalized,
    )

    if number_match:
        index = (
            int(number_match.group(1))
            - 1
        )

        if 0 <= index < len(candidates):
            return candidates[index]

    reply_tokens = {
        token
        for token in normalized.split()
        if token not in {
            "the",
            "one",
            "existing",
            "use",
            "that",
            "this",
            "please",
        }
    }

    if not reply_tokens:
        return None

    scored = []

    for candidate in candidates:
        overlap = len(
            reply_tokens
            & _candidate_tokens(
                candidate
            )
        )

        if overlap:
            scored.append(
                (
                    overlap,
                    candidate,
                )
            )

    if not scored:
        return None

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score = scored[0][0]

    best = [
        candidate
        for score, candidate
        in scored
        if score == best_score
    ]

    if len(best) == 1:
        return best[0]

    return None


def _appliance_question(
    status: str,
    reference: str,
    candidates: List[Dict[str, Any]],
    tool_name: str = "",
) -> str:
    if status == SINGLE_MATCH:
        label = candidates[0][
            "display_label"
        ]

        if tool_name == "report_issue":
            return (
                "I found an existing appliance record: "
                f"{label}. Is this issue for that appliance, "
                "or would you like to add a new appliance?"
            )

        return (
            "I found an existing appliance record: "
            f"{label}. Is this repair/service for that "
            "appliance, or would you like to add a new appliance?"
        )

    if status == MULTIPLE_MATCHES:
        lines = [
            (
                "I found several similar appliance records. "
                "Which one is this for?"
            )
        ]

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            lines.append(
                "{}. {}".format(
                    index,
                    candidate[
                        "display_label"
                    ],
                )
            )

        lines.append(
            "{}. Add a new appliance".format(
                len(candidates) + 1
            )
        )

        return "\n".join(lines)

    readable_reference = (
        reference
        or "that appliance"
    )

    return (
        "I couldn't find an appliance record matching "
        f"'{readable_reference}'. Would you like to add "
        "the appliance record first?"
    )


def _resolved_appliance_from_context(
    restored_context: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(
        restored_context,
        dict,
    ):
        return None

    resolution = restored_context.get(
        "appliance_resolution"
    )

    if not isinstance(
        resolution,
        dict,
    ):
        return None

    if (
        resolution.get("status")
        != "CONFIRMED"
    ):
        return None

    appliance_id = str(
        resolution.get(
            "confirmed_appliance_id"
        )
        or ""
    ).strip()

    if not appliance_id:
        return None

    return dict(resolution)


def _resolve_appliance_clarification(
    *,
    tool_name: str,
    args: Dict[str, Any],
    current_action: Dict[str, Any],
    message: str,
    restored_context: Any,
) -> Dict[str, Any]:
    """Return deterministic appliance prerequisite state.

    The returned mapping contains:
      - clarification: user-facing question or None
      - missing_field: clarification field name or None
      - resolution_context: server-side context to persist
      - confirmed_appliance_id: id only after explicit user confirmation
      - add_new_requested: True when the user chose the new-appliance branch
    """

    existing_confirmed = (
        _resolved_appliance_from_context(
            restored_context
        )
    )

    if existing_confirmed:
        return {
            "clarification": None,
            "missing_field": None,
            "resolution_context": (
                existing_confirmed
            ),
            "confirmed_appliance_id": (
                existing_confirmed.get(
                    "confirmed_appliance_id"
                )
            ),
            "add_new_requested": False,
        }

    restored_resolution = None

    if isinstance(
        restored_context,
        dict,
    ):
        value = restored_context.get(
            "appliance_resolution"
        )

        if isinstance(value, dict):
            restored_resolution = dict(
                value
            )

    normalized_reply = (
        _normalize_choice_text(
            message
        )
    )

    if restored_resolution:
        candidates = list(
            restored_resolution.get(
                "candidates"
            )
            or []
        )

        wants_new_appliance = (
            normalized_reply
            in _NEW_APPLIANCE_RESPONSES
        )

        if (
            restored_resolution.get("status")
            in {NO_MATCH, "ADD_NEW_REQUIRED"}
            and normalized_reply
            in _CONFIRM_EXISTING_RESPONSES
        ):
            # For a no-match question, "yes" means yes, create the
            # missing appliance record. It does NOT confirm an existing row.
            wants_new_appliance = True

        resolved_new_reference = str(
            restored_resolution.get(
                "reference"
            )
            or ""
        ).strip()

        if (
            restored_resolution.get(
                "status"
            )
            == "ADD_NEW_REQUIRED"
            and not resolved_new_reference
            and normalized_reply
            and normalized_reply
            not in _CONFIRM_EXISTING_RESPONSES
            and normalized_reply
            not in _NEW_APPLIANCE_RESPONSES
        ):
            # The previous turn asked what the new appliance should be
            # called. Treat this reply as that name, not as a new command.
            resolved_new_reference = (
                " ".join(
                    str(message or "").split()
                ).strip()
            )
            wants_new_appliance = bool(
                resolved_new_reference
            )

        if wants_new_appliance:
            return {
                "clarification": None,
                "missing_field": None,
                "resolution_context": {
                    **restored_resolution,
                    "status": (
                        "ADD_NEW_REQUIRED"
                    ),
                    "reference": (
                        resolved_new_reference
                    ),
                },
                "confirmed_appliance_id": None,
                "add_new_requested": True,
            }

        if (
            restored_resolution.get(
                "status"
            )
            == SINGLE_MATCH
            and normalized_reply
            in _CONFIRM_EXISTING_RESPONSES
            and candidates
        ):
            chosen = candidates[0]

            return {
                "clarification": None,
                "missing_field": None,
                "resolution_context": {
                    "status": "CONFIRMED",
                    "reference": (
                        restored_resolution.get(
                            "reference"
                        )
                    ),
                    "confirmed_appliance_id": (
                        chosen.get(
                            "appliance_id"
                        )
                    ),
                    "display_label": (
                        chosen.get(
                            "display_label"
                        )
                    ),
                },
                "confirmed_appliance_id": (
                    chosen.get(
                        "appliance_id"
                    )
                ),
                "add_new_requested": False,
            }

        if candidates:
            chosen = (
                _select_candidate_from_reply(
                    message,
                    candidates,
                )
            )

            if chosen is not None:
                return {
                    "clarification": None,
                    "missing_field": None,
                    "resolution_context": {
                        "status": "CONFIRMED",
                        "reference": (
                            restored_resolution.get(
                                "reference"
                            )
                        ),
                        "confirmed_appliance_id": (
                            chosen.get(
                                "appliance_id"
                            )
                        ),
                        "display_label": (
                            chosen.get(
                                "display_label"
                            )
                        ),
                    },
                    "confirmed_appliance_id": (
                        chosen.get(
                            "appliance_id"
                        )
                    ),
                    "add_new_requested": False,
                }

        # The reply did not safely select one of the persisted candidates.
        # Ask the same deterministic question again instead of guessing.
        return {
            "clarification": _appliance_question(
                str(
                    restored_resolution.get(
                        "status"
                    )
                    or ""
                ),
                str(
                    restored_resolution.get(
                        "reference"
                    )
                    or ""
                ),
                candidates,
                tool_name=tool_name,
            ),
            "missing_field": (
                "appliance_selection"
            ),
            "resolution_context": (
                restored_resolution
            ),
            "confirmed_appliance_id": None,
            "add_new_requested": False,
        }

    reference = (
        _appliance_reference_for_call(
            tool_name,
            args,
            current_action,
            message,
        )
    )

    session = SessionLocal()

    try:
        resolution = (
            resolve_appliance_reference(
                session,
                reference,
            )
        )
    finally:
        session.close()

    candidates = [
        _candidate_dict(
            candidate
        )
        for candidate
        in resolution.candidates
    ]

    resolution_context = {
        "status": resolution.status,
        "reference": reference,
        "candidates": candidates,
    }

    if resolution.status in {
        SINGLE_MATCH,
        MULTIPLE_MATCHES,
    }:
        return {
            "clarification": (
                _appliance_question(
                    resolution.status,
                    reference,
                    candidates,
                    tool_name=tool_name,
                )
            ),
            "missing_field": (
                "appliance_selection"
            ),
            "resolution_context": (
                resolution_context
            ),
            "confirmed_appliance_id": None,
            "add_new_requested": False,
        }

    if resolution.status == NO_MATCH:
        return {
            "clarification": (
                _appliance_question(
                    NO_MATCH,
                    reference,
                    [],
                    tool_name=tool_name,
                )
            ),
            "missing_field": (
                "appliance_record_required"
            ),
            "resolution_context": (
                resolution_context
            ),
            "confirmed_appliance_id": None,
            "add_new_requested": False,
        }

    return {
        "clarification": None,
        "missing_field": None,
        "resolution_context": (
            resolution_context
        ),
        "confirmed_appliance_id": (
            resolution.confirmed_appliance_id
        ),
        "add_new_requested": False,
    }


def _dependency_appliance_context(
    current_action: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return trusted appliance identity created by a prerequisite action."""

    dependency = current_action.get(
        "dependency_context"
    )

    if not isinstance(
        dependency,
        dict,
    ):
        return None

    if (
        str(
            dependency.get("kind")
            or ""
        ).strip()
        != "appliance_creation_parent"
    ):
        return None

    if (
        str(
            dependency.get("status")
            or ""
        ).strip()
        != "confirmed"
    ):
        return None

    appliance_id = str(
        dependency.get(
            "confirmed_appliance_id"
        )
        or ""
    ).strip()

    if not appliance_id:
        return None

    return {
        "appliance_resolution": {
            "status": "CONFIRMED",
            "reference": str(
                dependency.get(
                    "reference"
                )
                or ""
            ).strip(),
            "confirmed_appliance_id": (
                appliance_id
            ),
            "display_label": str(
                dependency.get(
                    "display_label"
                )
                or dependency.get(
                    "reference"
                )
                or ""
            ).strip(),
        }
    }


def _stage_appliance_creation_dependency(
    *,
    state: AgentState,
    call: Dict[str, Any],
    args: Dict[str, Any],
    actions: List[Dict[str, Any]],
    action_index: int,
    current_action: Dict[str, Any],
    reference: str,
    is_resumed_clarification: bool,
) -> Dict[str, Any]:
    """Insert add_appliance before the exact pending maintenance/task action.

    The original tool call is preserved server-side on the parent action.
    The prerequisite itself still goes through normal consistency/RBAC/execution.
    """

    clean_reference = " ".join(
        str(reference or "").split()
    ).strip()

    if not clean_reference:
        return {
            "pending_tool_call": None,
            "pending_ai_message": None,
            "response": (
                "What appliance should I add before "
                "continuing this maintenance request?"
            ),
            "clarification_needed": True,
            "clarification_context": {
                "kind": "normal_chat",
                "missing_field": (
                    "appliance_record_name"
                ),
                "tool_name": str(
                    call.get("name")
                    or ""
                ),
                "tool_args": dict(args),
                "action_index": action_index,
                "action": dict(
                    current_action
                ),
                "appliance_resolution": {
                    "status": (
                        "ADD_NEW_REQUIRED"
                    ),
                    "reference": "",
                    "candidates": [],
                },
            },
            "confirmation_kind": None,
        }

    if not (
        0 <= action_index < len(actions)
    ):
        return {
            "pending_tool_call": None,
            "pending_ai_message": None,
            "clarification_needed": False,
            "clarification_context": None,
            "finished": True,
            "response": (
                "I couldn't safely preserve the original "
                "maintenance action while adding the appliance."
            ),
        }

    parent_call = dict(call)
    parent_call["args"] = dict(args)

    parent_action = dict(
        actions[action_index]
    )

    parent_action["status"] = "pending"
    parent_action["result"] = None
    parent_action[
        "display_result"
    ] = None
    parent_action[
        "dependency_context"
    ] = {
        "kind": (
            "appliance_creation_parent"
        ),
        "status": (
            "awaiting_creation"
        ),
        "reference": clean_reference,
        "original_tool_call": (
            parent_call
        ),
    }

    prerequisite_action = {
        "domain": "maintenance",
        "intent": (
            "Add appliance record"
        ),
        "description": (
            "Add appliance record for "
            + clean_reference
        ),
        "tool_name": (
            "add_appliance"
        ),
        "tool_args": {
            "name": clean_reference,
        },
        "status": "pending",
        "result": None,
        "display_result": None,
        "origin": "dependency",
        "dependency_context": {
            "kind": (
                "appliance_creation_prerequisite"
            ),
            "status": "pending",
            "reference": clean_reference,
        },
    }

    updated_actions = list(
        actions
    )

    updated_actions[
        action_index:action_index + 1
    ] = [
        prerequisite_action,
        parent_action,
    ]

    tool_call_id = (
        "appliance-prerequisite-"
        + uuid4().hex
    )

    pending_tool_call = {
        "name": "add_appliance",
        "args": {
            "name": clean_reference,
        },
        "id": tool_call_id,
    }

    pending_ai_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": (
                    "add_appliance"
                ),
                "args": {
                    "name": clean_reference,
                },
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )

    if is_resumed_clarification:
        try:
            complete_pending_clarification(
                state
            )
        except ClarificationWorkflowError:
            return {
                "pending_tool_call": None,
                "pending_ai_message": None,
                "clarification_needed": False,
                "clarification_context": None,
                "pending_edit_context": None,
                "confirmation_kind": None,
                "workflow_proposal_id": None,
                "finished": True,
                "response": (
                    "I understood that you want a new appliance "
                    "record, but I couldn't safely close the "
                    "pending clarification. Please try again."
                ),
            }

    return {
        "planned_actions": updated_actions,
        "current_action_index": (
            action_index
        ),
        "pending_tool_call": (
            pending_tool_call
        ),
        "pending_ai_message": (
            pending_ai_message
        ),
        "tool_result": None,
        "authorized": False,
        "auth_error": None,
        "clarification_needed": False,
        "clarification_context": None,
        "pending_edit_context": None,
        "confirmation_kind": None,
        "workflow_proposal_id": None,
        "force_action_review": False,
        "finished": False,
        "response": "",
    }

def clarification_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Central clarification gate before mutation.

    When required information is missing, preserve enough trusted
    server-side context for a later request to resume the same action.
    """

    call = state.get("pending_tool_call")

    if not call:
        return {
            "pending_tool_call": call,
        }

    tool_name = str(
        call.get("name") or ""
    ).strip()

    raw_args = call.get("args") or {}

    args = (
        dict(raw_args)
        if isinstance(raw_args, dict)
        else {}
    )

    message = str(
        state.get("message") or ""
    ).lower()
    
    restored_context = state.get(
        "clarification_context"
    )

    is_resumed_clarification = (
        isinstance(restored_context, dict)
        and restored_context.get("kind")
        == "normal_chat"
        and bool(
            str(
                state.get(
                    "workflow_proposal_id"
                )
                or ""
            ).strip()
        )
    )

    resuming_same_tool = (
        is_resumed_clarification
        and str(
            restored_context.get(
                "tool_name"
            )
            or ""
        ).strip()
        == tool_name
    )
    suggestion_proposal_id = str(
        state.get(
            "editing_workflow_proposal_id"
        )
        or state.get(
            "workflow_proposal_id"
        )
        or ""
    ).strip()

    suggestion_owned_followup = (
        str(
            state.get("confirmation_kind")
            or ""
        ).strip()
        == "suggestion"
        and bool(
            suggestion_proposal_id
        )
    )
    clarification = None
    missing_field = None
    appliance_resolution_context = None
    confirmed_appliance_id = None
    add_new_appliance_requested = False

    # --------------------------------------------------------------
    # Preserve the current planned action
    # --------------------------------------------------------------

    actions = state.get("planned_actions") or []

    try:
        action_index = int(
            state.get("current_action_index", 0)
        )
    except (TypeError, ValueError):
        action_index = 0

    current_action: Dict[str, Any] = {}

    if (
        0 <= action_index < len(actions)
        and isinstance(
            actions[action_index],
            dict,
        )
    ):
        action = actions[action_index]

        current_action = {
            "domain": action.get("domain"),
            "intent": action.get("intent"),
            "description": action.get(
                "description"
            ),
            "origin": action.get("origin"),
        }

        if isinstance(
            action.get(
                "dependency_context"
            ),
            dict,
        ):
            current_action[
                "dependency_context"
            ] = dict(
                action[
                    "dependency_context"
                ]
            )

      # --------------------------------------------------------------
    # 1. Food
    # --------------------------------------------------------------

    if tool_name in {
        "add_grocery_item",
        "add_inventory_item",
    }:
        target_words = (
            "grocery",
            "groceries",
            "grocery list",
            "shopping list",
            "inventory",
            "fridge",
            "pantry",
            "stock",
        )

        purchase_words = (
            "i bought",
            "bought",
            "i purchased",
            "purchased",
            "already bought",
            "already purchased",
        )

        food_context = " ".join(
            [
                message,
                str(
                    current_action.get("intent")
                    or ""
                ).lower(),
                str(
                    current_action.get("description")
                    or ""
                ).lower(),
            ]
        )

        target_already_known = (
            resuming_same_tool
            or suggestion_owned_followup
            or any(
                word in food_context
                for word in target_words
            )
            or any(
                word in food_context
                for word in purchase_words
            )
        )

        if not target_already_known:
            missing_field = "target"

            clarification = (
                "Did you want to add "
                f"{args.get('name', 'that')} "
                "to your grocery list or your inventory?"
            )

        elif (
            "quantity" not in args
            or not args.get("quantity")
        ):
            missing_field = "quantity"

            clarification = (
                "How much/many "
                f"{args.get('name', 'of that')} "
                "do you want to add?"
            )
    # --------------------------------------------------------------
    # 2. Tasks
    # --------------------------------------------------------------

    elif tool_name == "create_task":
        due_at = str(
            args.get("due_at", "")
        ).strip()

        repair_task = (
            not suggestion_owned_followup
            and _repair_related_task(
                args,
                current_action,
            )
        )

        if repair_task:
            appliance_result = (
                _resolve_appliance_clarification(
                    tool_name=tool_name,
                    args=args,
                    current_action=(
                        current_action
                    ),
                    message=message,
                    restored_context=(
                        restored_context
                        or _dependency_appliance_context(
                            current_action
                        )
                    ),
                )
            )

            appliance_resolution_context = (
                appliance_result.get(
                    "resolution_context"
                )
            )

            confirmed_appliance_id = (
                appliance_result.get(
                    "confirmed_appliance_id"
                )
            )

            add_new_appliance_requested = bool(
                appliance_result.get(
                    "add_new_requested"
                )
            )

            if appliance_result.get(
                "clarification"
            ):
                missing_field = (
                    appliance_result.get(
                        "missing_field"
                    )
                )

                clarification = str(
                    appliance_result[
                        "clarification"
                    ]
                )

        # Normalize task scheduling only after any appliance prerequisite is
        # satisfied. create_task remains strict ISO-only; this clarification
        # layer converts relative user wording before authorization/execution.
        if clarification is None:
            restored_missing_field = (
                str(
                    restored_context.get(
                        "missing_field"
                    )
                    or ""
                ).strip()
                if isinstance(
                    restored_context,
                    dict,
                )
                else ""
            )

            # ----------------------------------------------------------
            # Resumed date clarification
            # ----------------------------------------------------------
            if (
                resuming_same_tool
                and restored_missing_field
                == "due_date"
            ):
                date_reply = str(
                    state.get("message")
                    or ""
                ).strip()

                resolved_due_at = (
                    resolve_relative_datetime(
                        date_reply,
                        state.get(
                            "current_datetime"
                        ),
                    )
                )

                if resolved_due_at:
                    args["due_at"] = (
                        resolved_due_at
                    )
                    due_at = resolved_due_at

                    updated_call = dict(
                        call
                    )
                    updated_call[
                        "args"
                    ] = dict(args)
                    call = updated_call
                else:
                    resolved_due_date = (
                        resolve_relative_date(
                            date_reply,
                            state.get(
                                "current_datetime"
                            ),
                        )
                    )

                    if resolved_due_date:
                        # Persist the resolved date itself so the next
                        # clarification can combine it with a time reply.
                        args["due_at"] = (
                            resolved_due_date
                        )
                        due_at = (
                            resolved_due_date
                        )

                        updated_call = dict(
                            call
                        )
                        updated_call[
                            "args"
                        ] = dict(args)
                        call = updated_call

                        missing_field = (
                            "due_time"
                        )
                        clarification = (
                            "What time should I schedule "
                            f"'{args.get('title', 'that task')}' "
                            "for on that day?"
                        )
                    else:
                        missing_field = (
                            "due_date"
                        )
                        clarification = (
                            "I couldn't interpret that task date. "
                            "Please provide a date such as today, "
                            "tomorrow, next week, next Monday, "
                            "or YYYY-MM-DD."
                        )

            # ----------------------------------------------------------
            # Resumed time clarification
            # ----------------------------------------------------------
            elif (
                resuming_same_tool
                and restored_missing_field
                == "due_time"
            ):
                preserved_date = due_at

                if (
                    not preserved_date
                    or preserved_date == "None"
                ):
                    restored_args = (
                        restored_context.get(
                            "tool_args"
                        )
                        if isinstance(
                            restored_context,
                            dict,
                        )
                        else None
                    )

                    if isinstance(
                        restored_args,
                        dict,
                    ):
                        preserved_date = str(
                            restored_args.get(
                                "due_at"
                            )
                            or ""
                        ).strip()

                resolved_due_at = (
                    resolve_relative_datetime(
                        state.get("message"),
                        state.get(
                            "current_datetime"
                        ),
                        default_date=(
                            preserved_date
                            or None
                        ),
                    )
                )

                if resolved_due_at:
                    args["due_at"] = (
                        resolved_due_at
                    )
                    due_at = resolved_due_at

                    updated_call = dict(
                        call
                    )
                    updated_call[
                        "args"
                    ] = dict(args)
                    call = updated_call
                else:
                    missing_field = (
                        "due_time"
                    )
                    clarification = (
                        "I couldn't interpret that task time. "
                        "Please provide a time such as 6 PM, "
                        "10:30 AM, noon, morning, or evening."
                    )

            # ----------------------------------------------------------
            # Fresh task proposal
            # ----------------------------------------------------------
            elif (
                not due_at
                or due_at == "None"
            ):
                missing_field = "due_date"

                clarification = (
                    "What day or date should I schedule "
                    f"'{args.get('title', 'that task')}' for?"
                )

            else:
                resolved_due_at = (
                    resolve_relative_datetime(
                        due_at,
                        state.get(
                            "current_datetime"
                        ),
                    )
                )

                if resolved_due_at:
                    args["due_at"] = (
                        resolved_due_at
                    )
                    due_at = resolved_due_at

                    updated_call = dict(
                        call
                    )
                    updated_call[
                        "args"
                    ] = dict(args)
                    call = updated_call
                else:
                    resolved_due_date = (
                        resolve_relative_date(
                            due_at,
                            state.get(
                                "current_datetime"
                            ),
                        )
                    )

                    if resolved_due_date:
                        args["due_at"] = (
                            resolved_due_date
                        )
                        due_at = (
                            resolved_due_date
                        )

                        updated_call = dict(
                            call
                        )
                        updated_call[
                            "args"
                        ] = dict(args)
                        call = updated_call

                        missing_field = (
                            "due_time"
                        )
                        clarification = (
                            "What time should I schedule "
                            f"'{args.get('title', 'that task')}' "
                            "for on that day?"
                        )
                    else:
                        missing_field = (
                            "due_date"
                        )
                        clarification = (
                            "I couldn't interpret that task date. "
                            "Please provide a date such as today, "
                            "tomorrow, next week, next Monday, "
                            "or YYYY-MM-DD."
                        )

    # --------------------------------------------------------------
    # 3. Calendar
    # --------------------------------------------------------------

    elif tool_name == "create_calendar_event":
        starts_at = str(
            args.get("starts_at", "")
        ).strip()

        ends_at = str(
            args.get("ends_at", "")
        ).strip()

        restored_missing_field = (
            str(
                restored_context.get(
                    "missing_field"
                )
                or ""
            ).strip()
            if isinstance(
                restored_context,
                dict,
            )
            else ""
        )

        # ----------------------------------------------------------
        # Start date / time
        # ----------------------------------------------------------

        if (
            resuming_same_tool
            and restored_missing_field
            == "calendar_start_date"
        ):
            start_reply = str(
                state.get("message")
                or ""
            ).strip()

            resolved_start = (
                resolve_relative_datetime(
                    start_reply,
                    state.get(
                        "current_datetime"
                    ),
                )
            )

            if resolved_start:
                args["starts_at"] = (
                    resolved_start
                )
                starts_at = resolved_start

                updated_call = dict(call)
                updated_call["args"] = dict(
                    args
                )
                call = updated_call
            else:
                resolved_start_date = (
                    resolve_relative_date(
                        start_reply,
                        state.get(
                            "current_datetime"
                        ),
                    )
                )

                if resolved_start_date:
                    args["starts_at"] = (
                        resolved_start_date
                    )
                    starts_at = (
                        resolved_start_date
                    )

                    updated_call = dict(call)
                    updated_call["args"] = dict(
                        args
                    )
                    call = updated_call

                    missing_field = (
                        "calendar_start_time"
                    )
                    clarification = (
                        "What time should the calendar event start "
                        "on that day?"
                    )
                else:
                    missing_field = (
                        "calendar_start_date"
                    )
                    clarification = (
                        "I couldn't interpret the event date. "
                        "Please provide a date such as today, "
                        "tomorrow, next week, next Monday, "
                        "or YYYY-MM-DD."
                    )

        elif (
            resuming_same_tool
            and restored_missing_field
            == "calendar_start_time"
        ):
            preserved_date = starts_at

            if (
                not preserved_date
                or preserved_date == "None"
            ):
                restored_args = (
                    restored_context.get(
                        "tool_args"
                    )
                    if isinstance(
                        restored_context,
                        dict,
                    )
                    else None
                )

                if isinstance(
                    restored_args,
                    dict,
                ):
                    preserved_date = str(
                        restored_args.get(
                            "starts_at"
                        )
                        or ""
                    ).strip()

            resolved_start = (
                resolve_relative_datetime(
                    state.get("message"),
                    state.get(
                        "current_datetime"
                    ),
                    default_date=(
                        preserved_date
                        or None
                    ),
                )
            )

            if resolved_start:
                args["starts_at"] = (
                    resolved_start
                )
                starts_at = resolved_start

                updated_call = dict(call)
                updated_call["args"] = dict(
                    args
                )
                call = updated_call
            else:
                missing_field = (
                    "calendar_start_time"
                )
                clarification = (
                    "I couldn't interpret the event start time. "
                    "Please provide a time such as 10 AM, "
                    "2:30 PM, noon, morning, or evening."
                )

        elif (
            not starts_at
            or starts_at == "None"
        ):
            missing_field = (
                "calendar_start_date"
            )
            clarification = (
                "What day or date should I schedule "
                f"'{args.get('title', 'that event')}' for?"
            )

        else:
            resolved_start = (
                resolve_relative_datetime(
                    starts_at,
                    state.get(
                        "current_datetime"
                    ),
                )
            )

            if resolved_start:
                args["starts_at"] = (
                    resolved_start
                )
                starts_at = resolved_start

                updated_call = dict(call)
                updated_call["args"] = dict(
                    args
                )
                call = updated_call
            else:
                resolved_start_date = (
                    resolve_relative_date(
                        starts_at,
                        state.get(
                            "current_datetime"
                        ),
                    )
                )

                if resolved_start_date:
                    args["starts_at"] = (
                        resolved_start_date
                    )
                    starts_at = (
                        resolved_start_date
                    )

                    updated_call = dict(call)
                    updated_call["args"] = dict(
                        args
                    )
                    call = updated_call

                    missing_field = (
                        "calendar_start_time"
                    )
                    clarification = (
                        "What time should the calendar event start "
                        "on that day?"
                    )
                else:
                    missing_field = (
                        "calendar_start_date"
                    )
                    clarification = (
                        "I couldn't interpret the event start date. "
                        "Please provide a date such as today, "
                        "tomorrow, next week, next Monday, "
                        "or YYYY-MM-DD."
                    )

        # ----------------------------------------------------------
        # End time / duration — only after start is fully resolved.
        # ----------------------------------------------------------

        if clarification is None:
            start_date = (
                starts_at[:10]
                if starts_at
                else None
            )

            if (
                resuming_same_tool
                and restored_missing_field
                == "calendar_end_time"
            ):
                resolved_end = (
                    resolve_relative_datetime(
                        state.get("message"),
                        state.get(
                            "current_datetime"
                        ),
                        default_date=start_date,
                    )
                )

                if resolved_end:
                    args["ends_at"] = (
                        resolved_end
                    )
                    ends_at = resolved_end

                    updated_call = dict(call)
                    updated_call["args"] = dict(
                        args
                    )
                    call = updated_call
                else:
                    missing_field = (
                        "calendar_end_time"
                    )
                    clarification = (
                        "I couldn't interpret the event end time. "
                        "Please provide a time such as 11 AM, "
                        "3:30 PM, noon, or evening."
                    )

            elif ends_at and ends_at != "None":
                resolved_end = (
                    resolve_relative_datetime(
                        ends_at,
                        state.get(
                            "current_datetime"
                        ),
                        default_date=start_date,
                    )
                )

                if resolved_end:
                    args["ends_at"] = (
                        resolved_end
                    )
                    ends_at = resolved_end

                    updated_call = dict(call)
                    updated_call["args"] = dict(
                        args
                    )
                    call = updated_call
                else:
                    missing_field = (
                        "calendar_end_time"
                    )
                    clarification = (
                        "I couldn't interpret the event end time. "
                        "Please provide a time such as 11 AM, "
                        "3:30 PM, noon, or evening."
                    )

            else:
                duration_context = " ".join(
                    [
                        str(
                            state.get("message")
                            or ""
                        ),
                        str(
                            current_action.get(
                                "description"
                            )
                            or ""
                        ),
                    ]
                )

                duration_minutes = (
                    _calendar_duration_minutes(
                        duration_context
                    )
                )

                if duration_minutes:
                    try:
                        parsed_start = (
                            datetime.fromisoformat(
                                starts_at
                            )
                        )
                    except ValueError:
                        parsed_start = None

                    if parsed_start is not None:
                        resolved_end = (
                            parsed_start
                            + timedelta(
                                minutes=(
                                    duration_minutes
                                )
                            )
                        ).isoformat()

                        args["ends_at"] = (
                            resolved_end
                        )
                        ends_at = resolved_end

                        updated_call = dict(
                            call
                        )
                        updated_call[
                            "args"
                        ] = dict(args)
                        call = updated_call

                if not ends_at:
                    missing_field = (
                        "calendar_end_time"
                    )
                    clarification = (
                        "What time should the calendar event end, "
                        "or how long should it last?"
                    )

    # --------------------------------------------------------------
    # 4. Maintenance
    # --------------------------------------------------------------

    elif tool_name in {
        "log_repair",
        "report_issue",
    }:
        dependency_context = (
            _dependency_appliance_context(
                current_action
            )
        )

        restored_appliance_context = (
            isinstance(
                restored_context,
                dict,
            )
            and isinstance(
                restored_context.get(
                    "appliance_resolution"
                ),
                dict,
            )
        )

        explicit_appliance_reference = (
            _appliance_reference_for_call(
                tool_name,
                args,
                current_action,
                message,
            )
        )

        # Repairs always require appliance resolution. Issues do so only when
        # the request actually identifies an appliance or is resuming an
        # already-started appliance prerequisite. Generic household issues
        # remain valid with appliance_id=None.
        should_resolve_appliance = (
            tool_name == "log_repair"
            or bool(
                explicit_appliance_reference
            )
            or bool(
                dependency_context
            )
            or bool(
                restored_appliance_context
            )
        )

        # Suggestion-owned follow-ups already belong to a durable suggestion
        # workflow. Keep their existing ownership semantics unchanged.
        if (
            not suggestion_owned_followup
            and should_resolve_appliance
        ):
            appliance_result = (
                _resolve_appliance_clarification(
                    tool_name=tool_name,
                    args=args,
                    current_action=(
                        current_action
                    ),
                    message=message,
                    restored_context=(
                        restored_context
                        or dependency_context
                    ),
                )
            )

            appliance_resolution_context = (
                appliance_result.get(
                    "resolution_context"
                )
            )

            confirmed_appliance_id = (
                appliance_result.get(
                    "confirmed_appliance_id"
                )
            )

            add_new_appliance_requested = bool(
                appliance_result.get(
                    "add_new_requested"
                )
            )

            if appliance_result.get(
                "clarification"
            ):
                missing_field = (
                    appliance_result.get(
                        "missing_field"
                    )
                )

                clarification = str(
                    appliance_result[
                        "clarification"
                    ]
                )

            # Both maintenance tools accept appliance_id. Inject the id only
            # after explicit confirmation/selection; never from fuzzy ranking.
            if (
                confirmed_appliance_id
                and clarification is None
            ):
                args[
                    "appliance_id"
                ] = confirmed_appliance_id

                updated_call = dict(
                    call
                )
                updated_call["args"] = dict(
                    args
                )
                call = updated_call

        if tool_name == "report_issue":
            # report_issue has no additional required clarification once its
            # optional appliance reference has been resolved.
            pass

        if tool_name == "log_repair":
            # Normalize serviced_at only for repairs, using the shared
            # deterministic date resolver. This covers both:
            #   1. a resumed missing-date clarification, and
            #   2. a specialist-proposed relative date such as "today".
            restored_missing_field = (
                str(
                    restored_context.get("missing_field")
                    or ""
                ).strip()
                if isinstance(restored_context, dict)
                else ""
            )

            serviced_at = str(
                args.get("serviced_at", "")
            ).strip()

            # The durable clarification payload is trusted state. The specialist
            # runs again on a short reply such as "yes", so unrelated tool fields
            # must not be allowed to drift to that reply.
            restored_tool_args = (
                restored_context.get("tool_args")
                if isinstance(
                    restored_context,
                    dict,
                )
                else None
            )

            restored_serviced_at = ""

            if isinstance(
                restored_tool_args,
                dict,
            ):
                restored_serviced_at = str(
                    restored_tool_args.get(
                        "serviced_at"
                    )
                    or ""
                ).strip()

            serviced_at_source = None

            if (
                resuming_same_tool
                and restored_missing_field
                == "serviced_at"
            ):
                # This turn is answering the date question. Always consume the
                # current reply, even if a regenerated tool call contains a stale
                # non-empty serviced_at value from an earlier turn.
                serviced_at_source = (
                    state.get("message")
                )

            elif (
                resuming_same_tool
                and restored_missing_field
                in {
                    "appliance_selection",
                    "appliance_record_required",
                    "appliance_record_name",
                }
            ):
                # This turn is answering an appliance question, not a date
                # question. Preserve the original date value that was stored
                # before clarification instead of trusting a regenerated value
                # such as "yes".
                if (
                    restored_serviced_at
                    and restored_serviced_at
                    != "None"
                ):
                    serviced_at_source = (
                        restored_serviced_at
                    )
                else:
                    # Some specialist calls omit serviced_at even when the
                    # original user request contains a clear relative date such
                    # as "today". The durable clarification context preserves the
                    # original action description, so use that trusted text as a
                    # deterministic fallback before asking the user again.
                    restored_action = (
                        restored_context.get("action")
                        if isinstance(
                            restored_context,
                            dict,
                        )
                        else None
                    )

                    original_description = ""

                    if isinstance(
                        restored_action,
                        dict,
                    ):
                        original_description = str(
                            restored_action.get(
                                "description"
                            )
                            or ""
                        ).strip()

                    if not original_description:
                        original_description = str(
                            current_action.get(
                                "description"
                            )
                            or ""
                        ).strip()

                    if original_description:
                        serviced_at_source = (
                            original_description
                        )
                    else:
                        serviced_at = ""
                        args["serviced_at"] = ""

                        updated_call = dict(call)
                        updated_call["args"] = dict(
                            args
                        )
                        call = updated_call

            elif (
                serviced_at
                and serviced_at != "None"
            ):
                serviced_at_source = (
                    serviced_at
                )

            if (
                clarification is None
                and serviced_at_source is not None
            ):
                resolved_serviced_at = (
                    resolve_relative_date(
                        serviced_at_source,
                        state.get(
                            "current_datetime"
                        ),
                    )
                )

                # Appliance confirmation may restore a non-empty but unusable
                # specialist value such as "completed". If that persisted value
                # is not a date, fall back to the durable original action
                # description before asking the user for the date again.
                if (
                    not resolved_serviced_at
                    and resuming_same_tool
                    and restored_missing_field
                    in {
                        "appliance_selection",
                        "appliance_record_required",
                        "appliance_record_name",
                    }
                ):
                    restored_action = (
                        restored_context.get("action")
                        if isinstance(
                            restored_context,
                            dict,
                        )
                        else None
                    )

                    fallback_description = ""

                    if isinstance(
                        restored_action,
                        dict,
                    ):
                        fallback_description = str(
                            restored_action.get(
                                "description"
                            )
                            or ""
                        ).strip()

                    if not fallback_description:
                        fallback_description = str(
                            current_action.get(
                                "description"
                            )
                            or ""
                        ).strip()

                    if (
                        fallback_description
                        and fallback_description
                        != str(
                            serviced_at_source
                            or ""
                        ).strip()
                    ):
                        resolved_serviced_at = (
                            resolve_relative_date(
                                fallback_description,
                                state.get(
                                    "current_datetime"
                                ),
                            )
                        )

                if resolved_serviced_at:
                    args["serviced_at"] = (
                        resolved_serviced_at
                    )
                    serviced_at = (
                        resolved_serviced_at
                    )

                    updated_call = dict(call)
                    updated_call["args"] = dict(
                        args
                    )
                    call = updated_call
                else:
                    missing_field = "serviced_at"
                    clarification = (
                        "I couldn't interpret that repair date. "
                        "Please provide a date such as today, "
                        "yesterday, next week, next month, "
                        "next Monday, or YYYY-MM-DD."
                    )

            if (
                clarification is None
                and (
                    not serviced_at
                    or serviced_at == "None"
                )
            ):
                missing_field = "serviced_at"

                clarification = (
                    "What date was the repair serviced on?"
                )


    # --------------------------------------------------------------
    # Appliance record prerequisite
    # --------------------------------------------------------------

    if add_new_appliance_requested:
        reference = ""

        if isinstance(
            appliance_resolution_context,
            dict,
        ):
            reference = str(
                appliance_resolution_context.get(
                    "reference"
                )
                or ""
            ).strip()

        if reference:
            return (
                _stage_appliance_creation_dependency(
                    state=state,
                    call=call,
                    args=args,
                    actions=list(actions),
                    action_index=action_index,
                    current_action=(
                        current_action
                    ),
                    reference=reference,
                    is_resumed_clarification=(
                        is_resumed_clarification
                    ),
                )
            )

        missing_field = (
            "appliance_record_name"
        )
        clarification = (
            "What appliance should I add before "
            "continuing this maintenance request?"
        )
        appliance_resolution_context = {
            "status": "ADD_NEW_REQUIRED",
            "reference": "",
            "candidates": [],
        }

    # --------------------------------------------------------------
    # Clarification required
    # --------------------------------------------------------------

    if clarification:
        clarification_context = {
            "kind": "normal_chat",
            "missing_field": missing_field,
            "tool_name": tool_name,
            "tool_args": args,
            "action_index": action_index,
            "action": current_action,
        }

        if appliance_resolution_context:
            clarification_context[
                "appliance_resolution"
            ] = appliance_resolution_context

        
        update: Dict[str, Any] = {
            "pending_tool_call": None,
            "pending_ai_message": None,
            "response": clarification,
            "clarification_needed": True,
            "clarification_context": (
                clarification_context
            ),
            "pending_edit_context": None,
            "confirmation_kind": None,
        }
        # ----------------------------------------------------------
# Suggestion-owned clarification
#
# The accepted suggestion is already the durable owner of
# this interaction. Do not create a second WorkflowProposal.
# The next user reply will resume the same suggestion row.
# ----------------------------------------------------------

        if suggestion_owned_followup:
            update[
                "clarification_context"
            ] = None

            update[
                "confirmation_kind"
            ] = "suggestion"

            update[
                "workflow_proposal_id"
            ] = suggestion_proposal_id

            update[
                "awaiting_confirmation"
            ] = True

            return update
        # persist_clarification() needs the complete trusted state,
        # including the clarification values produced by this node.
        durable_state: Dict[str, Any] = dict(
            state
        )
        durable_state.update(
            update
        )

        persisted = persist_clarification(
            durable_state
        )

        # Keep the durable proposal reference in graph state as well.
        update["workflow_proposal_id"] = (
            persisted["proposal_id"]
        )

        return update

    if is_resumed_clarification:
        if (
            tool_name in {
                "log_repair",
                "report_issue",
            }
            and confirmed_appliance_id
        ):
            updated_call = dict(
                call
            )
            updated_args = dict(
                updated_call.get("args")
                or {}
            )
            updated_args[
                "appliance_id"
            ] = confirmed_appliance_id
            updated_call["args"] = (
                updated_args
            )
            call = updated_call

        try:
            complete_pending_clarification(
                state
            )
        except ClarificationWorkflowError:
            return {
                "pending_tool_call": None,
                "pending_ai_message": None,
                "clarification_needed": False,
                "clarification_context": None,
                "pending_edit_context": None,
                "confirmation_kind": None,
                "workflow_proposal_id": None,
                "finished": True,
                "response": (
                    "I understood the clarification, "
                    "but I couldn't safely close the "
                    "pending workflow. Please try again."
                ),
            }

    return {
        "pending_tool_call": call,
        "clarification_needed": False,
        "clarification_context": None,
        "pending_edit_context": None,
        "confirmation_kind": None,
        "workflow_proposal_id": None,
    }

def route_after_clarification(
    state: AgentState,
) -> str:
    """Route after the clarification gate."""

    if not state.get("pending_tool_call"):
        return "next_action"

    if (
        state.get("confirmation_kind")
        == "suggestion"
    ):
        return "suggestion_authorize"

    return "authorize"