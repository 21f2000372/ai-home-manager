from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import easyocr
import fitz
import numpy as np
from PIL import Image
from typing import Optional

@dataclass
class TextExtractionResult:
    success: bool
    text: str
    method: str
    page_count: int = 1
    reason: Optional[str] = None


# Create the OCR reader only once.
# gpu=False keeps this compatible with normal laptops/servers.
_OCR_READER = easyocr.Reader(
    ["en"],
    gpu=False,
)


def extract_text(file_path: str) -> TextExtractionResult:
    """
    Extract text from a supported staged file.

    Supported:
    - PDF
    - JPG / JPEG
    - PNG
    - WEBP

    PDF flow:
    1. Try normal embedded PDF text.
    2. If the PDF appears scanned, render pages and use EasyOCR.

    Image flow:
    1. Correct EXIF orientation where possible.
    2. Try 0°, 90°, 180°, 270°.
    3. Keep the orientation that produces the most OCR text.
    """

    path = Path(file_path)

    if not path.exists():
        return TextExtractionResult(
            success=False,
            text="",
            method="none",
            reason="File does not exist.",
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        return _extract_pdf(path)

    if extension in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        return _extract_image(path)

    return TextExtractionResult(
        success=False,
        text="",
        method="unsupported",
        reason="Unsupported file type for text extraction.",
    )


def _extract_pdf(path: Path) -> TextExtractionResult:
    """
    Extract text from a PDF.

    If useful embedded text exists, return it directly.
    Otherwise OCR each rendered page.
    """

    try:
        document = fitz.open(path)

        page_count = len(document)

        embedded_pages: list[str] = []

        for page in document:
            text = page.get_text("text").strip()

            if text:
                embedded_pages.append(text)

        embedded_text = "\n\n".join(
            embedded_pages
        ).strip()

        # If enough text was extracted directly,
        # don't waste time doing OCR.
        if len(embedded_text) >= 30:
            document.close()

            return TextExtractionResult(
                success=True,
                text=embedded_text,
                method="pdf_text",
                page_count=page_count,
            )

        # Otherwise OCR the PDF pages.
        ocr_pages: list[str] = []

        for page_number, page in enumerate(
            document,
            start=1,
        ):
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
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

            page_text = _extract_best_orientation_text(
                image
            )

            if page_text:
                ocr_pages.append(
                    f"--- Page {page_number} ---\n{page_text}"
                )

        document.close()

        combined_text = "\n\n".join(
            ocr_pages
        ).strip()

        if not combined_text:
            return TextExtractionResult(
                success=False,
                text="",
                method="pdf_ocr",
                page_count=page_count,
                reason="No readable text could be extracted from the PDF.",
            )

        return TextExtractionResult(
            success=True,
            text=combined_text,
            method="pdf_ocr",
            page_count=page_count,
        )

    except Exception as exc:
        return TextExtractionResult(
            success=False,
            text="",
            method="pdf",
            reason=f"PDF extraction failed: {exc}",
        )


def _extract_image(path: Path) -> TextExtractionResult:
    """
    OCR an image file.
    """

    try:
        with Image.open(path) as image:
            image = _apply_exif_orientation(
                image
            )

            text = _extract_best_orientation_text(
                image
            )

        if not text:
            return TextExtractionResult(
                success=False,
                text="",
                method="image_ocr",
                reason="No readable text found in image.",
            )

        return TextExtractionResult(
            success=True,
            text=text,
            method="image_ocr",
            page_count=1,
        )

    except Exception as exc:
        return TextExtractionResult(
            success=False,
            text="",
            method="image_ocr",
            reason=f"Image OCR failed: {exc}",
        )


def _extract_best_orientation_text(
    image: Image.Image,
) -> str:
    """
    OCR an image in four orientations and keep
    the orientation that gives the most text.
    """

    if image.mode != "RGB":
        image = image.convert("RGB")

    candidates = [
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

    best_text = ""

    for candidate in candidates:
        text = _easyocr_image(
            candidate
        )

        if len(text) > len(best_text):
            best_text = text

    return best_text.strip()

def _preprocess_image(
    image: Image.Image,
) -> Image.Image:
    """
    Basic preprocessing to improve OCR quality.
    """

    # Convert to grayscale
    image = image.convert("L")

    # Increase contrast using a simple threshold
    image = image.point(
        lambda pixel: 0 if pixel < 180 else 255
    )

    return image
def _easyocr_image(
    image: Image.Image,
) -> str:
    """
    Run EasyOCR on a PIL image.
    """

    image = _preprocess_image(image)
    image_array = np.array(image)
    results = _OCR_READER.readtext(
        image_array,
        detail=1,
        paragraph=False,
    )

    lines: list[str] = []

    for result in results:
        # EasyOCR detail=1 returns:
        #
        # (
        #     bounding_box,
        #     text,
        #     confidence,
        # )

        _, text, confidence = result

        text = text.strip()

        if not text:
            continue

        # Ignore very uncertain OCR noise.
        if confidence < 0.20:
            continue

        lines.append(text)

    return "\n".join(lines)


def _apply_exif_orientation(
    image: Image.Image,
) -> Image.Image:
    """
    Apply EXIF orientation information when available.
    """

    try:
        from PIL import ImageOps

        return ImageOps.exif_transpose(
            image
        )

    except Exception:
        return image