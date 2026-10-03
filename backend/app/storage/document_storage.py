"""Provider selection for permanent document storage and view links."""
from __future__ import annotations

from typing import Any

from flask import url_for
from itsdangerous import URLSafeTimedSerializer

from app.config import config
from app.storage import cloudinary_storage, local_storage


SUPPORTED_DOCUMENT_STORAGE_PROVIDERS = {"cloudinary", "local"}
LOCAL_VIEW_TOKEN_SALT = "document-local-view-v1"
LOCAL_VIEW_TOKEN_MAX_AGE = 300


def _provider() -> str:
    provider = config.DOCUMENT_STORAGE_PROVIDER
    if provider not in SUPPORTED_DOCUMENT_STORAGE_PROVIDERS:
        raise ValueError(
            "DOCUMENT_STORAGE_PROVIDER must be 'cloudinary' or 'local'."
        )
    return provider


def upload_file(
    file_path: str,
    *,
    folder: str | None = None,
    public_id: str | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    provider = _provider()
    if provider == "local":
        return local_storage.upload_file(
            file_path,
            folder=folder,
            public_id=public_id,
            overwrite=overwrite,
        )

    result = cloudinary_storage.upload_file(
        file_path,
        folder=folder,
        public_id=public_id,
        overwrite=overwrite,
    )
    cloudinary_key = str(result.get("public_id") or "").strip()
    if not cloudinary_key:
        raise ValueError("Cloudinary did not return a document key.")
    result["public_id"] = f"cloudinary:{cloudinary_key}"
    return result


def _local_view_url(payload: dict[str, Any]) -> str:
    serializer = URLSafeTimedSerializer(
        config.SECRET_KEY,
        salt=LOCAL_VIEW_TOKEN_SALT,
    )
    token = serializer.dumps(payload)
    return url_for("documents.serve_local_document", token=token, _external=True)


def document_view_url(
    storage_key: str,
    file_format: str,
    *,
    document_id: str,
    filename: str,
    mime_type: str | None,
    role: str,
    user_id: str | None,
    inline: bool,
) -> str:
    key = str(storage_key or "")
    if key.startswith("local:"):
        return _local_view_url({
            "kind": "document",
            "document_id": document_id,
            "storage_key": key,
            "filename": filename,
            "mime_type": mime_type,
            "role": role,
            "user_id": user_id,
            "inline": inline,
        })

    cloudinary_key = key.removeprefix("cloudinary:")
    if not inline:
        return cloudinary_storage.generate_download_url(
            cloudinary_key,
            file_format,
            resource_type="image",
        )
    return cloudinary_storage.generate_view_url(
        cloudinary_key,
        file_format,
        resource_type="image",
    )


def pending_view_url(*, pending_id: str, user_id: str) -> str:
    return _local_view_url({
        "kind": "pending",
        "pending_id": pending_id,
        "user_id": user_id,
    })


def load_local_view_token(token: str) -> dict[str, Any]:
    serializer = URLSafeTimedSerializer(
        config.SECRET_KEY,
        salt=LOCAL_VIEW_TOKEN_SALT,
    )
    payload = serializer.loads(token, max_age=LOCAL_VIEW_TOKEN_MAX_AGE)
    if not isinstance(payload, dict):
        raise ValueError("Invalid document view link.")
    return payload