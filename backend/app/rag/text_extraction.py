from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import List, Optional

import easyocr
import fitz
import numpy as np
from PIL import Image, ImageOps


logger = logging.getLogger(__name__)


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MIN_EMBEDDED_TEXT_LENGTH = 30
OCR_CONFIDENCE_THRESHOLD = 0.20
SECURITY_OCR_CONFIDENCE_THRESHOLD = 0.02
PDF_RENDER_SCALE = 2

# Most correctly-oriented document images should need only one OCR pass.
# Additional rotations are attempted only when the first pass contains too
# little useful text. This preserves rotated-image support while avoiding four
# OCR passes for the common case.
MIN_ORIENTATION_TEXT_LENGTH = 24
MIN_ORIENTATION_WORDS = 4


@dataclass
class TextExtractionResult:
    success: bool
    text: str
    method: str
    page_count: int = 1
    reason: Optional[str] = None
    # Low-confidence OCR is scanned only by deterministic security
    # guardrails. It must never be used as document facts or persisted as the
    # approved extraction.
    security_text: str = ""


# Create the OCR reader once per application process. gpu=False keeps the
# current laptop/server behavior. The reader is protected by a lock because
# EasyOCR/PyTorch reader thread-safety is not guaranteed across simultaneous
# Flask requests.
_OCR_READER = easyocr.Reader(
    ["en"],
    gpu=False,
)
_OCR_LOCK = Lock()


def extract_text(file_path: str) -> TextExtractionResult:
    """
    Extract readable text from a supported staged document.

    Supported file types:
    - PDF
    - JPG / JPEG
    - PNG
    - WEBP

    Every successful extraction contains explicit page markers in the form:

        --- Page N ---

    This function only reads the document. It does not classify it, infer
    business actions, persist permanent files, or execute mutations.
    """

    path = Path(file_path)

    if not path.exists():
        return TextExtractionResult(
            success=False,
            text="",
            method="none",
            reason="File does not exist.",
        )

    if not path.is_file():
        return TextExtractionResult(
            success=False,
            text="",
            method="none",
            reason="Path is not a file.",
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        return _extract_pdf(path)

    if extension in IMAGE_EXTENSIONS:
        return _extract_image(path)

    return TextExtractionResult(
        success=False,
        text="",
        method="unsupported",
        reason="Unsupported file type for text extraction.",
    )


def _extract_pdf(path: Path) -> TextExtractionResult:
    """
    Extract text from a PDF while preserving page evidence.

    Strategy:
    1. Read embedded text from every page.
    2. If the document contains enough embedded text overall, return it.
    3. Otherwise render every page and OCR it.

    Mixed per-page OCR remains a later hardening step so this performance
    refactor does not silently alter the document-reading contract.
    """

    document = None

    try:
        document = fitz.open(str(path))
        page_count = len(document)

        if page_count <= 0:
            return TextExtractionResult(
                success=False,
                text="",
                method="pdf",
                page_count=0,
                reason="PDF contains no pages.",
            )

        embedded_pages: List[str] = []

        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()

            if page_text:
                embedded_pages.append(
                    _format_page_text(
                        page_number=page_number,
                        text=page_text,
                    )
                )

        embedded_text = "\n\n".join(embedded_pages).strip()

        if len(embedded_text) >= MIN_EMBEDDED_TEXT_LENGTH:
            return TextExtractionResult(
                success=True,
                text=embedded_text,
                method="pdf_text",
                page_count=page_count,
            )

        ocr_pages: List[str] = []

        for page_number, page in enumerate(document, start=1):
            page_text = _ocr_pdf_page(page)

            if page_text:
                ocr_pages.append(
                    _format_page_text(
                        page_number=page_number,
                        text=page_text,
                    )
                )

        combined_text = "\n\n".join(ocr_pages).strip()

        if not combined_text:
            return TextExtractionResult(
                success=False,
                text="",
                method="pdf_ocr",
                page_count=page_count,
                reason=(
                    "No readable text could be extracted from the PDF."
                ),
            )

        return TextExtractionResult(
            success=True,
            text=combined_text,
            method="pdf_ocr",
            page_count=page_count,
        )

    except Exception:
        logger.exception(
            "PDF text extraction failed for staged file %s",
            path.name,
        )

        return TextExtractionResult(
            success=False,
            text="",
            method="pdf",
            reason="PDF text extraction failed.",
        )

    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                logger.exception(
                    "Failed to close PDF document %s",
                    path.name,
                )


def _extract_image(path: Path) -> TextExtractionResult:
    """
    OCR a single image file and expose it as page 1 evidence.
    """

    try:
        with Image.open(str(path)) as source_image:
            image = _apply_exif_orientation(source_image)
            text = _extract_best_orientation_text(image)
            security_text = _extract_security_ocr_text(image)

        if not text:
            return TextExtractionResult(
                success=False,
                text="",
                method="image_ocr",
                page_count=1,
                reason="No readable text found in image.",
            )

        return TextExtractionResult(
            success=True,
            text=_format_page_text(
                page_number=1,
                text=text,
            ),
            method="image_ocr",
            page_count=1,
            security_text=security_text,
        )

    except Exception:
        logger.exception(
            "Image OCR failed for staged file %s",
            path.name,
        )

        return TextExtractionResult(
            success=False,
            text="",
            method="image_ocr",
            page_count=1,
            reason="Image OCR failed.",
        )


def _ocr_pdf_page(page: fitz.Page) -> str:
    """
    Render one PDF page and OCR the rendered image.
    """

    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(
            PDF_RENDER_SCALE,
            PDF_RENDER_SCALE,
        ),
        alpha=False,
    )

    image = Image.frombytes(
        "RGB",
        (
            pixmap.width,
            pixmap.height,
        ),
        pixmap.samples,
    )

    return _extract_best_orientation_text(image)


