from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from app.config import config


logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

ALLOWED_IMAGE_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
}


@dataclass
class FileValidationResult:
    valid: bool
    filename: str
    extension: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: int = 0
    reason: Optional[str] = None


def validate_file(file_path: str) -> FileValidationResult:
    """
    Validate a local file before processing or Cloudinary upload.

    Checks:
    - file exists
    - file is not empty
    - file size limit
    - allowed extension
    - actual PDF/image content
    """

    path = Path(file_path)

    # -------------------------
    # File exists
    # -------------------------

    if not path.exists():
        return FileValidationResult(
            valid=False,
            filename=path.name,
            reason="File does not exist.",
        )

    # -------------------------
    # File size
    # -------------------------

    file_size = path.stat().st_size

    if file_size == 0:
        return FileValidationResult(
            valid=False,
            filename=path.name,
            file_size=0,
            reason="File is empty.",
        )

    if file_size > config.MAX_UPLOAD_BYTES:
        return FileValidationResult(
            valid=False,
            filename=path.name,
            file_size=file_size,
            reason="File exceeds maximum upload size.",
        )

    # -------------------------
    # Extension
    # -------------------------

    extension = path.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return FileValidationResult(
            valid=False,
            filename=path.name,
            extension=extension,
            file_size=file_size,
            reason="Unsupported file type.",
        )

    # -------------------------
    # PDF validation
    # -------------------------

    if extension == ".pdf":
        return _validate_pdf(
            path=path,
            file_size=file_size,
        )

    # -------------------------
    # Image validation
    # -------------------------

    return _validate_image(
        path=path,
        file_size=file_size,
    )


def _validate_pdf(
    path: Path,
    file_size: int,
) -> FileValidationResult:
    """
    Check whether the file really looks like a PDF.
    """

    try:
        with path.open("rb") as file:
            header = file.read(5)

        if header != b"%PDF-":
            return FileValidationResult(
                valid=False,
                filename=path.name,
                extension=".pdf",
                file_size=file_size,
                reason="File extension is PDF but content is not a valid PDF.",
            )

        return FileValidationResult(
            valid=True,
            filename=path.name,
            extension=".pdf",
            mime_type="application/pdf",
            file_size=file_size,
        )

    except Exception:
        logger.exception(
            "PDF content validation failed for %s",
            path.name,
        )
        return FileValidationResult(
            valid=False,
            filename=path.name,
            extension=".pdf",
            file_size=file_size,
            reason="The PDF could not be read safely.",
        )


def _validate_image(
    path: Path,
    file_size: int,
) -> FileValidationResult:
    """
    Verify that the file is actually a readable image.
    """

    try:
        with Image.open(path) as image:
            image.verify()
            actual_format = image.format

        if actual_format not in ALLOWED_IMAGE_FORMATS:
            return FileValidationResult(
                valid=False,
                filename=path.name,
                extension=path.suffix.lower(),
                file_size=file_size,
                reason=f"Unsupported image format: {actual_format}",
            )

        mime_map = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }

        return FileValidationResult(
            valid=True,
            filename=path.name,
            extension=path.suffix.lower(),
            mime_type=mime_map.get(actual_format),
            file_size=file_size,
        )

    except Exception:
        return FileValidationResult(
            valid=False,
            filename=path.name,
            extension=path.suffix.lower(),
            file_size=file_size,
            reason="File is not a valid image.",
        )
