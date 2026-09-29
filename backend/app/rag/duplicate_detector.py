from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import List, Optional

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.models.documents import (
    Document,
    PendingDocumentUpload,
)


# =========================================================
# File SHA-256
# =========================================================


def calculate_sha256(
    file_path: str,
    chunk_size: int = 1024 * 1024,
) -> str:
    """
    Calculate SHA-256 for a file.

    Same hash means the files are byte-for-byte identical.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            "File does not exist: {}".format(
                file_path
            )
        )

    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                chunk_size
            )

            if not chunk:
                break

            sha256.update(
                chunk
            )

    return sha256.hexdigest()


def are_exact_duplicates(
    first_file_path: str,
    second_file_path: str,
) -> bool:
    """
    Compare two files using SHA-256.
    """

    first_hash = calculate_sha256(
        first_file_path
    )

    second_hash = calculate_sha256(
        second_file_path
    )

    return (
        first_hash
        ==
        second_hash
    )


def compare_hashes(
    first_hash: Optional[str],
    second_hash: Optional[str],
) -> bool:
    """
    Compare two previously calculated hashes.
    """

    if not first_hash:
        return False

    if not second_hash:
        return False

    return (
        first_hash
        ==
        second_hash
    )


# =========================================================
# Normalized text hashing
# =========================================================


def normalize_document_text(
    text: str,
) -> str:
    """
    Normalize extracted text for duplicate comparison.
    """

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = " ".join(
        text.split()
    )

    return text


def calculate_text_hash(
    text: str,
) -> str:
    """
    Calculate SHA-256 over normalized extracted text.
    """

    normalized = normalize_document_text(
        text
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


def are_text_duplicates(
    first_text: str,
    second_text: str,
) -> bool:
    """
    Compare two documents after text normalization.
    """

    return (
        calculate_text_hash(
            first_text
        )
        ==
        calculate_text_hash(
            second_text
        )
    )


# =========================================================
# Visual / perceptual hashing
# =========================================================


def calculate_visual_hashes(
    file_path: str,
) -> List[str]:
    """
    Calculate perceptual hashes for:

    0 degrees
    90 degrees
    180 degrees
    270 degrees

    This helps detect rotated or recompressed copies.
    """

    hashes: List[str] = []

    with Image.open(
        file_path
    ) as image:

        image = image.convert(
            "RGB"
        )

        rotations = [
            image,
            image.rotate(
                90,
                expand=True,
            ),
            image.rotate(
                180,
                expand=True,
            ),
            image.rotate(
                270,
                expand=True,
            ),
        ]

        for rotated in rotations:

            visual_hash = imagehash.phash(
                rotated
            )

            hashes.append(
                str(
                    visual_hash
                )
            )

    return hashes


def visual_hash_distance(
    first_hash: str,
    second_hash: str,
) -> int:
    """
    Return Hamming distance between two perceptual hashes.

    Smaller values indicate greater visual similarity.
    """

    first = imagehash.hex_to_hash(
        first_hash
    )

    second = imagehash.hex_to_hash(
        second_hash
    )

    return (
        first
        -
        second
    )


def are_visual_near_duplicates(
    first_hashes: List[str],
    second_hashes: List[str],
    threshold: int = 6,
) -> bool:
    """
    Compare all orientation hashes.

    Visual similarity should only FLAG a possible duplicate.

    It should never automatically reject the document.
    """

    if not first_hashes:
        return False

    if not second_hashes:
        return False

    for first_hash in first_hashes:

        for second_hash in second_hashes:

            try:
                distance = visual_hash_distance(
                    first_hash,
                    second_hash,
                )

            except Exception:
                continue

            if distance <= threshold:
                return True

    return False


# =========================================================
# Database duplicate lookup policy
# =========================================================


ACTIVE_PENDING_DUPLICATE_STATUSES = (
    "staged",
    "needs_review",
    "archived_pending_actions",
)

APPROVED_DOCUMENT_STATUS = "approved"


def _safe_duplicate_result(
    match_type: str,
    source: str,
) -> dict:
    """Return duplicate information safe for propagation through ingestion."""

    return {
        "match_type": match_type,
        "source": source,
    }


# =========================================================
# Database exact duplicate lookup
# =========================================================


def find_exact_duplicate(
    session: Session,
    sha256_hash: str,
    uploaded_by: Optional[str] = None,
) -> Optional[dict]:
    """Search approved documents and this user's active pending uploads."""

    if not sha256_hash:
        return None

    document = (
        session.query(Document)
        .filter(
            Document.sha256 == sha256_hash,
            Document.status == APPROVED_DOCUMENT_STATUS,
        )
        .first()
    )

    if document is not None:
        return _safe_duplicate_result("exact", "document")

    if not uploaded_by:
        return None

    pending = (
        session.query(PendingDocumentUpload)
        .filter(
            PendingDocumentUpload.sha256 == sha256_hash,
            PendingDocumentUpload.uploaded_by == str(uploaded_by),
            PendingDocumentUpload.status.in_(
                ACTIVE_PENDING_DUPLICATE_STATUSES
            ),
        )
        .first()
    )

    if pending is not None:
        return _safe_duplicate_result("exact", "pending")

    return None


