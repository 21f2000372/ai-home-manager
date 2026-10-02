"""Household-scoped retrieval for approved saved documents.

Chroma supplies semantic candidates only. SQLite revalidates lifecycle and
prompt-injection state before any vector text reaches the agent. Document
visibility is role-gated; uploader identity is provenance only and is never
used as a read filter. The private object-storage key is never returned.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from app.db.base import SessionLocal
from app.models.documents import Document
from app.models.enums import HouseholdRole
from app.rag.document_access import resolve_min_role
from app.rag.vector_store import (
    VectorStore,
    get_default_store,
    roles_visible_to,
)
from app.storage.cloudinary_storage import generate_download_url


logger = logging.getLogger(__name__)


MAX_SEARCH_RESULTS = 10
MAX_QUERY_CHARACTERS = 300
MAX_EVIDENCE_CHARACTERS = 900
MAX_DOCUMENT_EXCERPT_CHARACTERS = 1800
MIN_SHORT_REFERENCE_CHARACTERS = 8

_DOCUMENT_REFERENCE_RE = re.compile(r"^[0-9a-fA-F-]+$")
_DOCUMENT_FILENAME_RE = re.compile(
    r"^[^/\\\x00-\x1f]{1,255}\.(?:pdf|jpe?g|png|webp)$",
    re.IGNORECASE,
)


class DocumentRetrievalError(RuntimeError):
    """Retrieval error containing a client-safe message."""


@dataclass(frozen=True)
class _SemanticCandidate:
    document_id: str
    content_hash: str
    text: str
    page_number: Optional[int]
    distance: Optional[float]


def _authorized_role(value: Any) -> HouseholdRole:
    """Validate a household role without imposing a global Adult+ gate.

    Document visibility is decided per document from its resolved min_role.
    """

    try:
        return HouseholdRole(value)
    except (TypeError, ValueError):
        raise DocumentRetrievalError(
            "You do not have permission to retrieve documents."
        ) from None


def _bounded_limit(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_SEARCH_RESULTS
    ):
        raise DocumentRetrievalError(
            "limit must be an integer from 1 to {0}.".format(
                MAX_SEARCH_RESULTS
            )
        )
    return value


def _normalized_query(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DocumentRetrievalError(
            "query must be a string."
        )

    cleaned = " ".join(value.split())
    if len(cleaned) > MAX_QUERY_CHARACTERS:
        raise DocumentRetrievalError(
            "query is too long."
        )
    if any(not character.isprintable() for character in cleaned):
        raise DocumentRetrievalError(
            "query contains invalid characters."
        )
    return cleaned


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _safe_documents_query(session: Any) -> Any:
    """Return documents eligible for household retrieval.

    uploaded_by is intentionally not part of this filter. It is audit /
    provenance metadata, not an authorization boundary.
    """

    return session.query(Document).filter(
        Document.status == "approved",
        Document.prompt_injection_detected.is_(False),
    )


def _document_visible_to(
    row: Document,
    role: HouseholdRole,
) -> bool:
    """Return whether ``role`` may read this document.

    The document's resolved min_role is authoritative. This keeps direct SQL
    lookup and lexical fallback aligned with Chroma's role filter and fails
    closed if a malformed document cannot be assigned a visibility level.
    """

    try:
        min_role = resolve_min_role(row)
    except Exception:
        logger.exception(
            "Unable to resolve document visibility for document %s",
            getattr(row, "document_id", "unknown"),
        )
        return False

    return min_role.value in roles_visible_to(role)


def _document_type(row: Document) -> str:
    value = getattr(row.document_type, "value", row.document_type)
    return str(value or "Other")


def _short_reference(document_id: str) -> str:
    return str(document_id)[:12]


def _bounded_text(value: Any, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _lexical_excerpt(text: str, query: str) -> str:
    value = " ".join(str(text or "").split())
    if not value:
        return ""
    if not query:
        return _bounded_text(value, MAX_EVIDENCE_CHARACTERS)

    lowered = value.casefold()
    terms = [
        term.casefold()
        for term in query.split()
        if len(term) >= 2
    ]
    positions = [
        lowered.find(term)
        for term in terms
        if lowered.find(term) >= 0
    ]
    if not positions:
        return _bounded_text(value, MAX_EVIDENCE_CHARACTERS)

    center = min(positions)
    start = max(0, center - 180)
    end = min(len(value), start + MAX_EVIDENCE_CHARACTERS)
    excerpt = value[start:end].strip()
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(value):
        excerpt += "…"
    return excerpt


def _nested_values(result: Dict[str, Any], field: str) -> List[Any]:
    value = result.get(field) or []
    if not isinstance(value, list) or not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else []


def _semantic_candidates(result: Dict[str, Any]) -> List[_SemanticCandidate]:
    documents = _nested_values(result, "documents")
    metadatas = _nested_values(result, "metadatas")
    distances = _nested_values(result, "distances")
    candidates: List[_SemanticCandidate] = []

    for index, text in enumerate(documents):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            and isinstance(metadatas[index], dict)
            else {}
        )
        document_id = str(
            metadata.get("document_id") or ""
        ).strip()
        content_hash = str(
            metadata.get("content_hash") or ""
        ).strip()
        if not document_id or not content_hash:
            continue

        page_value = metadata.get("page_number")
        try:
            page_number = int(page_value)
        except (TypeError, ValueError):
            page_number = None

        distance_value = (
            distances[index]
            if index < len(distances)
            else None
        )
        try:
            distance = float(distance_value)
        except (TypeError, ValueError):
            distance = None

        candidates.append(
            _SemanticCandidate(
                document_id=document_id,
                content_hash=content_hash,
                text=_bounded_text(
                    text,
                    MAX_EVIDENCE_CHARACTERS,
                ),
                page_number=page_number,
                distance=distance,
            )
        )

    return candidates


def _public_result(
    row: Document,
    *,
    evidence: str,
    page_number: Optional[int] = None,
    distance: Optional[float] = None,
) -> Dict[str, Any]:
    saved_at = _created_at_token(row.created_at)
    result: Dict[str, Any] = {
        "document_id": str(row.document_id),
        "reference": _short_reference(str(row.document_id)),
        "filename": str(row.original_filename or "document"),
        "document_type": _document_type(row),
        "classified_document_type": str(
            row.classified_document_type or ""
        ),
        "domain": str(row.domain or ""),
        "created_at": saved_at or None,
        "saved_at": saved_at or None,
        "evidence": evidence,
    }
    if page_number is not None and page_number > 0:
        result["page_number"] = page_number
    if distance is not None:
        result["distance"] = distance
    return result


def search_documents(
    *,
    role: str,
    query: str = "",
    limit: int = 5,
    store: Optional[VectorStore] = None,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search approved household documents semantically with SQL fallback.

    user_id is accepted temporarily for backward compatibility with older
    callers, but is intentionally ignored and never used as a read filter.
    """

    scoped_role = _authorized_role(role)
    cleaned_query = _normalized_query(query)
    bounded_limit = _bounded_limit(limit)

    semantic: List[_SemanticCandidate] = []
    if cleaned_query:
        try:
            result = (store or get_default_store()).query(
                cleaned_query,
                role=scoped_role,
                n_results=min(bounded_limit * 4, 20),
                source_domain="documents",
            )
            semantic = _semantic_candidates(result)
        except Exception:
            logger.exception(
                "Semantic household document retrieval failed"
            )

    session = SessionLocal()

    try:
        result_rows: List[Dict[str, Any]] = []
        seen = set()

        candidate_ids = []
        for candidate in semantic:
            if candidate.document_id not in candidate_ids:
                candidate_ids.append(candidate.document_id)

        rows_by_id: Dict[str, Document] = {}
        if candidate_ids:
            rows = (
                _safe_documents_query(session)
                .filter(Document.document_id.in_(candidate_ids))
                .all()
            )
            rows_by_id = {
                str(row.document_id): row
                for row in rows
            }

        for candidate in semantic:
            if len(result_rows) >= bounded_limit:
                break
            if candidate.document_id in seen:
                continue
            row = rows_by_id.get(candidate.document_id)
            if row is None:
                continue
            if not _document_visible_to(row, scoped_role):
                continue
            current_hash = str(
                row.normalized_text_hash
                or row.sha256
                or ""
            ).strip()
            if (
                not current_hash
                or candidate.content_hash != current_hash
            ):
                continue
            seen.add(candidate.document_id)
            result_rows.append(
                _public_result(
                    row,
                    evidence=candidate.text,
                    page_number=candidate.page_number,
                    distance=candidate.distance,
                )
            )

        lexical_query = _safe_documents_query(session)
        if cleaned_query:
            pattern = "%{0}%".format(
                _escape_like(cleaned_query)
            )
            lexical_query = lexical_query.filter(
                or_(
                    Document.original_filename.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Document.classified_document_type.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Document.domain.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Document.extracted_text.ilike(
                        pattern,
                        escape="\\",
                    ),
                )
            )

        lexical_rows = (
            lexical_query.order_by(
                Document.created_at.desc()
            )
            .limit(100)
            .all()
        )

        for row in lexical_rows:
            if len(result_rows) >= bounded_limit:
                break
            document_id = str(row.document_id)
            if document_id in seen:
                continue
            if not _document_visible_to(row, scoped_role):
                continue
            seen.add(document_id)
            result_rows.append(
                _public_result(
                    row,
                    evidence=_lexical_excerpt(
                        str(row.extracted_text or ""),
                        cleaned_query,
                    ),
                )
            )

        return result_rows

    finally:
        session.close()


