from __future__ import annotations

import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.config import BASE_DIR, config


def get_temp_upload_dir() -> Path:
    """
    Return the temporary upload directory.
    Create it if it does not exist.
    """

    temp_dir = Path(config.TEMP_UPLOAD_DIR)

    if not temp_dir.is_absolute():
        temp_dir = BASE_DIR / temp_dir

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return temp_dir


def save_temp_upload(
    uploaded_file: FileStorage,
) -> dict:
    """
    Save an uploaded Flask file temporarily.

    Nothing is uploaded to Cloudinary here.
    """

    if uploaded_file is None:
        raise ValueError(
            "No uploaded file was provided."
        )

    original_filename = uploaded_file.filename or ""

    safe_filename = secure_filename(
        original_filename
    )

    if not safe_filename:
        raise ValueError(
            "Invalid filename."
        )

    upload_id = str(uuid.uuid4())

    temp_dir = get_temp_upload_dir()

    stored_filename = (
        f"{upload_id}_{safe_filename}"
    )

    temp_path = temp_dir / stored_filename

    uploaded_file.save(
        str(temp_path)
    )

    return {
        "upload_id": upload_id,
        "original_filename": original_filename,
        "safe_filename": safe_filename,
        "temp_path": str(temp_path),
    }


def delete_temp_file(
    file_path: str,
) -> None:
    """
    Delete a temporary uploaded file.
    """

    path = Path(file_path)

    if path.exists():
        path.unlink()