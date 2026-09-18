"""Document metadata CRUD tools."""
from __future__ import annotations

from langchain_core.tools import tool

from app.db.base import SessionLocal
from app.models.documents import Document
from app.models.enums import DocumentType
from typing import Optional

@tool
def create_document(
    storage_key: str,
    document_type: str = "Other",
    original_filename: str = "",
    mime_type: str = "",
) -> str:
    """Create document metadata for a file already stored in object storage."""
    session = SessionLocal()

    try:
        try:
            parsed_type = DocumentType(document_type)
        except ValueError:
            return (
                f"Invalid document_type '{document_type}'. "
                "Use Receipt, Bill, Warranty, or Other."
            )

        document = Document(
            storage_key=storage_key,
            document_type=parsed_type,
            original_filename=original_filename or None,
            mime_type=mime_type or None,
        )

        session.add(document)
        session.commit()
        session.refresh(document)

        return (
            f"Created document "
            f"'{original_filename or storage_key}' "
            f"(id={document.document_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to create document: {exc}"

    finally:
        session.close()


@tool
def list_documents() -> str:
    """List stored document metadata."""
    session = SessionLocal()

    try:
        rows = (
            session.query(Document)
            .order_by(Document.created_at.desc())
            .limit(20)
            .all()
        )

        if not rows:
            return "No documents found."

        return "\n".join(
            f"- {d.original_filename or d.storage_key}: "
            f"type={d.document_type.value} "
            f"(id={d.document_id})"
            for d in rows
        )

    finally:
        session.close()


@tool
def get_document(document_id: str) -> str:
    """Get one document by id."""
    session = SessionLocal()

    try:
        document = session.get(Document, document_id)

        if not document:
            return f"No document found with id {document_id}."

        return (
            f"Document: "
            f"{document.original_filename or document.storage_key}; "
            f"type: {document.document_type.value}; "
            f"mime_type: {document.mime_type or 'not set'}; "
            f"id: {document.document_id}"
        )

    finally:
        session.close()


@tool
def update_document(
    document_id: str,
    storage_key: Optional[str] = None,
    document_type: Optional[str] = None,
    original_filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> str:
    """Update document metadata."""
    session = SessionLocal()

    try:
        document = session.get(Document, document_id)

        if not document:
            return f"No document found with id {document_id}."

        changed = []

        if storage_key is not None:
            document.storage_key = storage_key
            changed.append("storage_key updated")

        if document_type is not None:
            try:
                document.document_type = DocumentType(document_type)
            except ValueError:
                return (
                    f"Invalid document_type '{document_type}'. "
                    "Use Receipt, Bill, Warranty, or Other."
                )

            changed.append(f"document_type={document_type}")

        if original_filename is not None:
            document.original_filename = original_filename or None
            changed.append("original_filename updated")

        if mime_type is not None:
            document.mime_type = mime_type or None
            changed.append("mime_type updated")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated document ({document.document_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update document: {exc}"

    finally:
        session.close()


@tool
def delete_document(document_id: str) -> str:
    """Delete document metadata."""
    session = SessionLocal()

    try:
        document = session.get(Document, document_id)

        if not document:
            return f"No document found with id {document_id}."

        session.delete(document)
        session.commit()

        return f"Deleted document (id={document_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete document: {exc}"

    finally:
        session.close()


TOOLS = [
    create_document,
    list_documents,
    get_document,
    update_document,
    delete_document,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}