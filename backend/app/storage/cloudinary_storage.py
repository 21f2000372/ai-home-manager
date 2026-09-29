from __future__ import annotations

from pathlib import Path
from typing import Any

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from typing import List, Optional
from app.config import config
from app.rag.file_validation import validate_file

def configure_cloudinary() -> None:
    """Configure the Cloudinary Python SDK."""

    if not config.CLOUDINARY_CLOUD_NAME:
        raise RuntimeError(
            "CLOUDINARY_CLOUD_NAME is missing."
        )

    if not config.CLOUDINARY_API_KEY:
        raise RuntimeError(
            "CLOUDINARY_API_KEY is missing."
        )

    if not config.CLOUDINARY_API_SECRET:
        raise RuntimeError(
            "CLOUDINARY_API_SECRET is missing."
        )

    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_file(
    file_path: str,
    *,
    folder: Optional[str] = None,
) -> dict[str, Any]:
    """
    Upload a document or image as an authenticated Cloudinary asset.

    The uploaded file is private and is not publicly accessible.
    """

    configure_cloudinary()

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File does not exist: {file_path}"
        )

    upload_folder = (
        folder
        or config.CLOUDINARY_FOLDER
    )

    result = cloudinary.uploader.upload(
        str(path),
        folder=upload_folder,
        resource_type="auto",
        type="authenticated",
    )

    return {
        "public_id": result.get("public_id"),
        "asset_id": result.get("asset_id"),
        "resource_type": result.get("resource_type"),
        "type": result.get("type"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
        "original_filename": result.get(
            "original_filename"
        ),
    }

def validate_and_upload_file(file_path: str) -> dict:
    """
    Validate a local file first.

    Only valid PDF/image files are uploaded to Cloudinary.
    """

    validation = validate_file(file_path)

    if not validation.valid:
        return {
            "success": False,
            "uploaded": False,
            "reason": validation.reason,
            "filename": validation.filename,
        }

    upload_result = upload_file(file_path)

    return {
        "success": True,
        "uploaded": True,
        "validation": {
            "filename": validation.filename,
            "extension": validation.extension,
            "mime_type": validation.mime_type,
            "file_size": validation.file_size,
        },
        "cloudinary": upload_result,
    }
def generate_download_url(
    public_id: str,
    file_format: str,
    *,
    resource_type: str = "image",
) -> str:
    """
    Generate a signed Cloudinary download URL.

    The caller should perform authorization checks
    before calling this function.
    """

    configure_cloudinary()

    return cloudinary.utils.private_download_url(
        public_id,
        file_format,
        resource_type=resource_type,
        type="authenticated",
    )


def delete_file(
    public_id: str,
    *,
    resource_type: str = "image",
) -> dict[str, Any]:
    """
    Delete an authenticated asset from Cloudinary.
    """

    configure_cloudinary()

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type=resource_type,
        type="authenticated",
        invalidate=True,
    )

    return {
        "result": result.get("result"),
    }