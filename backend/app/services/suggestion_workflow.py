"""Durable workflow support for cross-domain follow-up suggestions.

Cross-domain suggestions are proposals, not commands.  They are stored in the
existing ``workflow_proposals`` table so a later yes/no reply binds to the exact
suggestion shown to the user.  The service deliberately contains no LLM calls.

Refactor notes
--------------
* A new offer now *supersedes* an older, unanswered suggestion offer instead of
  being silently suppressed by it.  Any other kind of active review (action,
  duplicate, conflict, document) or a suggestion the user is already answering
  still blocks the new offer, so there is never more than one live review.
* Every lookup goes through ``_query_pending``, so expiry is enforced
  consistently (previously approval and replan completion skipped it).
* Exact approval compares arguments after normalising numbers, whitespace and
  ISO datetimes, so ``2`` vs ``2.0`` or ``Z`` vs ``+00:00`` no longer fails
  an otherwise identical call.  Anything else must still match exactly.
* ``persist_suggestion_offer`` validates the suggestion shape up front.
* Session handling lives in one ``_unit_of_work`` helper.
* ``_is_expired`` handles both naive/aware mismatches.

Public API is unchanged: ``SuggestionWorkflowError``,
``persist_suggestion_offer``, ``load_pending_suggestion``,
``begin_suggestion_details``, ``reject_pending_suggestion``,
``complete_replan_suggestion``, ``approve_exact_suggestion`` and
``reject_suggestion_for_authorization``.

Compatibility target: Python 3.8+.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterator, List, Optional, Tuple

from sqlalchemy import desc

from app.db.base import SessionLocal, utcnow
from app.models.workflows import WorkflowProposal


__all__ = [
    "SUGGESTION_TTL_HOURS",
    "SuggestionWorkflowError",
    "approve_exact_suggestion",
    "begin_suggestion_details",
    "complete_replan_suggestion",
    "load_pending_suggestion",
    "persist_suggestion_offer",
    "reject_pending_suggestion",
    "reject_suggestion_for_authorization",
]

logger = logging.getLogger(__name__)

SUGGESTION_TTL_HOURS = 24

_VALID_CONTINUATION_MODES = {"exact", "collect_exact", "replan"}
_EXACT_MODES = {"exact", "collect_exact"}
_REQUIRED_SUGGESTION_KEYS = (
    "target_domain",
    "permission_tool",
    "prompt",
    "continuation_mode",
)

# A suggestion the user has not started answering may be replaced by a newer
# one.  Once details are being collected the user is mid-flow: never replace.
_SUPERSEDABLE_STAGES = {"offered"}

_ISO_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class SuggestionWorkflowError(RuntimeError):
    """Raised when a cross-domain suggestion cannot be handled safely."""


# ---------------------------------------------------------------------------
# Serialisation / integrity
# ---------------------------------------------------------------------------

def _json_default(value: Any) -> str:
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _payload_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _load_payload(row: WorkflowProposal) -> Dict[str, Any]:
    try:
        payload = json.loads(row.payload_json)
    except Exception as exc:
        raise SuggestionWorkflowError(
            "The saved follow-up suggestion is unreadable."
        ) from exc
    if not isinstance(payload, dict):
        raise SuggestionWorkflowError(
            "The saved follow-up suggestion has an invalid payload."
        )
    if _payload_hash(payload) != row.args_hash:
        raise SuggestionWorkflowError(
            "The saved follow-up suggestion failed its integrity check."
        )
    return payload


def _store_payload(row: WorkflowProposal, payload: Dict[str, Any]) -> None:
    row.payload_json = _canonical_json(payload)
    row.args_hash = _payload_hash(payload)


# ---------------------------------------------------------------------------
# Scope / identifier validation
# ---------------------------------------------------------------------------

def _clean_identifier(
    value: Any,
    field: str,
    max_length: int,
    *,
    missing_message: str,
) -> str:
    """Validate one trusted identifier (no whitespace, printable, bounded)."""

    if not isinstance(value, str):
        raise SuggestionWorkflowError(missing_message.format(field))
    cleaned = value.strip()
    if (
        not cleaned
        or cleaned != value
        or len(cleaned) > max_length
        or any(
            character.isspace() or not character.isprintable()
            for character in cleaned
        )
    ):
        raise SuggestionWorkflowError(
            "{} has an invalid value.".format(field)
        )
    return cleaned


def _required_scope_value(
    state: Dict[str, Any],
    field: str,
    max_length: int,
) -> str:
    """Read one required trusted suggestion-workflow identifier."""

    return _clean_identifier(
        state.get(field),
        field,
        max_length,
        missing_message="{} is required for suggestion workflow access.",
    )


def _workflow_scope(state: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return the exact owned user, conversation, and session scope."""

    return (
        _required_scope_value(state, "user_id", 36),
        _required_scope_value(state, "conversation_id", 36),
        _required_scope_value(state, "session_id", 100),
    )


