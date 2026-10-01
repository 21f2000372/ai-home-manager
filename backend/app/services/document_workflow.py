"""Durable, owner-scoped document review workflow.



This service owns persisted document proposals, revision/hash integrity,

approval and rejection state, trusted edit-context reconstruction, and

review expiration.



Every operation requires an authenticated user plus a validated

conversation/session pair.



Compatible with Python 3.9.

"""



from __future__ import annotations



import hashlib

import json

from datetime import timedelta

from typing import Any, Dict, Optional, Tuple



from sqlalchemy import desc



from app.db.base import SessionLocal, utcnow

from app.models.documents import PendingDocumentUpload

from app.models.workflows import WorkflowProposal

from app.services.document_lifecycle import (

    PENDING_DOCUMENT_TTL_HOURS,

    cleanup_terminal_pending_upload,

    mark_document_review_expired,

)





DOCUMENT_PROPOSAL_TTL_HOURS = (

    PENDING_DOCUMENT_TTL_HOURS

)

FAILED_DOCUMENT_RETRY_MAX_AGE_HOURS = 24

DOCUMENT_REVIEW_KIND = "document"
DOCUMENT_ACTION_KIND = "document_action"





class DocumentWorkflowError(RuntimeError):

    """Raised when document review cannot be handled safely."""





def _json_default(

    value: Any,

) -> str:

    return str(value)





def _canonical_json(

    value: Any,

) -> str:

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





