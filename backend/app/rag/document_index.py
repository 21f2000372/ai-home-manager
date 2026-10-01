"""Deterministic, role-gated indexing for approved documents.

SQLite is authoritative. Chroma stores replaceable semantic-search chunks.
Only permanently approved, prompt-injection-free documents may be indexed.

Documents are household-wide. Visibility is controlled by min_role (see
app.rag.document_access); the uploader is recorded as provenance only.

Compatible with Python 3.9.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.db.base import SessionLocal
from app.models.documents import Document
from app.models.enums import HouseholdRole
from app.rag.document_access import resolve_min_role
from app.rag.vector_store import VectorStore, get_default_store


logger = logging.getLogger(__name__)


DOCUMENT_SOURCE_DOMAIN = "documents"
DEFAULT_CHUNK_CHARACTERS = 1200
DEFAULT_CHUNK_OVERLAP = 160

_PAGE_MARKER_RE = re.compile(
    r"(?m)^---\s*Page\s+(\d+)\s*---\s*$",
    re.IGNORECASE,
)


class DocumentIndexError(RuntimeError):
    """Safe indexing failure that does not expose storage internals."""


@dataclass(frozen=True)
class DocumentChunk:
    page_number: int
    chunk_index: int
    text: str


@dataclass(frozen=True)
class _IndexableDocument:
    document_id: str
    uploaded_by: Optional[str]
    original_filename: str
    document_type: str
    classified_document_type: str
    domain: str
    content_hash: str
    extracted_text: str
    min_role: HouseholdRole


def _required_identifier(
    value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise DocumentIndexError(
            "{0} is required.".format(field)
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
        raise DocumentIndexError(
            "{0} is invalid.".format(field)
        )

    return cleaned


def _page_sections(text: str) -> List[Tuple[int, str]]:
    """Split extracted text by stable page markers."""

    value = str(text or "").strip()
    if not value:
        return []

    matches = list(_PAGE_MARKER_RE.finditer(value))
    if not matches:
        return [(1, value)]

    sections: List[Tuple[int, str]] = []

    prefix = value[: matches[0].start()].strip()
    if prefix:
        sections.append((1, prefix))

    for index, match in enumerate(matches):
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(value)
        )
        body = value[start:end].strip()
        if not body:
            continue

        try:
            page_number = int(match.group(1))
        except (TypeError, ValueError):
            page_number = index + 1

        if page_number < 1:
            page_number = index + 1

        sections.append((page_number, body))

    return sections


def _chunk_section(
    text: str,
    *,
    max_characters: int,
    overlap: int,
) -> List[str]:
    """Create bounded deterministic chunks with whitespace boundaries."""

    value = " ".join(str(text or "").split())
    if not value:
        return []

    if max_characters < 200:
        raise ValueError(
            "max_characters must be at least 200."
        )
    if overlap < 0 or overlap >= max_characters:
        raise ValueError(
            "overlap must be non-negative and smaller than max_characters."
        )

    chunks: List[str] = []
    start = 0

    while start < len(value):
        hard_end = min(
            start + max_characters,
            len(value),
        )
        end = hard_end

        if hard_end < len(value):
            boundary = value.rfind(
                " ",
                start + (max_characters // 2),
                hard_end,
            )
            if boundary > start:
                end = boundary

        chunk = value[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(value):
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end

        while (
            next_start < len(value)
            and value[next_start].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks


def chunk_document_text(
    text: str,
    *,
    max_characters: int = DEFAULT_CHUNK_CHARACTERS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[DocumentChunk]:
    """Build deterministic page-aware chunks from approved extraction text."""

    chunks: List[DocumentChunk] = []

    for page_number, page_text in _page_sections(text):
        for chunk_index, chunk_text in enumerate(
            _chunk_section(
                page_text,
                max_characters=max_characters,
                overlap=overlap,
            )
        ):
            chunks.append(
                DocumentChunk(
                    page_number=page_number,
                    chunk_index=chunk_index,
                    text=chunk_text,
                )
            )

    return chunks


def _document_type_value(document: Document) -> str:
    value = getattr(document, "document_type", None)
    enum_value = getattr(value, "value", None)
    return str(enum_value or value or "Other")


def _load_indexable_document(
    document_id: str,
) -> _IndexableDocument:
    """Load one approved, injection-free document by id.

    No owner filter: documents are household-wide. Callers are responsible
    for authorizing who may trigger indexing.
    """

    session = SessionLocal()

    try:
        row = (
            session.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.status == "approved",
                Document.prompt_injection_detected.is_(False),
            )
            .one_or_none()
        )

        if row is None:
            raise DocumentIndexError(
                "Document is unavailable."
            )

        extracted_text = str(
            row.extracted_text or ""
        ).strip()
        if not extracted_text:
            raise DocumentIndexError(
                "Document has no approved extracted text."
            )

        return _IndexableDocument(
            document_id=str(row.document_id),
            # uploaded_by is ON DELETE SET NULL; keep it None rather than
            # the string "None".
            uploaded_by=(
                str(row.uploaded_by)
                if row.uploaded_by
                else None
            ),
            original_filename=str(
                row.original_filename or "document"
            ),
            document_type=_document_type_value(row),
            classified_document_type=str(
                row.classified_document_type or ""
            ),
            domain=str(row.domain or "documents"),
            content_hash=str(
                row.normalized_text_hash
                or row.sha256
                or ""
            ),
            extracted_text=extracted_text,
            min_role=resolve_min_role(row),
        )

    finally:
        session.close()


def _chunk_id(
    document_id: str,
    chunk: DocumentChunk,
) -> str:
    return "document:{0}:page:{1}:chunk:{2}".format(
        document_id,
        chunk.page_number,
        chunk.chunk_index,
    )


def index_document(
    *,
    document_id: str,
    user_id: Optional[str] = None,
    store: Optional[VectorStore] = None,
) -> Dict[str, Any]:
    """Replace semantic chunks for one exact approved document.

    user_id is accepted only so existing callers keep working. It is ignored:
    it is neither an authorization input nor a metadata value. The uploader
    recorded in SQLite is stored as provenance.
    """

    scoped_document_id = _required_identifier(
        document_id,
        field="document_id",
    )

    document = _load_indexable_document(
        scoped_document_id,
    )
    chunks = chunk_document_text(
        document.extracted_text
    )
    if not chunks:
        raise DocumentIndexError(
            "Document has no indexable extracted text."
        )

    vector_store = store or get_default_store()

    # Remove obsolete chunks first. If the following upsert fails, SQLite
    # remains authoritative and this operation can be retried safely.
    vector_store.delete_document_embeddings(
        document_id=document.document_id,
    )

    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for chunk in chunks:
        ids.append(
            _chunk_id(document.document_id, chunk)
        )
        texts.append(chunk.text)

        metadata: Dict[str, Any] = {
            "document_id": document.document_id,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "domain": document.domain,
            "document_type": document.document_type,
            "classified_document_type": (
                document.classified_document_type
            ),
            "content_hash": document.content_hash,
            "original_filename": document.original_filename,
        }

        # Provenance only; never used as a read filter.
        if document.uploaded_by is not None:
            metadata["user_id"] = document.uploaded_by

        metadatas.append(metadata)

    vector_store.upsert_texts(
        ids=ids,
        texts=texts,
        source_domain=DOCUMENT_SOURCE_DOMAIN,
        min_role=document.min_role,
        extra_metadata=metadatas,
    )

    return {
        "indexed": True,
        "document_id": document.document_id,
        "chunk_count": len(chunks),
        "min_role": document.min_role.value,
    }


def index_document_best_effort(
    *,
    document_id: str,
    user_id: Optional[str] = None,
    store: Optional[VectorStore] = None,
) -> Dict[str, Any]:
    """Index without turning a committed archive into a failed request."""

    try:
        return index_document(
            document_id=document_id,
            user_id=user_id,
            store=store,
        )
    except Exception:
        logger.exception(
            "Document indexing failed for document %s",
            document_id,
        )
        return {
            "indexed": False,
            "document_id": str(document_id or ""),
            "chunk_count": 0,
        }


def sync_document_visibility(
    *,
    document_id: str,
    store: Optional[VectorStore] = None,
) -> int:
    """Apply a document's current SQLite min_role to its Chroma chunks.

    Call this after changing Document.min_role (or the domain default
    mapping) so Chroma does not drift from SQLite. No re-embedding occurs.
    Returns the number of chunks updated.
    """

    scoped_document_id = _required_identifier(
        document_id,
        field="document_id",
    )

    document = _load_indexable_document(
        scoped_document_id,
    )

    vector_store = store or get_default_store()

    return vector_store.update_document_min_role(
        document_id=document.document_id,
        min_role=document.min_role,
    )