def _selected_proposal_id(state: Dict[str, Any]) -> Optional[str]:
    """Return an optional proposal selected by confirmation routing."""

    value = state.get("workflow_proposal_id")
    if value is None:
        return None
    return _clean_identifier(
        value,
        "workflow_proposal_id",
        36,
        missing_message="{} has an invalid value.",
    )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

@contextmanager
def _unit_of_work(failure_message: Optional[str] = None) -> Iterator[Any]:
    """Yield a session; roll back on error and always close it.

    ``SuggestionWorkflowError`` passes through unchanged.  Any other exception
    is re-raised as-is when ``failure_message`` is None, or converted into a
    ``SuggestionWorkflowError(failure_message)`` otherwise.
    """

    session = SessionLocal()
    try:
        yield session
    except SuggestionWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        if failure_message is None:
            raise
        logger.exception("suggestion_workflow: %s", failure_message)
        raise SuggestionWorkflowError(failure_message) from exc
    finally:
        session.close()


def _scoped_query(session, state: Dict[str, Any]):
    """Create a fail-closed query for the exact owned scope."""

    user_id, conversation_id, session_id = _workflow_scope(state)
    return session.query(WorkflowProposal).filter(
        WorkflowProposal.user_id == user_id,
        WorkflowProposal.conversation_id == conversation_id,
        WorkflowProposal.session_id == session_id,
    )


def _is_expired(row: WorkflowProposal) -> bool:
    expires_at = row.expires_at
    if expires_at is None:
        return False

    now = utcnow()
    if expires_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif expires_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=expires_at.tzinfo)
    return expires_at <= now


def _new_expiry():
    return utcnow() + timedelta(hours=SUGGESTION_TTL_HOURS)


def _query_pending(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str] = None,
) -> Optional[WorkflowProposal]:
    """Newest live, owned suggestion awaiting review (expiring stale ones)."""

    query = _scoped_query(session, state).filter(
        WorkflowProposal.kind == "suggestion",
        WorkflowProposal.status == "AWAITING_REVIEW",
    )
    if proposal_id:
        query = query.filter(WorkflowProposal.proposal_id == proposal_id)

    row = query.order_by(
        desc(WorkflowProposal.updated_at),
        desc(WorkflowProposal.created_at),
    ).first()
    if row is None:
        return None

    if _is_expired(row):
        row.status = "EXPIRED"
        row.updated_at = utcnow()
        row.last_error = "Cross-domain suggestion expired before a decision."
        session.commit()
        return None
    return row


def _require_pending(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str],
) -> WorkflowProposal:
    row = _query_pending(session, state, proposal_id)
    if row is None:
        raise SuggestionWorkflowError(
            "The follow-up suggestion is no longer available."
        )
    return row


# ---------------------------------------------------------------------------
# Suggestion validation
# ---------------------------------------------------------------------------

