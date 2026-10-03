"""Private Cloudinary storage helpers for AI Home Manager.

Step 8B adds deterministic public IDs so an archive upload is replay-safe: if
the process stops after Cloudinary accepted the file but before the database
transaction commits, a retry overwrites the same private asset instead of
creating a second copy.

Compatibility target: Python 3.8+.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from app.config import config
from app.rag.file_validation import validate_file


class CloudinaryConfigurationError(RuntimeError):
    """Raised when private Cloudinary storage credentials are unavailable."""


def configure_cloudinary() -> None:
    """Configure the Cloudinary Python SDK."""

    missing = [
        name
        for name, value in (
            ("CLOUDINARY_CLOUD_NAME", config.CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", config.CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", config.CLOUDINARY_API_SECRET),
        )
        if not value
    ]
    if missing:
        raise CloudinaryConfigurationError(
            "Document storage is not configured. Set "
            + ", ".join(missing)
            + " in backend/.env."
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
    public_id: Optional[str] = None,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """Upload a document/image as an authenticated Cloudinary asset.

    ``public_id`` may be supplied by a durable workflow to make an external
    upload idempotent across retries.  The file remains authenticated/private.
    """

    configure_cloudinary()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(
            "File does not exist: {0}".format(file_path)
        )

    upload_folder = folder or config.CLOUDINARY_FOLDER

    kwargs: Dict[str, Any] = {
        "folder": upload_folder,
        "resource_type": "auto",
        "type": "authenticated",
        "overwrite": bool(overwrite),
    }

    if public_id:
        kwargs["public_id"] = str(public_id)
        kwargs["unique_filename"] = False
        kwargs["use_filename"] = False

    result = cloudinary.uploader.upload(
        str(path),
        **kwargs
    )

    return {
        "public_id": result.get("public_id"),
        "asset_id": result.get("asset_id"),
        "resource_type": result.get("resource_type"),
        "type": result.get("type"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
        "original_filename": result.get("original_filename"),
    }


def validate_and_upload_file(file_path: str) -> Dict[str, Any]:
    """Validate a local file before uploading it to private storage."""

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
    """Generate a signed download URL after caller-side authorization."""

    configure_cloudinary()

    return cloudinary.utils.private_download_url(
        public_id,
        file_format,
        resource_type=resource_type,
        type="authenticated",
    )


def generate_view_url(
    public_id: str,
    file_format: str,
    *,
    resource_type: str = "image",
) -> str:
    """Generate a signed authenticated delivery URL for inline viewing."""

    configure_cloudinary()
    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        format=file_format,
        resource_type=resource_type,
        type="authenticated",
        sign_url=True,
        secure=True,
    )
    return str(url)


def delete_file(
    public_id: str,
    *,
    resource_type: str = "image",
) -> Dict[str, Any]:
    """Delete an authenticated Cloudinary asset."""

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
