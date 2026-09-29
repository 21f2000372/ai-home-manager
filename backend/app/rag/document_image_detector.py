from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from app.rag.text_extraction import _easyocr_image


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


def check_image_is_document(
    file_path: str,
) -> DocumentImageResult:
    """
    Decide whether an image appears to be a document.

    This does NOT classify the document into Finance/Maintenance.
    It only checks whether the image is document-like.
    """

    try:
        with Image.open(file_path) as image:
            text = _easyocr_image(image)

    except Exception as exc:
        return DocumentImageResult(
            is_document=False,
            confidence=0.0,
            text="",
            reason=f"Unable to inspect image: {exc}",
        )

    normalized = " ".join(
        text.lower().split()
    )

    if not normalized:
        return DocumentImageResult(
            is_document=False,
            confidence=0.10,
            text="",
            reason="No readable text was detected in the image.",
        )

    words = normalized.split()

    word_count = len(words)

    document_hint_count = sum(
        1
        for keyword in DOCUMENT_HINTS
        if keyword in normalized
    )

    # Very little text usually means this is not a useful document.
    if word_count < 3:
        return DocumentImageResult(
            is_document=False,
            confidence=0.25,
            text=text,
            reason="Image contains too little text to be treated as a document.",
        )

    # Strong document signal.
    if (
        word_count >= 8
        and document_hint_count >= 1
    ):
        return DocumentImageResult(
            is_document=True,
            confidence=0.90,
            text=text,
            reason="Image contains substantial text and document-related terms.",
        )

    # It has enough readable text to probably be a document,
    # but the signal is weaker.
    if word_count >= 8:
        return DocumentImageResult(
            is_document=True,
            confidence=0.65,
            text=text,
            reason="Image contains substantial readable text.",
        )

    return DocumentImageResult(
        is_document=False,
        confidence=0.40,
        text=text,
        reason="Image does not contain enough document-like text.",
    )