"""Document metadata CRUD tools."""
from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from app.db.base import SessionLocal
from app.models.documents import Document, DocumentLink
from app.models.enums import DocumentType
from typing import Optional


_MONEY_RE = re.compile(
    r"(?P<currency>₹|rs\.?|inr|\$|usd|eur|€|gbp|£)\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?P<date>\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    re.IGNORECASE,
)
_INVOICE_RE = re.compile(
    r"\b(?:invoice|bill|statement|ref(?:erence)?|account)\s*(?:no\.?|number|#|id)?\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/-]{2,})",
    re.IGNORECASE,
)


def _normalize_currency(raw: str) -> str:
    value = raw.lower().replace(".", "")
    if value in {"₹", "rs", "inr"}:
        return "INR"
    if value in {"$", "usd"}:
        return "USD"
    if value in {"€", "eur"}:
        return "EUR"
    if value in {"£", "gbp"}:
        return "GBP"
    return raw.upper()


def _minor_units(amount: str) -> int:
    return int(round(float(amount.replace(",", "")) * 100))


def _candidate_payee(lines: list[str]) -> str:
    for line in lines[:8]:
        clean = line.strip(" :-\t")
        if not clean:
            continue
        lowered = clean.lower()
        if any(token in lowered for token in ("invoice", "bill", "receipt", "statement", "date", "total")):
            continue
        if len(clean) <= 80:
            return clean
    return ""

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


@tool
def extract_bill_information(
    bill_text: str,
    document_id: str = "",
) -> str:
    """Extract bill/receipt facts from readable text supplied by the user or OCR."""
    text = (bill_text or "").strip()
    if not text:
        return "No readable bill text was provided for extraction."

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    amounts = []
    for match in _MONEY_RE.finditer(text):
        amounts.append({
            "amount_minor": _minor_units(match.group("amount")),
            "currency": _normalize_currency(match.group("currency")),
            "raw": match.group(0),
        })

    dates = [match.group("date") for match in _DATE_RE.finditer(text)]
    invoice_match = _INVOICE_RE.search(text)

    extracted = {
        "document_id": document_id or None,
        "payee": _candidate_payee(lines) or None,
        "total": max(amounts, key=lambda item: item["amount_minor"]) if amounts else None,
        "all_amounts": amounts[:8],
        "dates": dates[:8],
        "invoice_or_reference": invoice_match.group(1) if invoice_match else None,
        "category_hint": "utilities" if re.search(r"\b(electric|water|gas|internet|broadband|utility)\b", text, re.I) else None,
        "confidence": "heuristic",
        "next_step": "Use log_expense for a paid bill or create_recurring_bill for an upcoming recurring obligation.",
    }

    return json.dumps(extracted, ensure_ascii=False, separators=(",", ":"))


@tool
def link_document_to_record(
    document_id: str,
    linked_domain: str,
    linked_record_id: str,
) -> str:
    """Link a stored document to a finance, maintenance, food, or task record."""
    allowed_domains = {"finance", "maintenance", "food", "tasks"}
    if linked_domain not in allowed_domains:
        return f"Invalid linked_domain '{linked_domain}'. Use one of: {', '.join(sorted(allowed_domains))}."

    session = SessionLocal()

    try:
        document = session.get(Document, document_id)

        if not document:
            return f"No document found with id {document_id}."

        existing = (
            session.query(DocumentLink)
            .filter(
                DocumentLink.linked_domain == linked_domain,
                DocumentLink.linked_record_id == linked_record_id,
            )
            .first()
        )
        if existing:
            return (
                f"Document link already exists for "
                f"{linked_domain}:{linked_record_id} (link_id={existing.link_id})."
            )

        link = DocumentLink(
            document_id=document_id,
            linked_domain=linked_domain,
            linked_record_id=linked_record_id,
        )
        session.add(link)
        session.commit()
        session.refresh(link)

        return (
            f"Linked document {document_id} to "
            f"{linked_domain}:{linked_record_id} (link_id={link.link_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to link document: {exc}"

    finally:
        session.close()


@tool
def list_document_links(document_id: str = "") -> str:
    """List document-to-domain record links."""
    session = SessionLocal()

    try:
        query = session.query(DocumentLink)
        if document_id:
            query = query.filter(DocumentLink.document_id == document_id)

        rows = query.order_by(DocumentLink.created_at.desc()).limit(20).all()

        if not rows:
            return "No document links found."

        return "\n".join(
            f"- document={row.document_id} -> {row.linked_domain}:{row.linked_record_id} "
            f"(link_id={row.link_id})"
            for row in rows
        )

    finally:
        session.close()


TOOLS = [
    create_document,
    list_documents,
    get_document,
    update_document,
    delete_document,
    extract_bill_information,
    link_document_to_record,
    list_document_links,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}
