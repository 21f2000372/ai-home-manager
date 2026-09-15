"""SQLAlchemy engine, session factory, and declarative Base.

For SQLite we enable foreign-key enforcement and WAL journaling on every
connection (SQLite has these off / in rollback mode by default). These
pragmas mirror the settings recommended in the backend design docs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, mapped_column, sessionmaker

from app.config import config


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _uuid_str() -> str:
    """Generate a string UUID primary key (portable across SQLite/Postgres)."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Timezone-aware UTC now, used as a default for timestamp columns."""
    return datetime.now(timezone.utc)


# --- Engine ---------------------------------------------------------------

# check_same_thread=False lets the engine be shared across Flask request
# threads. SQLite still serializes writers, which is fine for this MVP.
_is_sqlite = config.DATABASE_URL.startswith("sqlite")
engine: Engine = create_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Apply SQLite pragmas on each new connection.

    No-op for non-SQLite engines (e.g. a future Postgres migration).
    """
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.close()


# --- Session --------------------------------------------------------------

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session():
    """Return a new SQLAlchemy session. Caller is responsible for closing."""
    return SessionLocal()