def _validate_suggestion(suggestion: Any) -> Dict[str, Any]:
    if not isinstance(suggestion, dict):
        raise SuggestionWorkflowError("Suggestion payload is invalid.")

    for key in _REQUIRED_SUGGESTION_KEYS:
        if not str(suggestion.get(key) or "").strip():
            raise SuggestionWorkflowError(
                "Suggestion payload is missing '{0}'.".format(key)
            )

    mode = str(suggestion.get("continuation_mode"))
    if mode not in _VALID_CONTINUATION_MODES:
        raise SuggestionWorkflowError(
            "Suggestion has an unsupported continuation mode."
        )

    if mode in _EXACT_MODES and not str(
        suggestion.get("target_tool") or ""
    ).strip():
        raise SuggestionWorkflowError(
            "An exact suggestion must name its target tool."
        )

    if not isinstance(suggestion.get("known_args") or {}, dict):
        raise SuggestionWorkflowError("Suggestion arguments are invalid.")

    if not isinstance(suggestion.get("missing_fields") or [], (list, tuple)):
        raise SuggestionWorkflowError("Suggestion missing fields are invalid.")

    return suggestion


def _is_supersedable(row: WorkflowProposal) -> bool:
    """True for an unanswered suggestion offer that a newer one may replace."""

    if row.kind != "suggestion":
        return False
    try:
        payload = _load_payload(row)
    except SuggestionWorkflowError:
        # Unreadable rows are never replaced silently.
        return False
    return str(payload.get("stage") or "") in _SUPERSEDABLE_STAGES


# ---------------------------------------------------------------------------
# Argument comparison (exact approval)
# ---------------------------------------------------------------------------

