"""Private local storage for approved household documents."""
from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import BASE_DIR, config
from app.rag.file_validation import ALLOWED_EXTENSIONS


_LOCAL_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+\.(?:pdf|jpg|jpeg|png|webp)$")


def get_local_document_dir() -> Path:
    root = Path(config.LOCAL_DOCUMENT_STORAGE_DIR)
    if not root.is_absolute():
        root = BASE_DIR / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def upload_file(
    file_path: str,
    *,
    folder: str | None = None,
    public_id: str | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Copy a validated staged file into private persistent local storage."""
    source = Path(file_path)
    if not source.is_file():
        raise FileNotFoundError("Document source file does not exist.")
    extension = source.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported document file type.")

    asset_id = public_id or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id):
        raise ValueError("Invalid local document identifier.")

    root = get_local_document_dir()
    destination = (root / f"{asset_id}{extension}").resolve()
    if destination.parent != root:
        raise ValueError("Invalid local document destination.")
    if destination.exists() and not overwrite:
        raise FileExistsError("Document already exists in local storage.")

    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "public_id": f"local:{destination.name}",
        "asset_id": None,
        "resource_type": "local",
        "type": "private",
        "format": extension.lstrip("."),
        "bytes": destination.stat().st_size,
        "original_filename": source.name,
    }


def resolve_local_document(storage_key: str) -> Path:
    """Resolve a local storage key while rejecting traversal and symlinks."""
    key = str(storage_key or "")
    if key.startswith("local:"):
        key = key[6:]
    filename = PurePosixPath(key).name
    if filename != key or not _LOCAL_KEY_RE.fullmatch(filename):
        raise ValueError("Invalid local document key.")

    root = get_local_document_dir()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise FileNotFoundError("Document file is unavailable.")
    return path