def _validated_reference(value: Any) -> str:
    if not isinstance(value, str):
        raise DocumentRetrievalError(
            "Document reference is required."
        )
    cleaned = value.strip()
    is_reference = bool(
        MIN_SHORT_REFERENCE_CHARACTERS <= len(cleaned) <= 36
        and _DOCUMENT_REFERENCE_RE.fullmatch(cleaned)
    )
    is_filename = bool(
        _DOCUMENT_FILENAME_RE.fullmatch(cleaned)
    )
    if not is_reference and not is_filename:
        raise DocumentRetrievalError(
            "Document reference is invalid."
        )
    return cleaned


def _created_at_token(value: Any) -> str:
    if not isinstance(value, datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _validated_saved_at(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise DocumentRetrievalError(
            "saved_at must be an ISO date-time string."
        )

    cleaned = value.strip()
    if (
        not cleaned
        or cleaned != value
        or len(cleaned) > 64
        or any(not character.isprintable() for character in cleaned)
    ):
        raise DocumentRetrievalError(
            "saved_at must be an ISO date-time string."
        )

    normalized = (
        cleaned[:-1] + "+00:00"
        if cleaned.endswith(("Z", "z"))
        else cleaned
    )
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise DocumentRetrievalError(
            "saved_at must be an ISO date-time string."
        ) from None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _resolve_document(
    *,
    role: str,
    document_reference: str,
    saved_at: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Document:
    """Resolve one approved household document visible to the caller.

    user_id is accepted temporarily for backward compatibility with older
    callers, but is intentionally ignored.
    """

    scoped_role = _authorized_role(role)
    reference = _validated_reference(document_reference)
    saved_datetime = _validated_saved_at(saved_at)
    session = SessionLocal()

    try:
        query = _safe_documents_query(session)
        if not _DOCUMENT_REFERENCE_RE.fullmatch(reference):
            query = query.filter(
                Document.original_filename.ilike(
                    _escape_like(reference),
                    escape="\\",
                )
            )
            rows = (
                query.order_by(Document.created_at.desc())
                .limit(101)
                .all()
            )
            if saved_datetime is not None:
                saved_token = _created_at_token(saved_datetime)
                rows = [
                    candidate
                    for candidate in rows
                    if _created_at_token(candidate.created_at)
                    == saved_token
                ]
        elif len(reference) == 36:
            rows = query.filter(
                Document.document_id == reference
            ).limit(2).all()
        else:
            rows = query.filter(
                Document.document_id.like(
                    _escape_like(reference) + "%",
                    escape="\\",
                )
            ).limit(101).all()

        # Filter before ambiguity checks so inaccessible documents neither
        # block an accessible match nor reveal their existence.
        rows = [
            candidate
            for candidate in rows
            if _document_visible_to(candidate, scoped_role)
        ]

        if not rows:
            raise DocumentRetrievalError(
                "Document is unavailable."
            )
        if len(rows) > 1:
            raise DocumentRetrievalError(
                "Document reference is ambiguous."
            )

        row = rows[0]
        if (
            saved_datetime is not None
            and _created_at_token(row.created_at)
            != _created_at_token(saved_datetime)
        ):
            raise DocumentRetrievalError(
                "Document is unavailable."
            )
        # Return a detached-safe copy with only fields needed by retrieval.
        detached = Document(
            document_id=str(row.document_id),
            document_type=row.document_type,
            classified_document_type=row.classified_document_type,
            domain=row.domain,
            classification_confidence=row.classification_confidence,
            classification_reason=row.classification_reason,
            storage_key=str(row.storage_key),
            original_filename=row.original_filename,
            mime_type=row.mime_type,
            extension=row.extension,
            file_size=row.file_size,
            extracted_text=row.extracted_text,
            extraction_method=row.extraction_method,
            page_count=row.page_count,
            prompt_injection_detected=False,
            status="approved",
            uploaded_by=row.uploaded_by,
            created_at=row.created_at,
        )
        return detached

    finally:
        session.close()


def get_document(
    *,
    role: str,
    document_reference: str,
    saved_at: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return safe metadata and bounded approved household document text.

    user_id is accepted temporarily for backward compatibility and ignored.
    """

    scoped_role = _authorized_role(role)
    row = _resolve_document(
        role=scoped_role.value,
        document_reference=document_reference,
        saved_at=saved_at,
    )
    result = _public_result(
        row,
        evidence=_bounded_text(
            row.extracted_text,
            MAX_DOCUMENT_EXCERPT_CHARACTERS,
        ),
    )
    result.update(
        {
            "mime_type": str(row.mime_type or ""),
            "file_size": row.file_size,
            "page_count": row.page_count,
            "extraction_method": str(
                row.extraction_method or ""
            ),
        }
    )
    return result


def _download_format(row: Document) -> str:
    extension = str(row.extension or "").strip().lower()
    value = extension.lstrip(".")
    if value == "jpeg":
        value = "jpg"
    if value not in {"pdf", "jpg", "png", "webp"}:
        raise DocumentRetrievalError(
            "Original document format is unavailable."
        )
    return value


def get_original_document(
    *,
    role: str,
    document_reference: str,
    saved_at: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Authorize one household document and return its signed download URL.

    user_id is accepted temporarily for backward compatibility and ignored.
    """

    scoped_role = _authorized_role(role)
    if scoped_role == HouseholdRole.GUEST:
        raise DocumentRetrievalError(
            "You do not have permission to download documents."
        )

    row = _resolve_document(
        role=scoped_role.value,
        document_reference=document_reference,
        saved_at=saved_at,
    )

    try:
        download_url = generate_download_url(
            str(row.storage_key),
            _download_format(row),
            resource_type="image",
        )
    except DocumentRetrievalError:
        raise
    except Exception:
        logger.exception(
            "Signed document download failed for document %s",
            row.document_id,
        )
        raise DocumentRetrievalError(
            "Original document is temporarily unavailable."
        ) from None

    return {
        "document_id": str(row.document_id),
        "reference": _short_reference(str(row.document_id)),
        "filename": str(row.original_filename or "document"),
        "mime_type": str(row.mime_type or ""),
        "download_url": str(download_url),
    }
