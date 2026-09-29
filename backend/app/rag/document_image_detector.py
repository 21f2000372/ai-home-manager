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
}

_PAGE_MARKER_RE = re.compile(
    r"---\s*page\s+\d+\s*---",
    flags=re.IGNORECASE,
)


def check_text_is_document(
    text: str,
) -> DocumentImageResult:
    """
    Decide whether already-extracted image text is document-like.

    This is the fast path used by the ingestion pipeline. It avoids running
    OCR a second time merely to decide whether the image looks like a
    document.
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

    return DocumentImageResult(
        is_document=False,
        confidence=0.40,
        text=raw_text,
        reason="Image does not contain enough document-like text.",
    )


def check_image_is_document(
    file_path: str,
    extracted_text: Optional[str] = None,
) -> DocumentImageResult:
    """
    Backwards-compatible image-document check.

    Callers that already performed OCR should pass ``extracted_text`` so this
    function performs only the inexpensive deterministic document-likeness
    check. Older callers may continue to pass only ``file_path``; in that
    case the public text-extraction API is used once.
    """

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