def _parse_iso_datetime(text: str) -> Optional[datetime]:
    if not _ISO_PREFIX_RE.match(text):
        return None
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _normalize_for_compare(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
        return number if number.is_finite() else value

    if isinstance(value, datetime):
        return (
            value.astimezone(timezone.utc)
            if value.tzinfo is not None
            else value
        )

    if isinstance(value, str):
        text = " ".join(value.split())
        parsed = _parse_iso_datetime(text)
        return parsed if parsed is not None else text

    return value


def _values_equal(actual: Any, expected: Any) -> bool:
    try:
        return _normalize_for_compare(actual) == _normalize_for_compare(expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public workflow API
# ---------------------------------------------------------------------------

def persist_suggestion_offer(
    state: Dict[str, Any],
    suggestion: Dict[str, Any],
) -> str:
    """Persist one exact follow-up suggestion for later yes/no resolution.

    At most one review may be live.  An older *unanswered* suggestion offer is
    superseded by the new one; any other live review blocks the new offer.
    """

    user_id, conversation_id, session_id = _workflow_scope(state)
    suggestion = _validate_suggestion(suggestion)

    payload = {
        "kind": "suggestion",
        "stage": "offered",
        "suggestion": suggestion,
    }
    now = utcnow()

    with _unit_of_work(
        "Unable to persist the follow-up suggestion."
    ) as session:
        active_rows = _scoped_query(session, state).filter(
            WorkflowProposal.status == "AWAITING_REVIEW",
        ).all()

        supersedable: List[WorkflowProposal] = []
        blocking: List[WorkflowProposal] = []
        for active in active_rows:
            if _is_expired(active):
                active.status = "EXPIRED"
                active.updated_at = now
                active.last_error = "Review expired before a user decision."
            elif _is_supersedable(active):
                supersedable.append(active)
            else:
                blocking.append(active)

        # Never introduce an ambiguous second review.
        if blocking:
            raise SuggestionWorkflowError(
                "Another review is already awaiting a decision."
            )

        for stale in supersedable:
            stale.status = "REJECTED"
            stale.updated_at = now
            stale.last_error = "Superseded by a newer follow-up suggestion."

        row = WorkflowProposal(
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            kind="suggestion",
            revision=1,
            payload_json=_canonical_json(payload),
            args_hash=_payload_hash(payload),
            pending_document_id=None,
            status="AWAITING_REVIEW",
            expires_at=now + timedelta(hours=SUGGESTION_TTL_HOURS),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return str(row.proposal_id)


def load_pending_suggestion(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    with _unit_of_work() as session:
        row = _query_pending(session, state, _selected_proposal_id(state))
        if row is None:
            return None
        payload = _load_payload(row)
        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "payload": payload,
        }


def begin_suggestion_details(
    state: Dict[str, Any],
    proposal_id: str,
) -> Dict[str, Any]:
    """Move an offered suggestion into its missing-detail collection stage."""

    with _unit_of_work(
        "Unable to continue the follow-up suggestion."
    ) as session:
        row = _require_pending(session, state, str(proposal_id))
        payload = _load_payload(row)
        suggestion = dict(payload.get("suggestion") or {})

        if not list(suggestion.get("missing_fields") or []):
            raise SuggestionWorkflowError(
                "This suggestion does not need additional information."
            )

        payload["stage"] = "collecting_details"
        _store_payload(row, payload)
        row.revision = int(row.revision or 0) + 1
        row.updated_at = utcnow()
        row.expires_at = _new_expiry()
        row.last_error = None
        session.commit()
        session.refresh(row)
        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision),
            "suggestion": suggestion,
        }


def reject_pending_suggestion(state: Dict[str, Any]) -> Optional[str]:
    with _unit_of_work() as session:
        row = _query_pending(session, state, _selected_proposal_id(state))
        if row is None:
            return None
        row.status = "REJECTED"
        row.updated_at = utcnow()
        row.last_error = None
        session.commit()
        return str(row.proposal_id)


def complete_replan_suggestion(
    state: Dict[str, Any],
    proposal_id: str,
) -> None:
    """Close an accepted open-ended suggestion before replanning its details."""

    with _unit_of_work(
        "Unable to complete the follow-up suggestion."
    ) as session:
        row = _require_pending(session, state, str(proposal_id))
        row.status = "COMPLETED"
        row.updated_at = utcnow()
        row.last_error = None
        session.commit()


def approve_exact_suggestion(state: Dict[str, Any]) -> None:
    """Approve an exact suggestion after fresh RBAC/duplicate checks."""

    proposal_id = str(state.get("workflow_proposal_id") or "").strip()
    if not proposal_id:
        raise SuggestionWorkflowError("Suggestion proposal id is missing.")

    call = state.get("pending_tool_call") or {}
    call_name = str(call.get("name") or "")
    call_args = dict(call.get("args") or {})

    with _unit_of_work(
        "Unable to approve the follow-up suggestion."
    ) as session:
        row = _require_pending(session, state, proposal_id)
        payload = _load_payload(row)
        suggestion = dict(payload.get("suggestion") or {})

        expected_tool = str(suggestion.get("target_tool") or "")
        if not expected_tool or call_name != expected_tool:
            raise SuggestionWorkflowError(
                "The approved suggestion no longer matches the proposed tool."
            )

        known_args = dict(suggestion.get("known_args") or {})
        for key, expected in known_args.items():
            if not _values_equal(call_args.get(key), expected):
                raise SuggestionWorkflowError(
                    "The approved suggestion arguments changed before execution."
                )

        if suggestion.get("missing_fields"):
            raise SuggestionWorkflowError(
                "The suggestion still has unresolved information."
            )

        row.status = "APPROVED"
        row.approved_by = (
            str(state.get("user_id")) if state.get("user_id") else None
        )
        row.approved_at = utcnow()
        row.updated_at = utcnow()
        row.last_error = None
        session.commit()


def reject_suggestion_for_authorization(state: Dict[str, Any]) -> None:
    """Best-effort: close a suggestion that failed its fresh RBAC check."""

    proposal_id = str(state.get("workflow_proposal_id") or "").strip()
    if not proposal_id:
        return

    try:
        with _unit_of_work() as session:
            row = _query_pending(session, state, proposal_id)
            if row is None:
                return
            row.status = "REJECTED"
            row.updated_at = utcnow()
            row.last_error = "Suggestion failed a fresh authorization check."
            session.commit()
    except Exception:
        # Closing the suggestion is best effort; authorization has already
        # denied the call, so never let this mask that outcome.
        logger.exception(
            "suggestion_workflow: could not reject suggestion after "
            "authorization failure"
        )