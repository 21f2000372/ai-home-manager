"""Deterministic document-likeness checks for uploaded images.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.rag.text_extraction import extract_text


@dataclass
class DocumentImageResult:
    is_document: bool
    confidence: float
    text: str
    reason: str


DOCUMENT_HINTS = {
    "invoice",
    "receipt",
    "bill",
    "total",
    "subtotal",
    "amount",
    "date",
    "qty",
    "quantity",
    "tax",
    "gst",
    "payment",
    "paid",
    "due",
    "warranty",
    "repair",
    "service",
    "statement",
    "grocery",
    "shopping",
}

_PAGE_MARKER_RE = re.compile(
    r"---\s*page\s+\d+\s*---",
    flags=re.IGNORECASE,
)


def check_text_is_document(
    text: str,
) -> DocumentImageResult:
    """Decide whether extracted image text can continue to classification.

    This gate only rejects blank or near-empty OCR. Short but readable text is
    accepted with low confidence so handwritten lists and bills can reach the
    stricter classification, authorization, interpretation, and review gates.
    It does not authorize storage or any derived action.
    """

    raw_text = text or ""
    text_without_page_markers = _PAGE_MARKER_RE.sub(
        " ",
        raw_text,
    )
    normalized = " ".join(
        text_without_page_markers.lower().split()
    )

    if not normalized:
        return DocumentImageResult(
            is_document=False,
            confidence=0.10,
            text=raw_text,
            reason="No readable text was detected in the image.",
        )

    words = normalized.split()
    word_count = len(words)

    document_hint_count = sum(
        1
        for keyword in DOCUMENT_HINTS
        if keyword in normalized
    )

    if word_count < 3:
        return DocumentImageResult(
            is_document=False,
            confidence=0.25,
            text=raw_text,
            reason=(
                "Image contains too little text to be treated as a "
                "document."
            ),
        )

    if word_count >= 8 and document_hint_count >= 1:
        return DocumentImageResult(
            is_document=True,
            confidence=0.90,
            text=raw_text,
            reason=(
                "Image contains substantial text and document-related "
                "terms."
            ),
        )

    if word_count >= 8:
        return DocumentImageResult(
            is_document=True,
            confidence=0.65,
            text=raw_text,
            reason="Image contains substantial readable text.",
        )

    if document_hint_count >= 1:
        return DocumentImageResult(
            is_document=True,
            confidence=0.60,
            text=raw_text,
            reason=(
                "Image contains limited readable text with a document-related "
                "term; downstream review is required."
            ),
        )

    return DocumentImageResult(
        is_document=True,
        confidence=0.45,
        text=raw_text,
        reason=(
            "Image contains limited readable text; downstream classification "
            "and review must determine whether it is supported."
        ),
    )


def check_image_is_document(
    file_path: str,
    extracted_text: Optional[str] = None,
) -> DocumentImageResult:
    """Run extraction once when the caller has not already supplied text."""

    if extracted_text is not None:
        return check_text_is_document(extracted_text)

    extraction = extract_text(file_path)

    if not extraction.success:
        return DocumentImageResult(
            is_document=False,
            confidence=0.0,
            text="",
            reason=(
                extraction.reason
                or "Unable to inspect image content."
            ),
        )

    return check_text_is_document(extraction.text)
