"""Database initialization helpers.

``create_all`` builds the full schema on the configured engine. Importing
``app.models`` registers every table on ``Base.metadata`` first.
"""

from __future__ import annotations

from app.db.base import Base, engine
import app.models  # noqa: F401  (import registers all models on Base.metadata)


def create_all() -> None:
    """Create every table that does not already exist."""
    Base.metadata.create_all(bind=engine)


def drop_all() -> None:
    """Drop every known table. Destructive; used for a clean rebuild."""
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    create_all()
    print("Database schema created.")
