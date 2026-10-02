"""Durable workflow support for normal-chat clarification.

A clarification is persisted in the existing workflow_proposals table so a
later short reply such as "1 kg", "Saturday", or "10 AM" can be associated
with the exact action that originally requested the missing information.

This module contains deterministic application logic only. It does not call
an LLM and it does not execute domain mutations.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import desc

from app.db.base import SessionLocal, utcnow
from app.models.workflows import WorkflowProposal


CLARIFICATION_KIND = "clarification"
CLARIFICATION_TTL_HOURS = 24


class ClarificationWorkflowError(RuntimeError):
    """Raised when clarification state cannot be handled safely."""


# ---------------------------------------------------------------------------
# Serialization / integrity
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


def _payload_hash(
    payload: Dict[str, Any],
) -> str:
    encoded = _canonical_json(
        payload
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


# ---------------------------------------------------------------------------
# Exact workflow scope
# ---------------------------------------------------------------------------


def _required_scope_value(
    state: Dict[str, Any],
    field: str,
    max_length: int,
) -> str:
    value = state.get(field)

    if not isinstance(value, str):
        raise ClarificationWorkflowError(
            "{} is required for clarification.".format(
                field
            )
        )

    cleaned = value.strip()

    if (
        not cleaned
        or cleaned != value
        or len(cleaned) > max_length
        or any(
            character.isspace()
            or not character.isprintable()
            for character in cleaned
        )
    ):
        raise ClarificationWorkflowError(
            "{} has an invalid value.".format(
                field
            )
        )

    return cleaned


def _workflow_scope(
    state: Dict[str, Any],
) -> Tuple[str, str, str]:
    """Return exact authenticated clarification scope."""

    return (
        _required_scope_value(
            state,
            "user_id",
            36,
        ),
        _required_scope_value(
            state,
            "conversation_id",
            36,
        ),
        _required_scope_value(
            state,
            "session_id",
            100,
        ),
    )


def _scoped_query(
    session,
    state: Dict[str, Any],
):
    user_id, conversation_id, session_id = (
        _workflow_scope(state)
    )

    return session.query(
        WorkflowProposal
    ).filter(
        WorkflowProposal.user_id
        == user_id,
        WorkflowProposal.conversation_id
        == conversation_id,
        WorkflowProposal.session_id
        == session_id,
    )


# ---------------------------------------------------------------------------
# Expiry / payload loading
# ---------------------------------------------------------------------------


def _is_expired(
    row: WorkflowProposal,
) -> bool:
    expires_at = row.expires_at

    if expires_at is None:
        return False

    now = utcnow()

    if (
        expires_at.tzinfo is None
        and now.tzinfo is not None
    ):
        now = now.replace(
            tzinfo=None
        )

    elif (
        expires_at.tzinfo is not None
        and now.tzinfo is None
    ):
        now = now.replace(
            tzinfo=expires_at.tzinfo
        )

    return expires_at <= now


def _new_expiry():
    return utcnow() + timedelta(
        hours=CLARIFICATION_TTL_HOURS
    )


def _load_payload(
    row: WorkflowProposal,
) -> Dict[str, Any]:
    try:
        payload = json.loads(
            row.payload_json
        )
    except Exception as exc:
        raise ClarificationWorkflowError(
            "The saved clarification is unreadable."
        ) from exc

    if not isinstance(payload, dict):
        raise ClarificationWorkflowError(
            "The saved clarification has an invalid payload."
        )

    if (
        _payload_hash(payload)
        != row.args_hash
    ):
        raise ClarificationWorkflowError(
            "The saved clarification failed its integrity check."
        )

    return payload


def _query_pending(
    session,
    state: Dict[str, Any],
) -> Optional[WorkflowProposal]:
    """Return newest live clarification in exact owned scope."""

    row = (
        _scoped_query(
            session,
            state,
        )
        .filter(
            WorkflowProposal.kind
            == CLARIFICATION_KIND,
            WorkflowProposal.status
            == "AWAITING_REVIEW",
        )
        .order_by(
            desc(
                WorkflowProposal.updated_at
            ),
            desc(
                WorkflowProposal.created_at
            ),
        )
        .first()
    )

    if row is None:
        return None

    if _is_expired(row):
        row.status = "EXPIRED"
        row.updated_at = utcnow()
        row.last_error = (
            "Clarification expired before "
            "the user supplied an answer."
        )

        session.commit()

        return None

    return row


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


def _build_payload(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    context = state.get(
        "clarification_context"
    )

    if (
        not isinstance(context, dict)
        or not context
    ):
        raise ClarificationWorkflowError(
            "Clarification context is missing."
        )

    question = str(
        state.get("response") or ""
    ).strip()

    if not question:
        raise ClarificationWorkflowError(
            "Clarification question is missing."
        )

    raw_actions = (
        state.get("planned_actions")
        or []
    )

    if not isinstance(
        raw_actions,
        list,
    ):
        raise ClarificationWorkflowError(
            "Planned actions have an invalid value."
        )

    planned_actions = []

    for action in raw_actions:
        if not isinstance(
            action,
            dict,
        ):
            raise ClarificationWorkflowError(
                "A planned action has an invalid value."
            )

        planned_actions.append(
            dict(action)
        )

    raw_index = state.get(
        "current_action_index",
        0,
    )

    if (
        isinstance(raw_index, bool)
        or not isinstance(
            raw_index,
            int,
        )
        or raw_index < 0
    ):
        raise ClarificationWorkflowError(
            "Current action index has an invalid value."
        )

    return {
        "kind": CLARIFICATION_KIND,
        "stage": "awaiting_answer",
        "question": question,
        "clarification_context": dict(
            context
        ),
        "planned_actions": (
            planned_actions
        ),
        "current_action_index": (
            raw_index
        ),
    }


# ---------------------------------------------------------------------------
# Public workflow operations
# ---------------------------------------------------------------------------


def persist_clarification(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist or revise one pending normal-chat clarification.

    If this scope already has a clarification, reuse the same proposal and
    advance its revision when the clarification changes. This is important
    for multi-stage clarification, for example:

        add apple
        -> ask grocery/inventory
        -> user says grocery list
        -> same proposal revision advances
        -> ask quantity
    """

    if not state.get(
        "clarification_needed"
    ):
        raise ClarificationWorkflowError(
            "Cannot persist clarification when "
            "clarification_needed is false."
        )

    user_id, conversation_id, session_id = (
        _workflow_scope(state)
    )

    payload = _build_payload(
        state
    )

    payload_json = _canonical_json(
        payload
    )

    args_hash = _payload_hash(
        payload
    )

    now = utcnow()

    session = SessionLocal()

    try:
        # --------------------------------------------------------------
        # Do not create an ambiguous second active workflow.
        # --------------------------------------------------------------

        active_rows = (
            _scoped_query(
                session,
                state,
            )
            .filter(
                WorkflowProposal.status
                == "AWAITING_REVIEW",
            )
            .order_by(
                desc(
                    WorkflowProposal.updated_at
                ),
                desc(
                    WorkflowProposal.created_at
                ),
            )
            .all()
        )

        clarifications = []

        for active in active_rows:
            if _is_expired(active):
                active.status = "EXPIRED"
                active.updated_at = now
                active.last_error = (
                    "Workflow expired before "
                    "the user responded."
                )
                continue

            if (
                active.kind
                != CLARIFICATION_KIND
            ):
                session.commit()

                raise ClarificationWorkflowError(
                    "Another workflow is already "
                    "awaiting a response."
                )

            clarifications.append(
                active
            )

        # --------------------------------------------------------------
        # Reuse newest clarification if one already exists.
        # --------------------------------------------------------------

        if clarifications:
            row = clarifications[0]

            # Defensive cleanup if an older buggy version somehow created
            # multiple clarification rows in the same exact scope.
            for stale in clarifications[1:]:
                stale.status = "CANCELLED"
                stale.updated_at = now
                stale.last_error = (
                    "Superseded by a newer "
                    "clarification revision."
                )

            if row.args_hash != args_hash:
                row.revision = int(
                    row.revision or 0
                ) + 1

                row.payload_json = (
                    payload_json
                )

                row.args_hash = args_hash

            row.updated_at = now
            row.expires_at = (
                _new_expiry()
            )
            row.last_error = None

            session.commit()
            session.refresh(row)

            return {
                "proposal_id": str(
                    row.proposal_id
                ),
                "revision": int(
                    row.revision
                ),
                "args_hash": str(
                    row.args_hash
                ),
            }

        # --------------------------------------------------------------
        # First clarification for this scope.
        # --------------------------------------------------------------

        row = WorkflowProposal(
            user_id=user_id,
            conversation_id=(
                conversation_id
            ),
            session_id=session_id,
            kind=CLARIFICATION_KIND,
            revision=1,
            payload_json=payload_json,
            args_hash=args_hash,
            pending_document_id=None,
            status="AWAITING_REVIEW",
            expires_at=(
                _new_expiry()
            ),
        )

        session.add(row)
        session.commit()
        session.refresh(row)

        return {
            "proposal_id": str(
                row.proposal_id
            ),
            "revision": int(
                row.revision
            ),
            "args_hash": str(
                row.args_hash
            ),
        }

    except ClarificationWorkflowError:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()

        raise ClarificationWorkflowError(
            "Unable to persist clarification."
        ) from exc

    finally:
        session.close()


