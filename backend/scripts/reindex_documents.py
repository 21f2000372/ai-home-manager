"""Rebuild Chroma chunks for approved saved documents.

Run from the backend directory:

    python3 -m scripts.reindex_documents --dry-run
    python3 -m scripts.reindex_documents
    python3 -m scripts.reindex_documents --user-id <uuid> --limit 20

SQLite remains authoritative. This command only selects approved, safe,
owner-bound documents and delegates idempotent Chroma replacement to
``app.rag.document_index``.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from app.db.base import SessionLocal
from app.models.documents import Document
from app.rag.document_index import (
    DocumentIndexError,
    index_document,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Candidate:
    document_id: str
    user_id: str
    filename: str


def _optional_user_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

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
        raise ValueError("--user-id is invalid.")

    return cleaned


def _positive_limit(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or value < 1:
        raise ValueError("--limit must be a positive integer.")
    return value


def _load_candidates(
    *,
    user_id: Optional[str],
    limit: Optional[int],
) -> List[_Candidate]:
    session = SessionLocal()

    try:
        query = session.query(Document).filter(
            Document.uploaded_by.isnot(None),
            Document.status == "approved",
            Document.prompt_injection_detected.is_(False),
            Document.extracted_text.isnot(None),
        )

        if user_id is not None:
            query = query.filter(
                Document.uploaded_by == user_id
            )

        query = query.order_by(
            Document.created_at.asc(),
            Document.document_id.asc(),
        )

        if limit is not None:
            query = query.limit(limit)

        rows = query.all()
        candidates: List[_Candidate] = []

        for row in rows:
            owner_id = str(row.uploaded_by or "").strip()
            extracted_text = str(row.extracted_text or "").strip()
            if not owner_id or not extracted_text:
                continue

            candidates.append(
                _Candidate(
                    document_id=str(row.document_id),
                    user_id=owner_id,
                    filename=str(
                        row.original_filename
                        or "document"
                    ),
                )
            )

        return candidates

    finally:
        session.close()


def reindex_documents(
    *,
    user_id: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    fail_fast: bool = False,
) -> Dict[str, Any]:
    """Reindex eligible documents and return an operational summary."""

    scoped_user_id = _optional_user_id(user_id)
    bounded_limit = _positive_limit(limit)
    candidates = _load_candidates(
        user_id=scoped_user_id,
        limit=bounded_limit,
    )

    report: Dict[str, Any] = {
        "dry_run": bool(dry_run),
        "user_id": scoped_user_id,
        "limit": bounded_limit,
        "eligible": len(candidates),
        "indexed": 0,
        "failed": 0,
        "failures": [],
    }

    if dry_run:
        return report

    for candidate in candidates:
        try:
            result = index_document(
                document_id=candidate.document_id,
                user_id=candidate.user_id,
            )
            if result.get("indexed"):
                report["indexed"] += 1
            else:
                raise DocumentIndexError(
                    "Document indexing did not complete."
                )
        except Exception:
            logger.exception(
                "Document reindex failed for document %s",
                candidate.document_id,
            )
            report["failed"] += 1
            report["failures"].append(
                {
                    "document_id": candidate.document_id,
                    "filename": candidate.filename,
                    "reason": "Document indexing failed.",
                }
            )
            if fail_fast:
                break

    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild owner-scoped Chroma chunks for approved documents."
        )
    )
    parser.add_argument(
        "--user-id",
        help="Restrict indexing to one document owner.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many eligible documents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count eligible documents without modifying Chroma.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first indexing failure.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)

    try:
        report = reindex_documents(
            user_id=args.user_id,
            limit=args.limit,
            dry_run=args.dry_run,
            fail_fast=args.fail_fast,
        )
    except ValueError as exc:
        print(
            json.dumps(
                {"error": str(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