def _extract_best_orientation_text(
    image: Image.Image,
) -> str:
    """
    OCR the normal orientation first and rotate only when necessary.

    The previous implementation OCRed 0/90/180/270 degrees for every image.
    This implementation keeps that fallback for difficult/rotated documents,
    but returns after the first pass when enough readable text is found.
    """

    if image.mode != "RGB":
        image = image.convert("RGB")

    first_text = _easyocr_image(image)

    if _ocr_text_is_sufficient(first_text):
        return first_text.strip()

    best_text = first_text

    for angle in (90, 180, 270):
        candidate = image.rotate(angle, expand=True)
        text = _easyocr_image(candidate)

        if _ocr_quality_score(text) > _ocr_quality_score(best_text):
            best_text = text

        if _ocr_text_is_sufficient(best_text):
            # Once a fallback orientation produces clearly usable text, avoid
            # paying for additional OCR passes.
            break

    return best_text.strip()


def _ocr_text_is_sufficient(text: str) -> bool:
    clean_text = " ".join((text or "").split())

    if len(clean_text) < MIN_ORIENTATION_TEXT_LENGTH:
        return False

    return len(clean_text.split()) >= MIN_ORIENTATION_WORDS


def _ocr_quality_score(text: str) -> int:
    """
    Lightweight deterministic score for comparing orientation candidates.
    """

    clean_text = " ".join((text or "").split())
    word_count = len(clean_text.split())
    alphanumeric_count = sum(
        1
        for char in clean_text
        if char.isalnum()
    )

    return (word_count * 10) + alphanumeric_count


def _preprocess_image(
    image: Image.Image,
) -> Image.Image:
    """
    Apply simple deterministic preprocessing before OCR.
    """

    grayscale = image.convert("L")

    return grayscale.point(
        lambda pixel: 0 if pixel < 180 else 255
    )


def _extract_security_ocr_text(
    image: Image.Image,
) -> str:
    """Return low-confidence OCR solely for injection detection.

    The primary OCR applies a binary threshold and discards low-confidence
    text to protect document facts from noise. Handwritten attack text can be
    faint enough to disappear under those rules, so this independent pass
    uses grayscale autocontrast and a much lower confidence floor. Callers
    must not expose, persist, classify, summarize, or derive actions from this
    value.
    """

    grayscale = ImageOps.grayscale(image)
    processed_image = ImageOps.autocontrast(grayscale)
    image_array = np.array(processed_image)

    with _OCR_LOCK:
        results = _OCR_READER.readtext(
            image_array,
            detail=1,
            paragraph=False,
        )

    lines: List[str] = []

    for _box, text, confidence in results:
        normalized_text = str(text).strip()
        if not normalized_text:
            continue

        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0

        if confidence_value < SECURITY_OCR_CONFIDENCE_THRESHOLD:
            continue

        lines.append(normalized_text)

    return "\n".join(lines).strip()


def _easyocr_image(
    image: Image.Image,
) -> str:
    """
    Run EasyOCR on a PIL image and discard very low-confidence OCR noise.
    """

    processed_image = _preprocess_image(image)
    image_array = np.array(processed_image)

    with _OCR_LOCK:
        results = _OCR_READER.readtext(
            image_array,
            detail=1,
            paragraph=False,
        )

    lines: List[str] = []

    for result in results:
        # EasyOCR detail=1 returns:
        # (bounding_box, text, confidence)
        _, text, confidence = result

        normalized_text = str(text).strip()

        if not normalized_text:
            continue

        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0

        if confidence_value < OCR_CONFIDENCE_THRESHOLD:
            continue

        lines.append(normalized_text)

    return "\n".join(lines).strip()


def _apply_exif_orientation(
    image: Image.Image,
) -> Image.Image:
    """
    Apply EXIF orientation information when available.

    A copy is returned so the image remains valid after the source image's
    context manager closes.
    """

    try:
        corrected = ImageOps.exif_transpose(image)
        return corrected.copy()
    except Exception:
        logger.exception(
            "Unable to apply EXIF orientation; continuing with original "
            "image."
        )
        return image.copy()


def _format_page_text(
    page_number: int,
    text: str,
) -> str:
    """
    Format extracted text with the stable page marker used by the document
    proposal/evidence pipeline.
    """

    clean_text = text.strip()

    return "--- Page {0} ---\n{1}".format(
        page_number,
        clean_text,
    )