# =========================================================
# Database text duplicate lookup
# =========================================================


def find_text_duplicate(
    session: Session,
    normalized_text_hash: str,
    uploaded_by: Optional[str] = None,
) -> Optional[dict]:
    """Return an identical-text signal; callers must treat it as review-only."""

    if not normalized_text_hash:
        return None

    document = (
        session.query(Document)
        .filter(
            Document.normalized_text_hash == normalized_text_hash,
            Document.status == APPROVED_DOCUMENT_STATUS,
        )
        .first()
    )

    if document is not None:
        return _safe_duplicate_result("text", "document")

    if not uploaded_by:
        return None

    pending = (
        session.query(PendingDocumentUpload)
        .filter(
            PendingDocumentUpload.normalized_text_hash
            == normalized_text_hash,
            PendingDocumentUpload.uploaded_by == str(uploaded_by),
            PendingDocumentUpload.status.in_(
                ACTIVE_PENDING_DUPLICATE_STATUSES
            ),
        )
        .first()
    )

    if pending is not None:
        return _safe_duplicate_result("text", "pending")

    return None


# =========================================================
# Stored visual-hash utilities
# =========================================================


def _parse_visual_hashes(
    value: Optional[str],
) -> List[str]:
    """Decode visual hashes stored as JSON."""

    if not value:
        return []

    try:
        parsed = json.loads(value)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return []

    if not isinstance(parsed, list):
        return []

    return [
        item
        for item in parsed
        if isinstance(item, str)
    ]


# =========================================================
# Database visual near-duplicate lookup
# =========================================================


def find_visual_near_duplicate(
    session: Session,
    visual_hashes: List[str],
    threshold: int = 6,
    uploaded_by: Optional[str] = None,
) -> Optional[dict]:
    """Return a visual-similarity signal; it is never proof of duplication."""

    if not visual_hashes:
        return None

    documents = (
        session.query(Document)
        .filter(
            Document.visual_hashes_json.isnot(None),
            Document.status == APPROVED_DOCUMENT_STATUS,
        )
        .all()
    )

    for document in documents:
        stored_hashes = _parse_visual_hashes(
            document.visual_hashes_json
        )
        if (
            stored_hashes
            and are_visual_near_duplicates(
                visual_hashes,
                stored_hashes,
                threshold=threshold,
            )
        ):
            return _safe_duplicate_result("visual", "document")

    if not uploaded_by:
        return None

    pending_rows = (
        session.query(PendingDocumentUpload)
        .filter(
            PendingDocumentUpload.visual_hashes_json.isnot(None),
            PendingDocumentUpload.uploaded_by == str(uploaded_by),
            PendingDocumentUpload.status.in_(
                ACTIVE_PENDING_DUPLICATE_STATUSES
            ),
        )
        .all()
    )

    for pending in pending_rows:
        stored_hashes = _parse_visual_hashes(
            pending.visual_hashes_json
        )
        if (
            stored_hashes
            and are_visual_near_duplicates(
                visual_hashes,
                stored_hashes,
                threshold=threshold,
            )
        ):
            return _safe_duplicate_result("visual", "pending")

    return None
