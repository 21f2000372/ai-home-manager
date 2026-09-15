"""Application configuration loaded from environment variables.

Values default to sensible development settings so the database and RAG
scaffold can be built and run without a fully populated ``.env``. Copy
``.env.example`` to ``.env`` and fill in real secrets before any real use.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    # Optional: load a local .env if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at import time
    pass


# Project root = the directory that contains this app/ package's parent.
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Central configuration object.

    Read attributes off an instance (``Config()``) or the class directly.
    """

    # --- Flask ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

    # --- Auth (JWT) ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-jwt-change-me")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))

    # --- Database ---
    # Default to a SQLite file at the project root.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'ai_home_manager.db'}"
    )

    # --- LLM via OpenRouter ---
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    # --- RAG / Vector store ---
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_store")
    )
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


config = Config()
