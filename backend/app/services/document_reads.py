"""Read-only queries for household document records."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from app.models.documents import Document, DocumentLink, PendingDocumentUpload
from app.rag.document_access import can_read_document


def _timestamp(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _review_reasons(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        reasons = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(reasons, list):
        return []
    return [reason for reason in reasons if isinstance(reason, str)]


class DocumentReadService:
    """Load only records that the requesting household member may inspect."""

    @staticmethod
    def list_for_user(session, user_id: str, role: Any) -> dict[str, list[dict[str, Any]]]:
        documents = (
            session.query(Document)
            .filter(
                Document.status == "approved",
                Document.prompt_injection_detected.is_(False),
            )
            .order_by(Document.created_at.desc())
            .all()
        )
        visible_documents = [
            document
            for document in documents
            if can_read_document(role, document)
        ]
        visible_document_ids = {document.document_id for document in visible_documents}

        links = []
        if visible_document_ids:
            links = (
                session.query(DocumentLink)
                .filter(DocumentLink.document_id.in_(visible_document_ids))
                .order_by(DocumentLink.created_at.desc())
                .all()
            )
            links = [
                link
                for link in links
                if can_read_document(
                    role,
                    SimpleNamespace(domain=link.linked_domain),
                )
            ]

        pending_uploads = (
            session.query(PendingDocumentUpload)
            .filter(PendingDocumentUpload.uploaded_by == user_id)
            .order_by(PendingDocumentUpload.created_at.desc())
            .all()
        )

        return {
            "documents": [
                {
                    "document_id": document.document_id,
                    "document_type": _enum_value(document.document_type),
                    "classified_document_type": document.classified_document_type,
                    "domain": document.domain,
                    "classification_confidence": document.classification_confidence,
                    "classification_reason": document.classification_reason,
                    "original_filename": document.original_filename,
                    "mime_type": document.mime_type,
                    "extension": document.extension,
                    "file_size": document.file_size,
                    "extraction_method": document.extraction_method,
                    "page_count": document.page_count,
                    "prompt_injection_detected": document.prompt_injection_detected,
                    "status": document.status,
                    "uploaded_by": document.uploaded_by,
                    "created_at": _timestamp(document.created_at),
                }
                for document in visible_documents
            ],
            "pending_uploads": [
                {
                    "pending_id": pending.pending_id,
                    "upload_id": pending.upload_id,
                    "original_filename": pending.original_filename,
                    "mime_type": pending.mime_type,
                    "extension": pending.extension,
                    "file_size": pending.file_size,
                    "extraction_method": pending.extraction_method,
                    "page_count": pending.page_count,
                    "domain": pending.domain,
                    "classified_document_type": pending.classified_document_type,
                    "classification_confidence": pending.classification_confidence,
                    "classification_reason": pending.classification_reason,
                    "prompt_injection_detected": pending.prompt_injection_detected,
                    "status": pending.status,
                    "review_reasons": _review_reasons(pending.review_reasons_json),
                    "created_at": _timestamp(pending.created_at),
                }
                for pending in pending_uploads
            ],
            "links": [
                {
                    "link_id": link.link_id,
                    "document_id": link.document_id,
                    "linked_domain": link.linked_domain,
                    "linked_record_id": link.linked_record_id,
                    "created_at": _timestamp(link.created_at),
                }
                for link in links
            ],
        }