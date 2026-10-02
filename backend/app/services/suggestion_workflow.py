"""Durable workflow support for cross-domain follow-up suggestions.



Cross-domain suggestions are proposals, not commands.  They are stored in the

existing ``workflow_proposals`` table so a later yes/no reply binds to the exact

suggestion shown to the user.  The service deliberately contains no LLM calls.



Compatibility target: Python 3.8+.

"""

from __future__ import annotations



import hashlib

import json

from datetime import timedelta

from typing import Any, Dict, Optional, Tuple



from sqlalchemy import desc



from app.db.base import SessionLocal, utcnow

from app.models.workflows import WorkflowProposal





SUGGESTION_TTL_HOURS = 24





class SuggestionWorkflowError(RuntimeError):

    """Raised when a cross-domain suggestion cannot be handled safely."""





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





def _required_scope_value(

    state: Dict[str, Any],

    field: str,

    max_length: int,

) -> str:

    """Read one required trusted suggestion-workflow identifier."""



    value = state.get(field)



    if not isinstance(value, str):

        raise SuggestionWorkflowError(

            "{} is required for suggestion workflow access.".format(

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

        raise SuggestionWorkflowError(

            "{} has an invalid value.".format(field)

        )



    return cleaned





def _workflow_scope(

    state: Dict[str, Any],

) -> Tuple[str, str, str]:

    """Return the exact owned user, conversation, and session scope."""



    return (

        _required_scope_value(state, "user_id", 36),

        _required_scope_value(state, "conversation_id", 36),

        _required_scope_value(state, "session_id", 100),

    )





def _selected_proposal_id(

    state: Dict[str, Any],

) -> Optional[str]:

    """Return an optional proposal selected by confirmation routing."""



    value = state.get("workflow_proposal_id")

    if value is None:

        return None



    if not isinstance(value, str):

        raise SuggestionWorkflowError(

            "workflow_proposal_id has an invalid value."

        )



    cleaned = value.strip()

    if (

        not cleaned

        or cleaned != value

        or len(cleaned) > 36

        or any(

            character.isspace()

            or not character.isprintable()

            for character in cleaned

        )

    ):

        raise SuggestionWorkflowError(

            "workflow_proposal_id has an invalid value."

        )



    return cleaned





def _scoped_query(session, state: Dict[str, Any]):

    """Create a fail-closed query for the exact owned scope."""



    user_id, conversation_id, session_id = _workflow_scope(state)

    return session.query(WorkflowProposal).filter(

        WorkflowProposal.user_id == user_id,

        WorkflowProposal.conversation_id == conversation_id,

        WorkflowProposal.session_id == session_id,

    )





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





def _is_expired(row: WorkflowProposal) -> bool:

    expires_at = row.expires_at

    if expires_at is None:

        return False



    now = utcnow()

    comparable_now = now

    if expires_at.tzinfo is None and comparable_now.tzinfo is not None:

        comparable_now = comparable_now.replace(tzinfo=None)

    return expires_at <= comparable_now





def _query_pending(

    session,

    state: Dict[str, Any],

    proposal_id: Optional[str] = None,

) -> Optional[WorkflowProposal]:

    query = _scoped_query(session, state).filter(

        WorkflowProposal.kind == "suggestion",

        WorkflowProposal.status == "AWAITING_REVIEW",

    )

    if proposal_id:

        query = query.filter(

            WorkflowProposal.proposal_id == proposal_id

        )



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





def persist_suggestion_offer(

    state: Dict[str, Any],

    suggestion: Dict[str, Any],

) -> str:

    """Persist one exact follow-up suggestion for later yes/no resolution."""



    user_id, conversation_id, session_id = _workflow_scope(state)



    if not isinstance(suggestion, dict):

        raise SuggestionWorkflowError("Suggestion payload is invalid.")



    payload = {

        "kind": "suggestion",

        "stage": "offered",

        "suggestion": suggestion,

    }

    payload_json = _canonical_json(payload)

    args_hash = _payload_hash(payload)

    now = utcnow()

    session = SessionLocal()

    try:

        # Never introduce an ambiguous second review.  If any unrelated review

        # is already active, suppress the suggestion rather than replacing it.

        existing = _scoped_query(session, state).filter(

            WorkflowProposal.status == "AWAITING_REVIEW",

        )



        active_rows = existing.all()

        live_rows = []

        for active in active_rows:

            if _is_expired(active):

                active.status = "EXPIRED"

                active.updated_at = now

                active.last_error = "Review expired before a user decision."

            else:

                live_rows.append(active)



        if live_rows:

            raise SuggestionWorkflowError(

                "Another review is already awaiting a decision."

            )



        row = WorkflowProposal(

            session_id=session_id,

            conversation_id=conversation_id,

            user_id=user_id,

            kind="suggestion",

            revision=1,

            payload_json=payload_json,

            args_hash=args_hash,

            pending_document_id=None,

            status="AWAITING_REVIEW",

            expires_at=now + timedelta(hours=SUGGESTION_TTL_HOURS),

        )

        session.add(row)

        session.commit()

        session.refresh(row)

        return str(row.proposal_id)

    except SuggestionWorkflowError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise SuggestionWorkflowError(

            "Unable to persist the follow-up suggestion."

        ) from exc

    finally:

        session.close()





def load_pending_suggestion(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    session = SessionLocal()

    try:

        row = _query_pending(

            session,

            state,

            _selected_proposal_id(state),

        )

        if row is None:

            return None

        payload = _load_payload(row)

        return {

            "proposal_id": str(row.proposal_id),

            "revision": int(row.revision or 1),

            "payload": payload,

        }

    finally:

        session.close()





def begin_suggestion_details(

    state: Dict[str, Any],

    proposal_id: str,

) -> Dict[str, Any]:

    """Move an offered suggestion into its missing-detail collection stage."""



    session = SessionLocal()

    try:

        row = _query_pending(

            session,

            state,

            str(proposal_id),

        )

        if row is None:

            raise SuggestionWorkflowError(

                "The follow-up suggestion is no longer available."

            )



        payload = _load_payload(row)

        suggestion = dict(payload.get("suggestion") or {})

        missing_fields = list(suggestion.get("missing_fields") or [])

        if not missing_fields:

            raise SuggestionWorkflowError(

                "This suggestion does not need additional information."

            )



        payload["stage"] = "collecting_details"

        row.revision = int(row.revision or 0) + 1

        row.payload_json = _canonical_json(payload)

        row.args_hash = _payload_hash(payload)

        row.updated_at = utcnow()

        row.expires_at = utcnow() + timedelta(hours=SUGGESTION_TTL_HOURS)

        row.last_error = None

        session.commit()

        session.refresh(row)



        return {

            "proposal_id": str(row.proposal_id),

            "revision": int(row.revision),

            "suggestion": suggestion,

        }

    except SuggestionWorkflowError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise SuggestionWorkflowError(

            "Unable to continue the follow-up suggestion."

        ) from exc

    finally:

        session.close()





def reject_pending_suggestion(state: Dict[str, Any]) -> Optional[str]:

    session = SessionLocal()

    try:

        row = _query_pending(

            session,

            state,

            _selected_proposal_id(state),

        )

        if row is None:

            return None

        row.status = "REJECTED"

        row.updated_at = utcnow()

        row.last_error = None

        session.commit()

        return str(row.proposal_id)

    finally:

        session.close()





def complete_replan_suggestion(

    state: Dict[str, Any],

    proposal_id: str,

) -> None:

    """Close an accepted open-ended suggestion before replanning its details."""



    session = SessionLocal()

    try:

        query = _scoped_query(session, state).filter(

            WorkflowProposal.proposal_id == str(proposal_id),

            WorkflowProposal.kind == "suggestion",

            WorkflowProposal.status == "AWAITING_REVIEW",

        )

        row = query.first()

        if row is None:

            raise SuggestionWorkflowError(

                "The follow-up suggestion is no longer available."

            )

        row.status = "COMPLETED"

        row.updated_at = utcnow()

        row.last_error = None

        session.commit()

    except SuggestionWorkflowError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise SuggestionWorkflowError(

            "Unable to complete the follow-up suggestion."

        ) from exc

    finally:

        session.close()





def approve_exact_suggestion(

    state: Dict[str, Any],

) -> None:

    """Approve an exact suggestion after fresh RBAC/duplicate checks."""



    proposal_id = str(state.get("workflow_proposal_id") or "").strip()

    if not proposal_id:

        raise SuggestionWorkflowError("Suggestion proposal id is missing.")



    call = state.get("pending_tool_call") or {}

    call_name = str(call.get("name") or "")

    call_args = dict(call.get("args") or {})



    session = SessionLocal()

    try:

        query = _scoped_query(session, state).filter(

            WorkflowProposal.proposal_id == proposal_id,

            WorkflowProposal.kind == "suggestion",

            WorkflowProposal.status == "AWAITING_REVIEW",

        )

        row = query.first()

        if row is None:

            raise SuggestionWorkflowError(

                "The follow-up suggestion is no longer available."

            )



        payload = _load_payload(row)

        suggestion = dict(payload.get("suggestion") or {})

        expected_tool = str(suggestion.get("target_tool") or "")

        known_args = dict(suggestion.get("known_args") or {})



        if not expected_tool or call_name != expected_tool:

            raise SuggestionWorkflowError(

                "The approved suggestion no longer matches the proposed tool."

            )



        for key, expected in known_args.items():

            if call_args.get(key) != expected:

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

    except SuggestionWorkflowError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise SuggestionWorkflowError(

            "Unable to approve the follow-up suggestion."

        ) from exc

    finally:

        session.close()





def reject_suggestion_for_authorization(

    state: Dict[str, Any],

) -> None:

    proposal_id = str(state.get("workflow_proposal_id") or "").strip()

    if not proposal_id:

        return



    session = SessionLocal()

    try:

        query = _scoped_query(session, state).filter(

            WorkflowProposal.proposal_id == proposal_id,

            WorkflowProposal.kind == "suggestion",

            WorkflowProposal.status == "AWAITING_REVIEW",

        )

        row = query.first()

        if row is None:

            return

        row.status = "REJECTED"

        row.updated_at = utcnow()

        row.last_error = "Suggestion failed a fresh authorization check."

        session.commit()

    except Exception:

        session.rollback()

    finally:

        session.close()
