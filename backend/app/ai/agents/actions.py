from __future__ import annotations

import re
from typing import Dict, List

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal, utcnow
from app.models.workflows import WorkflowProposal


_UUID_PATTERN = (
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}"
)

# Common tool result format:
#   "(pending, id=<uuid>)"
# Remove only the internal id fragment, preserving the useful row state and
# its surrounding punctuation.
_INTERNAL_ID_FIELD_RE = re.compile(
    r",?\s*\bid\s*[=:]\s*" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_WITH_ID_RE = re.compile(
    r"\s+\bwith\s+id\s+" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_BARE_UUID_RE = re.compile(
    _UUID_PATTERN,
    re.IGNORECASE,
)


_CLOUDINARY_DOWNLOAD_URL_RE = re.compile(
    r"https://api\.cloudinary\.com/[^\s]+",
    re.IGNORECASE,
)


def _sanitize_user_facing_result(value: object) -> str:
    """Hide internal identifiers and signed URLs in conversational text."""

    raw = str(value or "")

    # Preserve the real signed URL only in the structured API response.
    # Conversational text gets a stable placeholder instead.
    raw = _CLOUDINARY_DOWNLOAD_URL_RE.sub(
        "[secure document link available]",
        raw,
    )

    raw = _INTERNAL_ID_FIELD_RE.sub("", raw)
    raw = _INTERNAL_WITH_ID_RE.sub("", raw)
    raw = _INTERNAL_BARE_UUID_RE.sub("[internal-id]", raw)

    # Preserve list/newline structure returned by read tools. Only normalize
    # whitespace inside each individual line.
    lines = [
        " ".join(line.split())
        for line in raw.splitlines()
    ]

    return "\n".join(
        line
        for line in lines
        if line
    ).strip()




_MUTATION_HINTS = (
    "add ",
    "create ",
    "log ",
    "record ",
    "update ",
    "change ",
    "delete ",
    "remove ",
    "mark ",
    "complete ",
    "report ",
    "schedule ",
    "set ",
    "pay ",
    "assign ",
    "buy ",
)


_READ_TOOL_PREFIXES = ("get_", "list_", "search_")


def _is_read_tool(tool_name: object) -> bool:
    """Return True only for lookup/list tools that cannot mutate state."""

    name = str(tool_name or "").strip()
    return bool(name) and name.startswith(_READ_TOOL_PREFIXES)


def _action_requests_mutation(action: Dict) -> bool:
    """Detect whether the requested action changes household state.

    This intentionally ignores ``tool_name``. During entity resolution a
    mutation action can temporarily have ``tool_name=list_*`` or ``get_*``
    because the specialist first needs a server-derived identifier. A lookup
    must never make that mutation look completed.
    """

    text = " ".join(
        str(action.get(key) or "").casefold().strip()
        for key in ("intent", "description")
    )

    return any(hint in (text + " ") for hint in _MUTATION_HINTS)


def _action_requires_tool(action: Dict) -> bool:
    """Conservatively detect actions that must have a real tool outcome."""

    if action.get("tool_name"):
        return True

    return _action_requests_mutation(action)


def _naturalize_description(value: object) -> str:
    """Turn a planner action description into a short completion sentence."""

    description = " ".join(str(value or "").split()).strip()
    if not description:
        return "Done."

    # Small household-language normalizations for common planner phrasing.
    description = re.sub(
        r"\bto grocery list\b",
        "to the grocery list",
        description,
        flags=re.IGNORECASE,
    )

    words = description.split(" ", 1)
    verb = words[0].casefold()
    rest = words[1] if len(words) > 1 else ""

    past_tense = {
        "add": "Added",
        "create": "Created",
        "log": "Logged",
        "record": "Recorded",
        "update": "Updated",
        "change": "Changed",
        "delete": "Deleted",
        "remove": "Removed",
        "mark": "Marked",
        "complete": "Completed",
        "report": "Reported",
        "schedule": "Scheduled",
        "set": "Set",
        "pay": "Paid",
        "assign": "Assigned",
        "find": "Found",
        "show": "Found",
        "retrieve": "Retrieved",
        "list": "Listed",
        "get": "Retrieved",
    }

    lead = past_tense.get(verb)
    if lead is None:
        sentence = description[0].upper() + description[1:]
    else:
        sentence = lead + ((" " + rest) if rest else "")

    if sentence[-1:] not in ".!?":
        sentence += "."

    return sentence


def _derive_display_result(
    action: Dict,
    raw_result: object,
    *,
    specialist_response: object = None,
) -> str:
    """Build a natural user-facing result while preserving raw tool output.

    The raw tool result remains in ``action["result"]`` for server-side
    chaining/audit. This function only produces presentation text.
    """

    specialist_text = _sanitize_user_facing_result(
        specialist_response
    ).strip()

    # For read/search tools, prefer the specialist's synthesis after it has
    # consumed the tool result. This avoids dumping raw document/DB payloads.
    if specialist_text:
        return specialist_text

    raw_text = str(raw_result or "")
    sanitized = _sanitize_user_facing_result(raw_result).strip()

    # Mutation tool results often append internal resource metadata such as
    # "Grocery item with id <uuid>". If an internal UUID was present, do not
    # try to repair the tool's storage-oriented string for presentation.
    # Use the planner's natural resource description instead.
    if (
        _action_requests_mutation(action)
        and _INTERNAL_BARE_UUID_RE.search(raw_text)
    ):
        return _naturalize_description(
            action.get("description")
        )

    # Special case original documents: the real signed URL is carried in the
    # structured API field, so the conversational response only needs a label.
    filename_match = re.search(
        r"(?im)^Original document:\s*(.+?)\s*$",
        str(raw_result or ""),
    )
    if filename_match:
        filename = " ".join(filename_match.group(1).split())
        base = _naturalize_description(action.get("description"))
        return "{0} You can open {1} below.".format(
            base.rstrip("."),
            filename,
        )

    # A bare UUID has no user meaning. If one survived only as an internal-id
    # placeholder, use the planner's resource description instead.
    if not sanitized or "[internal-id]" in sanitized:
        return _naturalize_description(action.get("description"))

    return sanitized


def _format_action_result(action: Dict) -> str:
    status = str(action.get("status") or "pending").strip().casefold()
    display_result = str(
        action.get("display_result")
        or _derive_display_result(
            action,
            action.get("result"),
        )
        or ""
    ).strip()

    if status == "completed":
        return display_result or _naturalize_description(
            action.get("description")
        )

    if status == "unauthorized":
        reason = display_result or "You do not have permission for that."
        return "I couldn't complete that request: {0}".format(reason)

    if status == "failed":
        reason = display_result or "The requested action did not complete."
        return "I couldn't complete that request: {0}".format(reason)

    return "{0} ({1})".format(
        " ".join(str(action.get("description") or "Request").split()),
        status,
    )


def _build_final_response(actions: List[Dict]) -> str:
    if not actions:
        return "No actions were identified."

    rendered = [
        _format_action_result(action)
        for action in actions
    ]

    if len(rendered) == 1:
        return rendered[0]

    return "\n".join(
        "- {0}".format(item)
        for item in rendered
        if item
    ).strip()


def _finalize_approved_workflow(
    state: AgentState,
    action: Dict,
) -> bool:
    """Close the durable normal-chat proposal after its action finishes.

    Normal-chat confirmations persist one current action. Once that approved
    action has actually completed (or failed authorization/execution), its
    workflow row must not remain indefinitely in APPROVED state.
    """

    proposal_id = str(
        state.get("workflow_proposal_id") or ""
    ).strip()

    if not proposal_id:
        return False

    action_status = str(action.get("status") or "")
    if action_status not in {
        "completed",
        "failed",
        "unauthorized",
    }:
        return False

    session = SessionLocal()

    try:
        row = session.get(
            WorkflowProposal,
            proposal_id,
        )

        if row is None or row.status != "APPROVED":
            return False

        if action_status == "completed":
            row.status = "COMPLETED"
            row.last_error = None
        else:
            row.status = "FAILED"
            row.last_error = str(
                action.get("result")
                or "The approved action did not complete."
            )

        row.updated_at = utcnow()
        session.commit()
        return True

    except Exception:
        session.rollback()
        # The domain action result is already known. Do not rewrite it as a
        # success/failure based on audit-row cleanup. Codex will later move
        # normal-chat writes under the shared execution ledger.
        return False

    finally:
        session.close()


def next_action_node(state: AgentState) -> dict:
    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    if index >= len(actions):
        return {
            "finished": True,
            "response": _build_final_response(actions),
        }

    current_action = dict(actions[index])

    # ---------------------------------------------------------
    # Unauthorized action
    # ---------------------------------------------------------
    if (
        state.get("authorized") is False
        and state.get("auth_error")
    ):
        current_action["status"] = "unauthorized"
        current_action["result"] = state["auth_error"]
        current_action["display_result"] = _sanitize_user_facing_result(
            state["auth_error"]
        )

    # ---------------------------------------------------------
    # Tool result available
    # ---------------------------------------------------------
    elif state.get("tool_result") is not None:
        tool_result = str(state["tool_result"])
        executed_tool = str(current_action.get("tool_name") or "").strip()

        if tool_result.startswith("That action failed:"):
            current_action["status"] = "failed"
            current_action["result"] = tool_result
            current_action["display_result"] = _derive_display_result(
                current_action,
                tool_result,
            )
        elif tool_result.startswith("Unknown tool"):
            current_action["status"] = "failed"
            current_action["result"] = tool_result
            current_action["display_result"] = _derive_display_result(
                current_action,
                tool_result,
            )
        elif (
            _action_requests_mutation(current_action)
            and _is_read_tool(executed_tool)
        ):
            # A list/get call is only an intermediate lookup for a mutation.
            # It can resolve a stable server-side id, but it can never prove
            # that an add/update/delete/complete/etc. actually occurred.
            specialist_response = str(state.get("response") or "").strip()
            current_action["status"] = "failed"
            current_action["result"] = (
                specialist_response
                or (
                    "The lookup completed, but no mutation tool confirmed "
                    "the requested change."
                )
            )
            current_action["display_result"] = _derive_display_result(
                current_action,
                current_action["result"],
                specialist_response=specialist_response,
            )
        else:
            current_action["status"] = "completed"
            current_action["result"] = tool_result
            specialist_response = str(
                state.get("response") or ""
            ).strip()
            current_action["display_result"] = _derive_display_result(
                current_action,
                tool_result,
                specialist_response=(
                    specialist_response
                    if _is_read_tool(executed_tool)
                    else None
                ),
            )

    # ---------------------------------------------------------
    # Specialist answered without a tool
    # ---------------------------------------------------------
    else:
        if _action_requests_mutation(current_action):
            specialist_response = str(state.get("response") or "").strip()
            current_action["status"] = "failed"
            current_action["result"] = (
                specialist_response
                or "No mutation tool confirmed the requested change."
            )
            current_action["display_result"] = _derive_display_result(
                current_action,
                current_action["result"],
                specialist_response=specialist_response,
            )
        elif _action_requires_tool(current_action):
            current_action["status"] = "failed"
            current_action["result"] = (
                "No tool execution confirmed this requested action."
            )
            current_action["display_result"] = _derive_display_result(
                current_action,
                current_action["result"],
            )
        else:
            current_action["status"] = "completed"
            current_action["result"] = state.get(
                "response",
                "Action completed.",
            )
            current_action["display_result"] = _derive_display_result(
                current_action,
                current_action["result"],
                specialist_response=current_action["result"],
            )

    updated_actions = list(actions)
    updated_actions[index] = current_action

    # If this action came from a durable normal-chat approval, close that
    # exact proposal now that the approved operation has a real outcome.
    proposal_finalized = _finalize_approved_workflow(
        state,
        current_action,
    )

    next_index = index + 1

    if next_index >= len(updated_actions):
        result = {
            "planned_actions": updated_actions,
            "current_action_index": next_index,

            "pending_tool_call": None,
            "pending_ai_message": None,
            "tool_result": None,

            "authorized": False,
            "auth_error": None,

            "finished": True,
            "response": _build_final_response(
                updated_actions
            ),
        }
        if proposal_finalized:
            result["workflow_proposal_id"] = None
        return result

    result = {
        "planned_actions": updated_actions,
        "current_action_index": next_index,

        "pending_tool_call": None,
        "pending_ai_message": None,
        "tool_result": None,

        "authorized": False,
        "auth_error": None,

        "finished": False,
    }
    if proposal_finalized:
        result["workflow_proposal_id"] = None
    return result


def route_after_action(state: AgentState) -> str:
    if state.get("finished"):
        return "cross_domain_suggestion"

    return "specialist"