def load_pending_clarification(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Load the exact pending clarification for the current scope."""

    session = SessionLocal()

    try:
        row = _query_pending(
            session,
            state,
        )

        if row is None:
            return None

        payload = _load_payload(
            row
        )

        return {
            "proposal_id": str(
                row.proposal_id
            ),
            "revision": int(
                row.revision
            ),
            "args_hash": str(
                row.args_hash
            ),
            "payload": payload,
        }

    except ClarificationWorkflowError:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()

        raise ClarificationWorkflowError(
            "Unable to load pending clarification."
        ) from exc

    finally:
        session.close()


def complete_pending_clarification(
    state: Dict[str, Any],
) -> Optional[str]:
    """Mark the current clarification completed."""

    session = SessionLocal()

    try:
        row = _query_pending(
            session,
            state,
        )

        if row is None:
            return None

        row.status = "COMPLETED"
        row.updated_at = utcnow()
        row.last_error = None

        session.commit()

        return str(
            row.proposal_id
        )

    except ClarificationWorkflowError:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()

        raise ClarificationWorkflowError(
            "Unable to complete clarification."
        ) from exc

    finally:
        session.close()


def cancel_pending_clarification(
    state: Dict[str, Any],
) -> Optional[str]:
    """Cancel the current pending clarification."""

    session = SessionLocal()

    try:
        row = _query_pending(
            session,
            state,
        )

        if row is None:
            return None

        row.status = "CANCELLED"
        row.updated_at = utcnow()
        row.last_error = None

        session.commit()

        return str(
            row.proposal_id
        )

    except ClarificationWorkflowError:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()

        raise ClarificationWorkflowError(
            "Unable to cancel clarification."
        ) from exc

    finally:
        session.close()