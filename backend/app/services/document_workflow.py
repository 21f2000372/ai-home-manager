"""Durable document-review workflow service for AI Home Manager.

Step 8A of the production refactor.

This module is deliberately application code, not an LLM node. It owns the
persistent document proposal shown to the user, revision/hash integrity,
approval/rejection state, and reconstruction of trusted server-side edit
context after a restart.

No document-derived domain mutation is executed here in Step 8A. Step 8B will
consume APPROVED document proposals through the execution ledger.

Compatibility target: Python 3.8+.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy import desc

from app.db.base import SessionLocal, utcnow
from app.models.documents import PendingDocumentUpload
from app.models.workflows import WorkflowProposal


DOCUMENT_PROPOSAL_TTL_HOURS = 24


class DocumentWorkflowError(RuntimeError):
    """Raised when durable document review cannot be handled safely."""


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
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _state_key(state: Dict[str, Any]) -> str:
    return str(
        state.get("session_id")
        or state.get("conversation_id")
        or ""
    ).strip()


def _load_payload(row: WorkflowProposal) -> Dict[str, Any]:
    try:
        payload = json.loads(row.payload_json)
    except Exception as exc:
        raise DocumentWorkflowError(
            "The saved document review is unreadable."
        ) from exc

    if not isinstance(payload, dict):
        raise DocumentWorkflowError(
            "The saved document review has an invalid payload."
        )

    if _payload_hash(payload) != row.args_hash:
        raise DocumentWorkflowError(
            "The saved document review failed its integrity check."
        )

    return payload


def _apply_user_scope(query, state: Dict[str, Any]):
    user_id = state.get("user_id")
    if user_id:
        query = query.filter(
            WorkflowProposal.user_id == str(user_id)
        )
    return query


def _mark_expired_if_needed(session, row: WorkflowProposal) -> bool:
    expires_at = row.expires_at
    if expires_at is None:
        return False

    now = utcnow()
    comparable_now = now

    if expires_at.tzinfo is None and comparable_now.tzinfo is not None:
        comparable_now = comparable_now.replace(tzinfo=None)

    if expires_at > comparable_now:
        return False

    row.status = "EXPIRED"
    row.updated_at = now
    row.last_error = "Document review expired before a user decision."
    session.commit()
    return True


def _find_pending_row(
    session,
    state: Dict[str, Any],
    proposal_id: Optional[str] = None,
) -> Optional[WorkflowProposal]:
    key = _state_key(state)
    if not key:
        return None

    query = session.query(WorkflowProposal).filter(
        WorkflowProposal.session_id == key,
        WorkflowProposal.kind == "document",
        WorkflowProposal.status == "AWAITING_REVIEW",
    )

    query = _apply_user_scope(query, state)

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


def _pending_upload_to_ingestion(
    pending: PendingDocumentUpload,
) -> Dict[str, Any]:
    try:
        review_reasons = json.loads(
            pending.review_reasons_json or "[]"
        )
    except Exception:
        review_reasons = []

    if not isinstance(review_reasons, list):
        review_reasons = []

    try:
        visual_hashes = json.loads(
            pending.visual_hashes_json or "[]"
        )
    except Exception:
        visual_hashes = []

    if not isinstance(visual_hashes, list):
        visual_hashes = []

    return {
        "success": True,
        "status": pending.status,
        "upload_id": pending.upload_id,
        "pending_id": pending.pending_id,
        "original_filename": pending.original_filename,
        "safe_filename": pending.safe_filename,
        "temp_path": pending.temp_path,
        "validation": {
            "extension": pending.extension,
            "mime_type": pending.mime_type,
            "file_size": pending.file_size,
        },
        "extraction": {
            "method": pending.extraction_method,
            "page_count": pending.page_count,
            "text": pending.extracted_text or "",
        },
        "classification": {
            "domain": pending.domain,
            "document_type": pending.classified_document_type,
            "confidence": pending.classification_confidence,
            "reason": pending.classification_reason,
        },
        "security": {
            "prompt_injection_detected": bool(
                pending.prompt_injection_detected
            ),
        },
        "duplicate_fingerprints": {
            "sha256": pending.sha256,
            "normalized_text_hash": pending.normalized_text_hash,
            "visual_hashes": visual_hashes,
        },
        "review_reasons": review_reasons,
    }


def persist_document_review(
    state: Dict[str, Any],
    review_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist the exact document proposal shown to the user.

    A new upload creates revision 1. A natural-language edit updates the same
    proposal row to revision N+1 and replaces the payload/hash atomically.
    """

    key = _state_key(state)
    if not key:
        raise DocumentWorkflowError(
            "Cannot persist document review without a session identifier."
        )

    pending_document_id = state.get("pending_document_id")
    if not pending_document_id:
        raise DocumentWorkflowError(
            "Cannot persist document review without a pending document."
        )

    document_proposal = state.get("document_proposal") or {}
    if not isinstance(document_proposal, dict):
        raise DocumentWorkflowError(
            "Document proposal has an invalid shape."
        )

    check_results = list(
        state.get("document_check_results") or []
    )

    edit_target_id = state.get("editing_workflow_proposal_id")
    user_id = state.get("user_id")

    session = SessionLocal()

    try:
        pending = session.query(PendingDocumentUpload).filter(
            PendingDocumentUpload.pending_id
            == str(pending_document_id)
        ).first()

        if pending is None:
            raise DocumentWorkflowError(
                "The staged document no longer exists."
            )

        if (
            user_id
            and pending.uploaded_by
            and str(pending.uploaded_by) != str(user_id)
        ):
            raise DocumentWorkflowError(
                "The staged document is not owned by the current user."
            )

        original_user_request = str(
            state.get("message") or ""
        )

        old_payload: Optional[Dict[str, Any]] = None
        row: Optional[WorkflowProposal] = None

        if edit_target_id:
            row = _find_pending_row(
                session,
                state,
                str(edit_target_id),
            )

            if row is None:
                raise DocumentWorkflowError(
                    "The document review can no longer be edited."
                )

            old_payload = _load_payload(row)
            original_user_request = str(
                old_payload.get("original_user_request")
                or original_user_request
            )

        payload: Dict[str, Any] = {
            "kind": "document",
            "pending_document_id": str(pending_document_id),
            "original_user_request": original_user_request,
            "document_proposal": document_proposal,
            "document_check_results": check_results,
            "review_payload": review_payload,
            "requires_clarification": bool(
                document_proposal.get("clarification_required")
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
                    str(state.get("document_edit_request") or "")
                    if edit_target_id
                    else None
                ),
            },
        }

        payload_json = _canonical_json(payload)
        args_hash = _payload_hash(payload)
        now = utcnow()
        expires_at = now + timedelta(
            hours=DOCUMENT_PROPOSAL_TTL_HOURS
        )

        if row is not None:
            row.revision = int(row.revision or 0) + 1
            row.payload_json = payload_json
            row.args_hash = args_hash
            row.pending_document_id = str(pending_document_id)
            row.status = "AWAITING_REVIEW"
            row.approved_by = None
            row.approved_at = None
            row.updated_at = now
            row.expires_at = expires_at
            row.last_error = None

            pending.status = "needs_review"

            session.commit()
            session.refresh(row)

            return {
                "proposal_id": str(row.proposal_id),
                "revision": int(row.revision),
                "args_hash": row.args_hash,
            }

        # One unresolved review at a time per session/user. This avoids an
        # ambiguous bare "yes" approving the wrong workflow.
        existing_query = session.query(WorkflowProposal).filter(
            WorkflowProposal.session_id == key,
            WorkflowProposal.status == "AWAITING_REVIEW",
        )
        existing_query = _apply_user_scope(
            existing_query,
            state,
        )

        for existing in existing_query.all():
            existing.status = "CANCELLED"
            existing.updated_at = now
            existing.last_error = (
                "Superseded by a newer review request."
            )

        row = WorkflowProposal(
            session_id=key,
            conversation_id=state.get("conversation_id"),
            user_id=(
                str(user_id)
                if user_id
                else None
            ),
            kind="document",
            revision=1,
            payload_json=payload_json,
            args_hash=args_hash,
            pending_document_id=str(pending_document_id),
            status="AWAITING_REVIEW",
            expires_at=expires_at,
        )

        pending.status = "needs_review"

        session.add(row)
        session.commit()
        session.refresh(row)

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision),
            "args_hash": row.args_hash,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to persist the document review."
        ) from exc
    finally:
        session.close()