def _required_scope_value(

    state: Dict[str, Any],

    field: str,

    max_length: int,

) -> str:

    """Read a required trusted workflow scope value."""



    value = state.get(field)



    if value is None:

        raise DocumentWorkflowError(

            "{} is required for document workflow access.".format(

                field

            )

        )



    if not isinstance(value, str):

        raise DocumentWorkflowError(

            "{} has an invalid value.".format(field)

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

        raise DocumentWorkflowError(

            "{} has an invalid value.".format(field)

        )



    return cleaned





def _workflow_scope(

    state: Dict[str, Any],

) -> Tuple[str, str, str]:

    """Return required user, conversation, and session IDs."""



    user_id = _required_scope_value(

        state,

        "user_id",

        36,

    )

    conversation_id = _required_scope_value(

        state,

        "conversation_id",

        36,

    )

    session_id = _required_scope_value(

        state,

        "session_id",

        100,

    )



    return (

        user_id,

        conversation_id,

        session_id,

    )





def _selected_proposal_id(

    state: Dict[str, Any],

) -> Optional[str]:

    """Return an optional trusted proposal selected by confirmation routing."""



    value = state.get(

        "workflow_proposal_id"

    )



    if value is None:

        return None



    if not isinstance(value, str):

        raise DocumentWorkflowError(

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

        raise DocumentWorkflowError(

            "workflow_proposal_id has an invalid value."

        )



    return cleaned





def _load_payload(

    row: WorkflowProposal,

) -> Dict[str, Any]:

    """Load and verify the persisted proposal revision."""



    try:

        payload = json.loads(

            row.payload_json

        )

    except Exception as exc:

        raise DocumentWorkflowError(

            "The saved document review is unreadable."

        ) from exc



    if not isinstance(payload, dict):

        raise DocumentWorkflowError(

            "The saved document review has an invalid payload."

        )



    if (

        _payload_hash(payload)

        != row.args_hash

    ):

        raise DocumentWorkflowError(

            "The saved document review failed its "

            "integrity check."

        )



    return payload





def _mark_expired_if_needed(

    session,

    row: WorkflowProposal,

) -> bool:

    """Expire a stale review before it can be used."""



    expires_at = row.expires_at



    if expires_at is None:

        return False



    now = utcnow()

    comparable_now = now



    if (

        expires_at.tzinfo is None

        and comparable_now.tzinfo is not None

    ):

        comparable_now = (

            comparable_now.replace(

                tzinfo=None

            )

        )

    elif (

        expires_at.tzinfo is not None

        and comparable_now.tzinfo is None

    ):

        comparable_now = (

            comparable_now.replace(

                tzinfo=expires_at.tzinfo

            )

        )



    if expires_at > comparable_now:

        return False



    pending_cleanup_id = (

        mark_document_review_expired(

            session,

            row,

            now=now,

        )

    )



    session.commit()



    if pending_cleanup_id:

        cleanup_terminal_pending_upload(

            pending_cleanup_id

        )



    return True



def _is_older_than(

    value,

    now,

    hours: int,

) -> bool:

    """Compare mixed SQLite-naive and timezone-aware timestamps safely."""



    if value is None:

        return True



    comparable_now = now

    if value.tzinfo is None and comparable_now.tzinfo is not None:

        comparable_now = comparable_now.replace(tzinfo=None)

    elif value.tzinfo is not None and comparable_now.tzinfo is None:

        comparable_now = comparable_now.replace(tzinfo=value.tzinfo)



    return value < (

        comparable_now

        - timedelta(hours=hours)

    )





def _find_pending_row(

    session,

    state: Dict[str, Any],

    proposal_id: Optional[str] = None,

) -> Optional[WorkflowProposal]:

    """Find one pending review inside the exact trusted scope."""



    (

        user_id,

        conversation_id,

        session_id,

    ) = _workflow_scope(state)



    query = (

        session.query(WorkflowProposal)

        .filter(

            WorkflowProposal.user_id

            == user_id,

            WorkflowProposal.conversation_id

            == conversation_id,

            WorkflowProposal.session_id

            == session_id,

            WorkflowProposal.kind

            == "document",

            WorkflowProposal.status

            == "AWAITING_REVIEW",

        )

    )



    if proposal_id:

        query = query.filter(

            WorkflowProposal.proposal_id

            == str(proposal_id)

        )



    row = (

        query.order_by(

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



    if _mark_expired_if_needed(

        session,

        row,

    ):

        return None



    return row



def _find_exact_document_row(

    session,

    state: Dict[str, Any],

    proposal_id: Optional[str],

) -> Optional[WorkflowProposal]:

    """Load one exact document workflow inside the authenticated scope."""



    if not proposal_id:

        return None



    (

        user_id,

        conversation_id,

        session_id,

    ) = _workflow_scope(state)



    return (

        session.query(WorkflowProposal)

        .filter(

            WorkflowProposal.proposal_id

            == str(proposal_id),

            WorkflowProposal.user_id

            == user_id,

            WorkflowProposal.conversation_id

            == conversation_id,

            WorkflowProposal.session_id

            == session_id,

            WorkflowProposal.kind

            == "document",

        )

        .first()

    )



def _already_approved_result(

    row: Optional[WorkflowProposal],

) -> Optional[Dict[str, Any]]:

    """Return an idempotent result for an already-handled approval."""



    if row is None:

        return None



    status = str(row.status or "")

    messages = {

        "APPROVED": (

            "This document review was already approved "

            "and is waiting for execution."

        ),

        "EXECUTING": (

            "This document review was already approved "

            "and is being processed."

        ),

        "COMPLETED": (

            "This document review was already approved "

            "and completed."

        ),

    }



    message = messages.get(status)

    if message is None:

        return None



    payload = _load_payload(row)



    return {

        "proposal_id": str(row.proposal_id),

        "revision": int(row.revision or 1),

        "args_hash": str(row.args_hash),

        "payload": payload,

        "already_handled": True,

        "status": status,

        "message": message,

    }





def _find_owned_pending_upload(

    session,

    *,

    pending_id: Any,

    user_id: str,

) -> Optional[PendingDocumentUpload]:

    """Find a staged upload only when it belongs to the user."""



    pending_key = str(

        pending_id or ""

    ).strip()



    if not pending_key:

        return None



    return (

        session.query(

            PendingDocumentUpload

        )

        .filter(

            PendingDocumentUpload.pending_id

            == pending_key,

            PendingDocumentUpload.uploaded_by

            == user_id,

        )

        .first()

    )





def _pending_upload_to_ingestion(

    pending: PendingDocumentUpload,

) -> Dict[str, Any]:

    """Reconstruct trusted ingestion state for document edits."""



    try:

        review_reasons = json.loads(

            pending.review_reasons_json

            or "[]"

        )

    except Exception:

        review_reasons = []



    if not isinstance(

        review_reasons,

        list,

    ):

        review_reasons = []



    try:

        visual_hashes = json.loads(

            pending.visual_hashes_json

            or "[]"

        )

    except Exception:

        visual_hashes = []



    if not isinstance(

        visual_hashes,

        list,

    ):

        visual_hashes = []



    return {

        "success": True,

        "status": pending.status,

        "upload_id": pending.upload_id,

        "pending_id": pending.pending_id,

        "original_filename": (

            pending.original_filename

        ),

        "safe_filename": (

            pending.safe_filename

        ),

        "temp_path": pending.temp_path,

        "validation": {

            "extension": pending.extension,

            "mime_type": pending.mime_type,

            "file_size": pending.file_size,

        },

        "extraction": {

            "method": (

                pending.extraction_method

            ),

            "page_count": (

                pending.page_count

            ),

            "text": (

                pending.extracted_text

                or ""

            ),

        },

        "classification": {

            "domain": pending.domain,

            "document_type": (

                pending.classified_document_type

            ),

            "confidence": (

                pending.classification_confidence

            ),

            "reason": (

                pending.classification_reason

            ),

        },

        "security": {

            "prompt_injection_detected": bool(

                pending.prompt_injection_detected

            ),

        },

        "duplicate_fingerprints": {

            "sha256": pending.sha256,

            "normalized_text_hash": (

                pending.normalized_text_hash

            ),

            "visual_hashes": visual_hashes,

        },

        "review_reasons": review_reasons,

    }





def persist_document_review(

    state: Dict[str, Any],

    review_payload: Dict[str, Any],

) -> Dict[str, Any]:

    """Persist the exact proposal shown to the authenticated user."""



    (

        user_id,

        conversation_id,

        session_id,

    ) = _workflow_scope(state)



    pending_document_id = state.get(

        "pending_document_id"

    )



    if not pending_document_id:

        raise DocumentWorkflowError(

            "Cannot persist document review without "

            "a pending document."

        )



    document_proposal = (

        state.get("document_proposal")

        or {}

    )



    if not isinstance(

        document_proposal,

        dict,

    ):

        raise DocumentWorkflowError(

            "Document proposal has an invalid shape."

        )



    if not isinstance(

        review_payload,

        dict,

    ):

        raise DocumentWorkflowError(

            "Document review payload has an invalid shape."

        )



    check_results = list(

        state.get(

            "document_check_results"

        )

        or []

    )



    edit_target_id = state.get(

        "editing_workflow_proposal_id"

    )



    session = SessionLocal()



    try:

        pending = _find_owned_pending_upload(

            session,

            pending_id=(

                pending_document_id

            ),

            user_id=user_id,

        )



        if pending is None:

            raise DocumentWorkflowError(

                "The staged document is unavailable."

            )



        original_user_request = str(

            state.get("message")

            or ""

        )



        row: Optional[

            WorkflowProposal

        ] = None



        if edit_target_id:

            row = _find_pending_row(

                session,

                state,

                str(edit_target_id),

            )



            if row is None:

                raise DocumentWorkflowError(

                    "The document review can no "

                    "longer be edited."

                )



            if (

                str(

                    row.pending_document_id

                    or ""

                )

                != str(

                    pending.pending_id

                )

            ):

                raise DocumentWorkflowError(

                    "The document review does not "

                    "match the staged document."

                )



            old_payload = _load_payload(

                row

            )



            original_user_request = str(

                old_payload.get(

                    "original_user_request"

                )

                or original_user_request

            )



        payload: Dict[str, Any] = {

            "kind": "document",

            "pending_document_id": str(

                pending.pending_id

            ),

            "original_user_request": (

                original_user_request

            ),

            "document_proposal": (

                document_proposal

            ),

            "document_check_results": (

                check_results

            ),

            "review_payload": (

                review_payload

            ),

            "requires_clarification": bool(

                document_proposal.get(

                    "clarification_required"

                )

            ),

            "edit_metadata": {

                "edited_from_proposal_id": (

                    str(edit_target_id)

                    if edit_target_id

                    else None

                ),

                "previous_revision": (

                    int(row.revision)

                    if row is not None

                    else None

                ),

                "user_edit_request": (

                    str(

                        state.get(

                            "document_edit_request"

                        )

                        or ""

                    )

                    if edit_target_id

                    else None

                ),

            },

        }



        payload_json = _canonical_json(

            payload

        )

        args_hash = _payload_hash(

            payload

        )

        now = utcnow()

        expires_at = (

            now

            + timedelta(

                hours=(

                    DOCUMENT_PROPOSAL_TTL_HOURS

                )

            )

        )



        if row is not None:

            row.revision = (

                int(row.revision or 0)

                + 1

            )

            row.payload_json = (

                payload_json

            )

            row.args_hash = args_hash

            row.pending_document_id = str(

                pending.pending_id

            )

            row.status = (

                "AWAITING_REVIEW"

            )

            row.approved_by = None

            row.approved_at = None

            row.updated_at = now

            row.expires_at = expires_at

            row.last_error = None



            pending.status = "needs_review"



            session.commit()

            session.refresh(row)



            return {

                "proposal_id": str(

                    row.proposal_id

                ),

                "revision": int(

                    row.revision

                ),

                "args_hash": (

                    row.args_hash

                ),

            }



        # Supersede unresolved reviews only inside the exact

        # authenticated user/conversation/session scope.

        existing_query = (

            session.query(

                WorkflowProposal

            )

            .filter(

                WorkflowProposal.user_id

                == user_id,

                WorkflowProposal.conversation_id

                == conversation_id,

                WorkflowProposal.session_id

                == session_id,

                WorkflowProposal.kind

                == "document",

                WorkflowProposal.status

                == "AWAITING_REVIEW",

            )

        )



        superseded_pending_ids = []



        for existing in (

            existing_query.all()

        ):

            existing.status = "CANCELLED"

            existing.updated_at = now

            existing.last_error = (

                "Superseded by a newer "

                "review request."

            )



            old_pending_id = str(

                existing.pending_document_id

                or ""

            ).strip()



            if (

                old_pending_id

                and old_pending_id

                != str(pending.pending_id)

            ):

                old_pending = (

                    _find_owned_pending_upload(

                        session,

                        pending_id=(

                            old_pending_id

                        ),

                        user_id=user_id,

                    )

                )



                if (

                    old_pending is not None

                    and old_pending.status

                    in (

                        "staged",

                        "needs_review",

                    )

                ):

                    old_pending.status = (

                        "superseded"

                    )

                    superseded_pending_ids.append(

                        old_pending_id

                    )



        row = WorkflowProposal(

            session_id=session_id,

            conversation_id=(

                conversation_id

            ),

            user_id=user_id,

            kind="document",

            revision=1,

            payload_json=payload_json,

            args_hash=args_hash,

            pending_document_id=str(

                pending.pending_id

            ),

            status="AWAITING_REVIEW",

            expires_at=expires_at,

        )



        pending.status = "needs_review"



        session.add(row)

        session.commit()

        session.refresh(row)



        for old_pending_id in (

            superseded_pending_ids

        ):

            cleanup_terminal_pending_upload(

                old_pending_id

            )



        return {

            "proposal_id": str(

                row.proposal_id

            ),

            "revision": int(

                row.revision

            ),

            "args_hash": row.args_hash,

        }



    except DocumentWorkflowError:

        session.rollback()

        raise



    except Exception as exc:

        session.rollback()



        raise DocumentWorkflowError(

            "Unable to persist the "

            "document review."

        ) from exc



    finally:

        session.close()


def approve_document_interpretation(
    state: Dict[str, Any],
    *,
    store_document: bool,
) -> Dict[str, Any]:
    """Approve interpretation/storage only, without authorizing actions.

    This is the first gate of the separated document workflow.  The explicit
    storage choice is added to the exact payload before its approval hash is
    written.  Derived actions remain inert until a separate
    ``document_action`` proposal is approved.
    """

    if not isinstance(store_document, bool):
        raise DocumentWorkflowError(
            "Choose whether the original document should be saved."
        )

    user_id, conversation_id, session_id = _workflow_scope(state)
    session = SessionLocal()

    try:
        selected_proposal_id = _selected_proposal_id(state)
        row = _find_pending_row(
            session,
            state,
            selected_proposal_id,
        )

        if row is None:
            already_handled = _already_approved_result(
                _find_exact_document_row(
                    session,
                    state,
                    selected_proposal_id,
                )
            )
            if already_handled is not None:
                return already_handled
            raise DocumentWorkflowError(
                "There is no pending document interpretation to verify."
            )

        payload = _load_payload(row)
        if payload.get("requires_clarification"):
            raise DocumentWorkflowError(
                "This document interpretation still has unresolved "
                "information. Edit it before verifying it."
            )

        pending = _find_owned_pending_upload(
            session,
            pending_id=row.pending_document_id,
            user_id=user_id,
        )
        if pending is None:
            raise DocumentWorkflowError(
                "The staged document is unavailable."
            )

        pending_id = str(pending.pending_id)
        if str(payload.get("pending_document_id") or "") != pending_id:
            raise DocumentWorkflowError(
                "The saved interpretation does not match the staged document."
            )

        proposal_id = str(row.proposal_id)
        revision = int(row.revision or 1)
        previous_hash = str(row.args_hash)
        now = utcnow()

        approved_payload = dict(payload)
        approved_payload["phase"] = "interpretation_verified"
        approved_payload["document_decision"] = {
            "interpretation_verified": True,
            "store_document": store_document,
        }
        approved_json = _canonical_json(approved_payload)
        approved_hash = _payload_hash(approved_payload)

        changed_workflow = session.query(WorkflowProposal).filter(
            WorkflowProposal.proposal_id == proposal_id,
            WorkflowProposal.user_id == user_id,
            WorkflowProposal.conversation_id == conversation_id,
            WorkflowProposal.session_id == session_id,
            WorkflowProposal.kind == DOCUMENT_REVIEW_KIND,
            WorkflowProposal.status == "AWAITING_REVIEW",
            WorkflowProposal.revision == revision,
            WorkflowProposal.args_hash == previous_hash,
            WorkflowProposal.pending_document_id == pending_id,
        ).update(
            {
                WorkflowProposal.payload_json: approved_json,
                WorkflowProposal.args_hash: approved_hash,
                WorkflowProposal.status: "APPROVED",
                WorkflowProposal.approved_by: user_id,
                WorkflowProposal.approved_at: now,
                WorkflowProposal.updated_at: now,
                WorkflowProposal.last_error: None,
            },
            synchronize_session=False,
        )

        if changed_workflow != 1:
            session.rollback()
            already_handled = _already_approved_result(
                _find_exact_document_row(
                    session,
                    state,
                    proposal_id,
                )
            )
            if already_handled is not None:
                return already_handled
            raise DocumentWorkflowError(
                "The document interpretation changed before verification. "
                "Reload the current review."
            )

        changed_pending = session.query(PendingDocumentUpload).filter(
            PendingDocumentUpload.pending_id == pending_id,
            PendingDocumentUpload.uploaded_by == user_id,
            PendingDocumentUpload.status.in_(("staged", "needs_review")),
        ).update(
            {
                PendingDocumentUpload.status: (
                    "verified_pending_finalization"
                )
            },
            synchronize_session=False,
        )

        if changed_pending != 1:
            session.rollback()
            raise DocumentWorkflowError(
                "The staged document changed before verification. "
                "Reload the current review."
            )

        session.commit()
        return {
            "proposal_id": proposal_id,
            "revision": revision,
            "args_hash": approved_hash,
            "pending_document_id": pending_id,
            "store_document": store_document,
            "payload": approved_payload,
            "status": "APPROVED",
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to verify the document interpretation safely."
        ) from exc
    finally:
        session.close()


def persist_document_action_review(
    state: Dict[str, Any],
    *,
    source_proposal_id: str,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the second, independently approvable action proposal.

    The source interpretation must already be completed by the storage
    finalizer.  The action proposal pins the source revision and approved hash,
    preventing later edits from changing what the user authorizes.
    """

    user_id, conversation_id, session_id = _workflow_scope(state)
    source_id = str(source_proposal_id or "").strip()
    if not source_id:
        raise DocumentWorkflowError(
            "The verified document interpretation is unavailable."
        )

    normalized_document_id = str(document_id or "").strip() or None
    session = SessionLocal()

    try:
        source = session.query(WorkflowProposal).filter(
            WorkflowProposal.proposal_id == source_id,
            WorkflowProposal.user_id == user_id,
            WorkflowProposal.conversation_id == conversation_id,
            WorkflowProposal.session_id == session_id,
            WorkflowProposal.kind == DOCUMENT_REVIEW_KIND,
            WorkflowProposal.status == "COMPLETED",
            WorkflowProposal.approved_by == user_id,
        ).first()
        if source is None:
            raise DocumentWorkflowError(
                "The verified document interpretation is unavailable."
            )

        source_payload = _load_payload(source)
        decision = source_payload.get("document_decision") or {}
        if not isinstance(decision, dict) or not decision.get(
            "interpretation_verified"
        ):
            raise DocumentWorkflowError(
                "The document interpretation was not verified."
            )

        store_document = decision.get("store_document")
        if not isinstance(store_document, bool):
            raise DocumentWorkflowError(
                "The document storage choice is unavailable."
            )
        if store_document and normalized_document_id is None:
            raise DocumentWorkflowError(
                "The approved document has not been stored safely."
            )
        if not store_document and normalized_document_id is not None:
            raise DocumentWorkflowError(
                "An unstored document cannot reference a permanent record."
            )

        pending_id = str(source.pending_document_id or "").strip()
        if not pending_id or str(
            source_payload.get("pending_document_id") or ""
        ).strip() != pending_id:
            raise DocumentWorkflowError(
                "The verified interpretation has an invalid staged "
                "document reference."
            )

        pending = _find_owned_pending_upload(
            session,
            pending_id=pending_id,
            user_id=user_id,
        )
        if pending is None:
            raise DocumentWorkflowError(
                "The staged document is unavailable."
            )

        document_proposal = source_payload.get("document_proposal") or {}
        if not isinstance(document_proposal, dict):
            raise DocumentWorkflowError(
                "The verified document proposal has an invalid shape."
            )
        actions = [
            dict(action)
            for action in (document_proposal.get("actions") or [])
            if isinstance(action, dict) and not action.get("blocked")
        ]

        if not actions:
            pending.status = "completed"
            session.commit()
            cleanup_terminal_pending_upload(pending_id)
            return {
                "created": False,
                "source_proposal_id": source_id,
                "pending_document_id": pending_id,
                "document_id": normalized_document_id,
                "store_document": store_document,
                "actions": [],
            }

        action_document_proposal = dict(document_proposal)
        action_document_proposal["actions"] = actions
        payload = {
            "kind": DOCUMENT_ACTION_KIND,
            "phase": "action_review",
            "pending_document_id": pending_id,
            "document_id": normalized_document_id,
            "store_document": store_document,
            "source_proposal_id": source_id,
            "source_revision": int(source.revision or 1),
            "source_args_hash": str(source.args_hash),
            "original_user_request": str(
                source_payload.get("original_user_request") or ""
            ),
            "document_proposal": action_document_proposal,
            "document_check_results": list(
                source_payload.get("document_check_results") or []
            ),
        }
        payload_json = _canonical_json(payload)
        args_hash = _payload_hash(payload)
        now = utcnow()
        expires_at = now + timedelta(hours=DOCUMENT_PROPOSAL_TTL_HOURS)

        existing = session.query(WorkflowProposal).filter(
            WorkflowProposal.user_id == user_id,
            WorkflowProposal.conversation_id == conversation_id,
            WorkflowProposal.session_id == session_id,
            WorkflowProposal.kind == DOCUMENT_ACTION_KIND,
            WorkflowProposal.pending_document_id == pending_id,
            WorkflowProposal.status == "AWAITING_REVIEW",
        ).first()
        if existing is not None:
            existing_payload = _load_payload(existing)
            if (
                existing.args_hash == args_hash
                and existing_payload == payload
            ):
                return {
                    "created": True,
                    "already_exists": True,
                    "proposal_id": str(existing.proposal_id),
                    "revision": int(existing.revision or 1),
                    "args_hash": str(existing.args_hash),
                    "pending_document_id": pending_id,
                    "document_id": normalized_document_id,
                    "store_document": store_document,
                    "payload": existing_payload,
                }
            existing.status = "CANCELLED"
            existing.updated_at = now
            existing.last_error = (
                "Superseded by a newer derived-action review."
            )

        row = WorkflowProposal(
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            kind=DOCUMENT_ACTION_KIND,
            revision=1,
            payload_json=payload_json,
            args_hash=args_hash,
            pending_document_id=pending_id,
            status="AWAITING_REVIEW",
            expires_at=expires_at,
        )
        pending.status = "awaiting_action_review"
        session.add(row)
        session.commit()
        session.refresh(row)

        return {
            "created": True,
            "already_exists": False,
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "args_hash": str(row.args_hash),
            "pending_document_id": pending_id,
            "document_id": normalized_document_id,
            "store_document": store_document,
            "payload": payload,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to create the derived-action review safely."
        ) from exc
    finally:
        session.close()


def _find_pending_document_action_row(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str] = None,
) -> Optional[WorkflowProposal]:
    """Find one pending derived-action review in the exact owner scope."""

    user_id, conversation_id, session_id = _workflow_scope(state)
    query = session.query(WorkflowProposal).filter(
        WorkflowProposal.user_id == user_id,
        WorkflowProposal.conversation_id == conversation_id,
        WorkflowProposal.session_id == session_id,
        WorkflowProposal.kind == DOCUMENT_ACTION_KIND,
        WorkflowProposal.status == "AWAITING_REVIEW",
    )
    if proposal_id:
        query = query.filter(
            WorkflowProposal.proposal_id == str(proposal_id)
        )
    row = query.order_by(
        desc(WorkflowProposal.updated_at),
        desc(WorkflowProposal.created_at),
    ).first()
    if row is None:
        return None
    if _mark_expired_if_needed(session, row):
        return None
    return row


def _find_exact_document_action_row(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str],
) -> Optional[WorkflowProposal]:
    if not proposal_id:
        return None
    user_id, conversation_id, session_id = _workflow_scope(state)
    return session.query(WorkflowProposal).filter(
        WorkflowProposal.proposal_id == str(proposal_id),
        WorkflowProposal.user_id == user_id,
        WorkflowProposal.conversation_id == conversation_id,
        WorkflowProposal.session_id == session_id,
        WorkflowProposal.kind == DOCUMENT_ACTION_KIND,
    ).first()


def _find_exact_document_family_row(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str],
) -> Optional[WorkflowProposal]:
    """Load an interpretation or derived-action row in the exact scope."""

    if not proposal_id:
        return None
    user_id, conversation_id, session_id = _workflow_scope(state)
    return session.query(WorkflowProposal).filter(
        WorkflowProposal.proposal_id == str(proposal_id),
        WorkflowProposal.user_id == user_id,
        WorkflowProposal.conversation_id == conversation_id,
        WorkflowProposal.session_id == session_id,
        WorkflowProposal.kind.in_(
            (DOCUMENT_REVIEW_KIND, DOCUMENT_ACTION_KIND)
        ),
    ).first()


def load_pending_document_action_review(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Load the current exact derived-action review."""

    _workflow_scope(state)
    session = SessionLocal()
    try:
        row = _find_pending_document_action_row(
            session,
            state,
            _selected_proposal_id(state),
        )
        if row is None:
            return None
        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "args_hash": str(row.args_hash),
            "pending_document_id": row.pending_document_id,
            "payload": _load_payload(row),
        }
    finally:
        session.close()


def approve_document_action_review(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Atomically approve only the exact derived actions shown to the user."""

    user_id, conversation_id, session_id = _workflow_scope(state)
    session = SessionLocal()
    try:
        selected_proposal_id = _selected_proposal_id(state)
        row = _find_pending_document_action_row(
            session,
            state,
            selected_proposal_id,
        )
        if row is None:
            already = _already_approved_result(
                _find_exact_document_action_row(
                    session,
                    state,
                    selected_proposal_id,
                )
            )
            if already is not None:
                return already
            raise DocumentWorkflowError(
                "There are no derived document actions waiting for approval."
            )

        payload = _load_payload(row)
        pending_id = str(row.pending_document_id or "").strip()
        if (
            payload.get("phase") != "action_review"
            or str(payload.get("pending_document_id") or "").strip()
            != pending_id
        ):
            raise DocumentWorkflowError(
                "The derived-action proposal is invalid."
            )
        actions = (
            (payload.get("document_proposal") or {}).get("actions") or []
        )
        if not any(
            isinstance(action, dict) and not action.get("blocked")
            for action in actions
        ):
            raise DocumentWorkflowError(
                "There are no executable derived actions to approve."
            )

        pending = _find_owned_pending_upload(
            session,
            pending_id=pending_id,
            user_id=user_id,
        )
        if pending is None:
            raise DocumentWorkflowError(
                "The staged document is unavailable."
            )

        now = utcnow()
        proposal_id = str(row.proposal_id)
        revision = int(row.revision or 1)
        args_hash = str(row.args_hash)
        changed = session.query(WorkflowProposal).filter(
            WorkflowProposal.proposal_id == proposal_id,
            WorkflowProposal.user_id == user_id,
            WorkflowProposal.conversation_id == conversation_id,
            WorkflowProposal.session_id == session_id,
            WorkflowProposal.kind == DOCUMENT_ACTION_KIND,
            WorkflowProposal.status == "AWAITING_REVIEW",
            WorkflowProposal.revision == revision,
            WorkflowProposal.args_hash == args_hash,
            WorkflowProposal.pending_document_id == pending_id,
        ).update(
            {
                WorkflowProposal.status: "APPROVED",
                WorkflowProposal.approved_by: user_id,
                WorkflowProposal.approved_at: now,
                WorkflowProposal.updated_at: now,
                WorkflowProposal.last_error: None,
            },
            synchronize_session=False,
        )
        if changed != 1:
            session.rollback()
            already = _already_approved_result(
                _find_exact_document_action_row(
                    session,
                    state,
                    proposal_id,
                )
            )
            if already is not None:
                return already
            raise DocumentWorkflowError(
                "The derived-action review changed before approval. "
                "Reload the current review."
            )

        changed_pending = session.query(PendingDocumentUpload).filter(
            PendingDocumentUpload.pending_id == pending_id,
            PendingDocumentUpload.uploaded_by == user_id,
            PendingDocumentUpload.status == "awaiting_action_review",
        ).update(
            {
                PendingDocumentUpload.status: "approved_pending_execution"
            },
            synchronize_session=False,
        )
        if changed_pending != 1:
            session.rollback()
            raise DocumentWorkflowError(
                "The staged document changed before action approval."
            )

        session.commit()
        return {
            "proposal_id": proposal_id,
            "revision": revision,
            "args_hash": args_hash,
            "pending_document_id": pending_id,
            "payload": payload,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to approve the derived document actions safely."
        ) from exc
    finally:
        session.close()


def reject_document_action_review(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Reject derived actions without undoing document verification/storage."""

    user_id, conversation_id, session_id = _workflow_scope(state)
    session = SessionLocal()
    cleanup_id: Optional[str] = None
    try:
        row = _find_pending_document_action_row(
            session,
            state,
            _selected_proposal_id(state),
        )
        if row is None:
            raise DocumentWorkflowError(
                "There are no derived document actions waiting for rejection."
            )
        payload = _load_payload(row)
        pending_id = str(row.pending_document_id or "").strip()
        if str(payload.get("pending_document_id") or "").strip() != pending_id:
            raise DocumentWorkflowError(
                "The derived-action proposal is invalid."
            )

        now = utcnow()
        proposal_id = str(row.proposal_id)
        revision = int(row.revision or 1)
        args_hash = str(row.args_hash)
        changed = session.query(WorkflowProposal).filter(
            WorkflowProposal.proposal_id == proposal_id,
            WorkflowProposal.user_id == user_id,
            WorkflowProposal.conversation_id == conversation_id,
            WorkflowProposal.session_id == session_id,
            WorkflowProposal.kind == DOCUMENT_ACTION_KIND,
            WorkflowProposal.status == "AWAITING_REVIEW",
            WorkflowProposal.revision == revision,
            WorkflowProposal.args_hash == args_hash,
            WorkflowProposal.pending_document_id == pending_id,
        ).update(
            {
                WorkflowProposal.status: "REJECTED",
                WorkflowProposal.approved_by: None,
                WorkflowProposal.approved_at: None,
                WorkflowProposal.updated_at: now,
                WorkflowProposal.last_error: None,
            },
            synchronize_session=False,
        )
        if changed != 1:
            session.rollback()
            raise DocumentWorkflowError(
                "The derived-action review changed before rejection."
            )

        pending = _find_owned_pending_upload(
            session,
            pending_id=pending_id,
            user_id=user_id,
        )
        if pending is None:
            session.rollback()
            raise DocumentWorkflowError(
                "The staged document is unavailable."
            )
        pending.status = "completed"
        session.commit()
        cleanup_id = pending_id
        cleanup_terminal_pending_upload(cleanup_id)

        return {
            "proposal_id": proposal_id,
            "revision": revision,
            "pending_document_id": pending_id,
            "document_id": payload.get("document_id"),
            "store_document": bool(payload.get("store_document")),
            "payload": payload,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to reject the derived document actions safely."
        ) from exc
    finally:
        session.close()





def load_pending_document_review(

    state: Dict[str, Any],

) -> Optional[Dict[str, Any]]:

    """Load the user's current pending document review."""



    # Validate before opening/querying the workflow store.

    _workflow_scope(state)



    session = SessionLocal()



    try:

        row = _find_pending_row(

            session,

            state,

            _selected_proposal_id(

                state

            ),

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

                row.revision or 1

            ),

            "args_hash": row.args_hash,

            "payload": payload,

            "pending_document_id": (

                row.pending_document_id

            ),

        }



    finally:

        session.close()





def load_document_edit_context(

    state: Dict[str, Any],

    proposal_id: str,

) -> Dict[str, Any]:

    """Reconstruct trusted edit context inside the owned scope."""



    (

        user_id,

        _conversation_id,

        _session_id,

    ) = _workflow_scope(state)



    session = SessionLocal()



    try:

        row = _find_pending_row(

            session,

            state,

            proposal_id,

        )



        if row is None:

            raise DocumentWorkflowError(

                "The document review can no "

                "longer be edited."

            )



        payload = _load_payload(

            row

        )



        pending_document_id = (

            row.pending_document_id

            or payload.get(

                "pending_document_id"

            )

        )



        pending = (

            _find_owned_pending_upload(

                session,

                pending_id=(

                    pending_document_id

                ),

                user_id=user_id,

            )

        )



        if pending is None:

            raise DocumentWorkflowError(

                "The staged document for this "

                "review is unavailable."

            )



        if (

            str(

                payload.get(

                    "pending_document_id"

                )

                or ""

            )

            != str(

                pending.pending_id

            )

        ):

            raise DocumentWorkflowError(

                "The saved review does not match "

                "the staged document."

            )



        return {

            "proposal_id": str(

                row.proposal_id

            ),

            "revision": int(

                row.revision or 1

            ),

            "pending_document_id": str(

                pending.pending_id

            ),

            "original_user_request": str(

                payload.get(

                    "original_user_request"

                )

                or ""

            ),

            "document_proposal": dict(

                payload.get(

                    "document_proposal"

                )

                or {}

            ),

            "document_check_results": list(

                payload.get(

                    "document_check_results"

                )

                or []

            ),

            "ingestion_result": (

                _pending_upload_to_ingestion(

                    pending

                )

            ),

        }



    finally:

        session.close()





def approve_document_review(

    state: Dict[str, Any],

) -> Dict[str, Any]:

    """Atomically approve the exact current owned revision.



    The compare-and-set update succeeds only while the same proposal

    revision, payload hash, owner, conversation, session, and pending

    status remain unchanged.

    """



    (

        user_id,

        conversation_id,

        session_id,

    ) = _workflow_scope(state)



    session = SessionLocal()



    try:

        selected_proposal_id = (

            _selected_proposal_id(

                state

            )

        )

        row = _find_pending_row(

            session,

            state,

            selected_proposal_id,

        )



        if row is None:

            already_handled = (

                _already_approved_result(

                    _find_exact_document_row(

                        session,

                        state,

                        selected_proposal_id,

                    )

                )

            )

            if already_handled is not None:

                return already_handled

            raise DocumentWorkflowError(

                "There is no pending document "

                "review to approve."

            )



        payload = _load_payload(

            row

        )



        if payload.get(

            "requires_clarification"

        ):

            raise DocumentWorkflowError(

                "This document review still has "

                "unresolved information. Edit the "

                "proposal before approving it."

            )



        proposal = (

            payload.get(

                "document_proposal"

            )

            or {}

        )

        actions = list(

            proposal.get("actions")

            or []

        )



        ready_actions = [

            action

            for action in actions

            if (

                isinstance(action, dict)

                and not action.get("blocked")

            )

        ]



        if not ready_actions:

            raise DocumentWorkflowError(

                "This document review has no "

                "executable ready actions."

            )



        pending = (

            _find_owned_pending_upload(

                session,

                pending_id=(

                    row.pending_document_id

                ),

                user_id=user_id,

            )

        )



        if pending is None:

            raise DocumentWorkflowError(

                "The staged document is unavailable."

            )



        payload_pending_id = str(

            payload.get(

                "pending_document_id"

            )

            or ""

        )



        if (

            payload_pending_id

            != str(pending.pending_id)

        ):

            raise DocumentWorkflowError(

                "The saved review does not match "

                "the staged document."

            )



        proposal_id = str(

            row.proposal_id

        )

        expected_revision = int(

            row.revision or 1

        )

        expected_hash = str(

            row.args_hash

        )

        pending_id = str(

            pending.pending_id

        )

        now = utcnow()



        # Compare-and-set: only one request can change this

        # exact awaiting-review revision to APPROVED.

        changed_workflows = (

            session.query(

                WorkflowProposal

            )

            .filter(

                WorkflowProposal.proposal_id

                == proposal_id,

                WorkflowProposal.user_id

                == user_id,

                WorkflowProposal.conversation_id

                == conversation_id,

                WorkflowProposal.session_id

                == session_id,

                WorkflowProposal.kind

                == "document",

                WorkflowProposal.status

                == "AWAITING_REVIEW",

                WorkflowProposal.revision

                == expected_revision,

                WorkflowProposal.args_hash

                == expected_hash,

                WorkflowProposal.pending_document_id

                == pending_id,

            )

            .update(

                {

                    WorkflowProposal.status: (

                        "APPROVED"

                    ),

                    WorkflowProposal.approved_by: (

                        user_id

                    ),

                    WorkflowProposal.approved_at: (

                        now

                    ),

                    WorkflowProposal.updated_at: (

                        now

                    ),

                    WorkflowProposal.last_error: (

                        None

                    ),

                },

                synchronize_session=False,

            )

        )



        if changed_workflows != 1:

            session.rollback()

            already_handled = (

                _already_approved_result(

                    _find_exact_document_row(

                        session,

                        state,

                        proposal_id,

                    )

                )

            )

            if already_handled is not None:

                return already_handled



            raise DocumentWorkflowError(

                "The document review changed before "

                "approval. Reload the current review."

            )



        # Keep pending-upload state in the same transaction.

        changed_pending = (

            session.query(

                PendingDocumentUpload

            )

            .filter(

                PendingDocumentUpload.pending_id

                == pending_id,

                PendingDocumentUpload.uploaded_by

                == user_id,

                PendingDocumentUpload.status.in_(

                    (

                        "staged",

                        "needs_review",

                    )

                ),

            )

            .update(

                {

                    PendingDocumentUpload.status: (

                        "approved_pending_execution"

                    )

                },

                synchronize_session=False,

            )

        )



        if changed_pending != 1:

            session.rollback()



            raise DocumentWorkflowError(

                "The staged document changed before "

                "approval. Reload the current review."

            )



        session.commit()



        return {

            "proposal_id": proposal_id,

            "revision": expected_revision,

            "args_hash": expected_hash,

            "payload": payload,

        }



    except DocumentWorkflowError:

        session.rollback()

        raise



    except Exception as exc:

        session.rollback()



        raise DocumentWorkflowError(

            "Unable to approve the "

            "document review safely."

        ) from exc



    finally:

        session.close()





def retry_failed_document_review(

    state: Dict[str, Any],

) -> Dict[str, Any]:

    """Atomically re-approve one recent failed document revision."""

    user_id, conversation_id, session_id = _workflow_scope(state)

    selected_proposal_id = _selected_proposal_id(state)

    session = SessionLocal()

    try:

        query = session.query(WorkflowProposal).filter(

            WorkflowProposal.user_id == user_id,

            WorkflowProposal.conversation_id == conversation_id,

            WorkflowProposal.session_id == session_id,

            WorkflowProposal.kind.in_(

                (DOCUMENT_REVIEW_KIND, DOCUMENT_ACTION_KIND)

            ),

            WorkflowProposal.status == "FAILED",

        )

        if selected_proposal_id:

            query = query.filter(

                WorkflowProposal.proposal_id == selected_proposal_id

            )

        row = query.order_by(

            desc(WorkflowProposal.updated_at),

            desc(WorkflowProposal.created_at),

        ).first()

        if row is None:

            if selected_proposal_id:

                already_handled = _already_approved_result(

                    _find_exact_document_family_row(

                        session,

                        state,

                        selected_proposal_id,

                    )

                )

                if already_handled is not None:

                    return already_handled

            raise DocumentWorkflowError(

                "There is no failed document execution available to retry."

            )

        now = utcnow()

        retry_anchor = (

            row.approved_at

            or row.created_at

        )

        if _is_older_than(

            retry_anchor,

            now,

            FAILED_DOCUMENT_RETRY_MAX_AGE_HOURS,

        ):

            raise DocumentWorkflowError(

                "The failed document execution is too old for an implicit "

                "retry. Review and approve it again."

            )

        payload = _load_payload(row)

        pending_id = str(row.pending_document_id or "").strip()

        payload_pending_id = str(

            payload.get("pending_document_id") or ""

        ).strip()

        if not pending_id or pending_id != payload_pending_id:

            raise DocumentWorkflowError(

                "The failed document proposal has an invalid staged "

                "document reference."

            )

        pending = _find_owned_pending_upload(

            session,

            pending_id=pending_id,

            user_id=user_id,

        )

        if pending is None:

            raise DocumentWorkflowError(

                "The staged document is unavailable."

            )

        proposal_id = str(row.proposal_id)

        revision = int(row.revision or 1)

        args_hash = str(row.args_hash)

        workflow_kind = str(row.kind or "")

        if workflow_kind not in {

            DOCUMENT_REVIEW_KIND,

            DOCUMENT_ACTION_KIND,

        }:

            raise DocumentWorkflowError(

                "The failed document workflow has an invalid kind."

            )

        changed_workflow = session.query(WorkflowProposal).filter(

            WorkflowProposal.proposal_id == proposal_id,

            WorkflowProposal.user_id == user_id,

            WorkflowProposal.conversation_id == conversation_id,

            WorkflowProposal.session_id == session_id,

            WorkflowProposal.kind == workflow_kind,

            WorkflowProposal.status == "FAILED",

            WorkflowProposal.revision == revision,

            WorkflowProposal.args_hash == args_hash,

            WorkflowProposal.pending_document_id == pending_id,

        ).update(

            {

                WorkflowProposal.status: "APPROVED",

                WorkflowProposal.approved_by: user_id,

                WorkflowProposal.updated_at: now,

                WorkflowProposal.last_error: None,

            },

            synchronize_session=False,

        )

        if changed_workflow != 1:

            session.rollback()

            already_handled = _already_approved_result(

                _find_exact_document_family_row(

                    session,

                    state,

                    proposal_id,

                )

            )

            if already_handled is not None:

                return already_handled

            raise DocumentWorkflowError(

                "The failed document execution changed before retry."

            )

        changed_pending = session.query(PendingDocumentUpload).filter(

            PendingDocumentUpload.pending_id == pending_id,

            PendingDocumentUpload.uploaded_by == user_id,

            PendingDocumentUpload.status == "execution_failed",

        ).update(

            {

                PendingDocumentUpload.status: (

                    "approved_pending_execution"

                )

            },

            synchronize_session=False,

        )

        if changed_pending != 1:

            session.rollback()

            raise DocumentWorkflowError(

                "The staged document is not available for retry."

            )

        session.commit()

        return {

            "proposal_id": proposal_id,

            "revision": revision,

            "args_hash": args_hash,

            "payload": payload,

            "pending_document_id": pending_id,

            "status": "APPROVED",

            "kind": workflow_kind,

            "retried": True,

        }

    except DocumentWorkflowError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise DocumentWorkflowError(

            "Unable to retry the failed document execution safely."

        ) from exc

    finally:

        session.close()



def reject_document_review(

    state: Dict[str, Any],

) -> Dict[str, Any]:

    """Atomically reject the exact current owned revision."""



    (

        user_id,

        conversation_id,

        session_id,

    ) = _workflow_scope(state)



    session = SessionLocal()

    pending_cleanup_id: Optional[str] = None



    try:

        row = _find_pending_row(

            session,

            state,

            _selected_proposal_id(

                state

            ),

        )



        if row is None:

            raise DocumentWorkflowError(

                "There is no pending document "

                "review to reject."

            )



        payload = _load_payload(

            row

        )



        pending = (

            _find_owned_pending_upload(

                session,

                pending_id=(

                    row.pending_document_id

                ),

                user_id=user_id,

            )

        )



        if pending is None:

            raise DocumentWorkflowError(

                "The staged document is unavailable."

            )



        payload_pending_id = str(

            payload.get(

                "pending_document_id"

            )

            or ""

        )



        if (

            payload_pending_id

            != str(pending.pending_id)

        ):

            raise DocumentWorkflowError(

                "The saved review does not match "

                "the staged document."

            )



        proposal_id = str(

            row.proposal_id

        )

        expected_revision = int(

            row.revision or 1

        )

        expected_hash = str(

            row.args_hash

        )

        pending_id = str(

            pending.pending_id

        )

        now = utcnow()



        # A concurrent approve, reject, edit, expiry, or

        # superseding request causes rowcount zero.

        changed_workflows = (

            session.query(

                WorkflowProposal

            )

            .filter(

                WorkflowProposal.proposal_id

                == proposal_id,

                WorkflowProposal.user_id

                == user_id,

                WorkflowProposal.conversation_id

                == conversation_id,

                WorkflowProposal.session_id

                == session_id,

                WorkflowProposal.kind

                == "document",

                WorkflowProposal.status

                == "AWAITING_REVIEW",

                WorkflowProposal.revision

                == expected_revision,

                WorkflowProposal.args_hash

                == expected_hash,

                WorkflowProposal.pending_document_id

                == pending_id,

            )

            .update(

                {

                    WorkflowProposal.status: (

                        "REJECTED"

                    ),

                    WorkflowProposal.approved_by: (

                        None

                    ),

                    WorkflowProposal.approved_at: (

                        None

                    ),

                    WorkflowProposal.updated_at: (

                        now

                    ),

                    WorkflowProposal.last_error: (

                        None

                    ),

                },

                synchronize_session=False,

            )

        )



        if changed_workflows != 1:

            session.rollback()



            raise DocumentWorkflowError(

                "The document review changed before "

                "rejection. Reload the current review."

            )



        changed_pending = (

            session.query(

                PendingDocumentUpload

            )

            .filter(

                PendingDocumentUpload.pending_id

                == pending_id,

                PendingDocumentUpload.uploaded_by

                == user_id,

                PendingDocumentUpload.status.in_(

                    (

                        "staged",

                        "needs_review",

                    )

                ),

            )

            .update(

                {

                    PendingDocumentUpload.status: (

                        "rejected_by_user"

                    )

                },

                synchronize_session=False,

            )

        )



        if changed_pending != 1:

            session.rollback()



            raise DocumentWorkflowError(

                "The staged document changed before "

                "rejection. Reload the current review."

            )



        session.commit()

        pending_cleanup_id = pending_id



        cleanup_terminal_pending_upload(

            pending_cleanup_id

        )



        return {

            "proposal_id": proposal_id,

            "revision": expected_revision,

            "payload": payload,

        }



    except DocumentWorkflowError:

        session.rollback()

        raise



    except Exception as exc:

        session.rollback()



        raise DocumentWorkflowError(

            "Unable to reject the "

            "document review safely."

        ) from exc



    finally:

        session.close()
