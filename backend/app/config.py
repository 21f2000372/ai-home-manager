"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from typing import Optional

# Project root = backend folder
BASE_DIR = Path(__file__).resolve().parent.parent


# Explicitly load:
# backend/.env
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)


class Config:
    """Central configuration object."""

    # =========================
    # Flask
    # =========================

    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-secret-change-me",
    )

    FLASK_ENV: str = os.getenv(
        "FLASK_ENV",
        "development",
    )

    # =========================
    # Auth / JWT
    # =========================

    JWT_SECRET: str = os.getenv(
        "JWT_SECRET",
        "dev-jwt-change-me",
    )

    JWT_EXPIRES_MINUTES: int = int(
        os.getenv(
            "JWT_EXPIRES_MINUTES",
            "1440",
        )
    )

    # =========================
    # Database
    # =========================

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'ai_home_manager.db'}",
    )

    # =========================
    # LLM / OpenRouter
    # =========================

    OPENROUTER_API_KEY: str = os.getenv(
        "OPENROUTER_API_KEY",
        "",
    )

    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )

    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL",
        "openai/gpt-4o-mini",
    )

    # =========================
    # RAG / Chroma
    # =========================

    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        str(BASE_DIR / "chroma_store"),
    )

    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    # =========================
    # Cloudinary
    # =========================

    CLOUDINARY_CLOUD_NAME: Optional[str] = os.getenv(
        "CLOUDINARY_CLOUD_NAME"
    )

    CLOUDINARY_API_KEY: Optional[str] = os.getenv(
        "CLOUDINARY_API_KEY"
    )

    CLOUDINARY_API_SECRET: Optional[str] = os.getenv(
        "CLOUDINARY_API_SECRET"
    )

    CLOUDINARY_FOLDER: str = os.getenv(
        "CLOUDINARY_FOLDER",
        "ai-home-manager/documents",
    )

    DOCUMENT_STORAGE_PROVIDER: str = os.getenv(
        "DOCUMENT_STORAGE_PROVIDER",
        "cloudinary",
    ).strip().lower()

    LOCAL_DOCUMENT_STORAGE_DIR: str = os.getenv(
        "LOCAL_DOCUMENT_STORAGE_DIR",
        str(BASE_DIR / "document_store"),
    )

    # 15 MB
    MAX_UPLOAD_BYTES: int = int(
        os.getenv(
            "MAX_UPLOAD_BYTES",
            "15728640",
        )
    )

    TEMP_UPLOAD_DIR: str = os.getenv(
        "TEMP_UPLOAD_DIR",
        str(BASE_DIR / ".pending_uploads"),
    )

config = Config()