def load_pending_document_review(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return the current durable document review for yes/no/edit routing."""

    session = SessionLocal()

    try:
        row = _find_pending_row(session, state)
        if row is None:
            return None

        payload = _load_payload(row)

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "args_hash": row.args_hash,
            "payload": payload,
            "pending_document_id": row.pending_document_id,
        }

    finally:
        session.close()


def load_document_edit_context(
    state: Dict[str, Any],
    proposal_id: str,
) -> Dict[str, Any]:
    """Reconstruct the exact server-side source needed for a safe edit."""

    session = SessionLocal()

    try:
        row = _find_pending_row(
            session,
            state,
            proposal_id,
        )

        if row is None:
            raise DocumentWorkflowError(
                "The document review can no longer be edited."
            )

        payload = _load_payload(row)

        pending_document_id = (
            row.pending_document_id
            or payload.get("pending_document_id")
        )

        if not pending_document_id:
            raise DocumentWorkflowError(
                "The saved review has no staged document reference."
            )

        pending = session.query(PendingDocumentUpload).filter(
            PendingDocumentUpload.pending_id
            == str(pending_document_id)
        ).first()

        if pending is None:
            raise DocumentWorkflowError(
                "The staged document for this review no longer exists."
            )

        user_id = state.get("user_id")
        if (
            user_id
            and pending.uploaded_by
            and str(pending.uploaded_by) != str(user_id)
        ):
            raise DocumentWorkflowError(
                "The staged document is not owned by the current user."
            )

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "pending_document_id": str(pending.pending_id),
            "original_user_request": str(
                payload.get("original_user_request") or ""
            ),
            "document_proposal": dict(
                payload.get("document_proposal") or {}
            ),
            "document_check_results": list(
                payload.get("document_check_results") or []
            ),
            "ingestion_result": _pending_upload_to_ingestion(
                pending
            ),
        }

    finally:
        session.close()


def approve_document_review(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Approve the exact current document revision, without executing it."""

    session = SessionLocal()

    try:
        row = _find_pending_row(session, state)
        if row is None:
            raise DocumentWorkflowError(
                "There is no pending document review to approve."
            )

        payload = _load_payload(row)

        if payload.get("requires_clarification"):
            raise DocumentWorkflowError(
                "This document review still has unresolved information. "
                "Edit the proposal before approving it."
            )

        proposal = payload.get("document_proposal") or {}
        actions = list(proposal.get("actions") or [])

        ready_actions = [
            action
            for action in actions
            if isinstance(action, dict)
            and not action.get("blocked")
        ]

        if not ready_actions:
            raise DocumentWorkflowError(
                "This document review has no executable ready actions."
            )

        row.status = "APPROVED"
        row.approved_by = (
            str(state.get("user_id"))
            if state.get("user_id")
            else None
        )
        row.approved_at = utcnow()
        row.updated_at = utcnow()
        row.last_error = None

        if row.pending_document_id:
            pending = session.query(PendingDocumentUpload).filter(
                PendingDocumentUpload.pending_id
                == row.pending_document_id
            ).first()
            if pending is not None:
                pending.status = "approved_pending_execution"

        session.commit()

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "args_hash": row.args_hash,
            "payload": payload,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to approve the document review safely."
        ) from exc
    finally:
        session.close()


def reject_document_review(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Reject the current document proposal without deleting the audit row."""

    session = SessionLocal()

    try:
        row = _find_pending_row(session, state)
        if row is None:
            raise DocumentWorkflowError(
                "There is no pending document review to reject."
            )

        payload = _load_payload(row)

        row.status = "REJECTED"
        row.updated_at = utcnow()
        row.last_error = None

        if row.pending_document_id:
            pending = session.query(PendingDocumentUpload).filter(
                PendingDocumentUpload.pending_id
                == row.pending_document_id
            ).first()
            if pending is not None:
                pending.status = "rejected_by_user"

        session.commit()

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "payload": payload,
        }

    except DocumentWorkflowError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise DocumentWorkflowError(
            "Unable to reject the document review safely."
        ) from exc
    finally:
        session.close()
