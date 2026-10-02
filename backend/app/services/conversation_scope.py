"""Ownership checks for agent conversations and sessions.

Compatible with Python 3.9.

The frontend may omit conversation_id and session_id independently.
Authenticated identity must come from server-side context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.documents import Conversation


class ConversationScopeError(ValueError):
    """An error with a safe message and HTTP status."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.public_message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ConversationScope:
    """Verified identifiers for an authenticated user's conversation."""

    user_id: str
    conversation_id: str
    session_id: str


def _optional_identifier(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> Optional[str]:
    """Accept omitted/null IDs and reject malformed supplied IDs."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise ConversationScopeError(
            "{} must be a string or null.".format(field),
            400,
        )

    value = value.strip()

    if not value:
        raise ConversationScopeError(
            "{} must not be empty; omit it or use null.".format(field),
            400,
        )

    if len(value) > max_length:
        raise ConversationScopeError(
            "{} is too long.".format(field),
            400,
        )

    if any(
        character.isspace() or not character.isprintable()
        for character in value
    ):
        raise ConversationScopeError(
            "{} contains invalid characters.".format(field),
            400,
        )

    return value


def _authenticated_user_id(value: Any) -> str:
    """Fail closed when authenticated server-side identity is missing."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 36
        or any(
            character.isspace() or not character.isprintable()
            for character in value
        )
    ):
        raise ConversationScopeError(
            "Authenticated user identity is required.",
            401,
        )

    return value


def _unavailable() -> ConversationScopeError:
    """Avoid revealing whether an inaccessible identifier exists."""

    return ConversationScopeError(
        "Conversation or session is unavailable.",
        404,
    )


def _scope_from_row(
    row: Conversation,
    *,
    user_id: str,
) -> ConversationScope:
    """Validate ownership and identifiers on an existing database row."""

    if row.user_id != user_id:
        raise _unavailable()

    try:
        conversation_id = _optional_identifier(
            row.conversation_id,
            field="conversation_id",
            max_length=36,
        )
        session_id = _optional_identifier(
            row.session_id,
            field="session_id",
            max_length=100,
        )
    except ConversationScopeError:
        raise _unavailable() from None

    if conversation_id is None or session_id is None:
        raise _unavailable()

    return ConversationScope(
        user_id=user_id,
        conversation_id=conversation_id,
        session_id=session_id,
    )


def require_owned_conversation(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    session_id: Optional[str] = None,
) -> ConversationScope:
    """Verify an existing conversation and its optional session ID.

    The caller owns the database session and transaction.
    This function does not create, commit, or modify records.
    """

    owner_id = _authenticated_user_id(user_id)

    requested_conversation = _optional_identifier(
        conversation_id,
        field="conversation_id",
        max_length=36,
    )
    requested_session = _optional_identifier(
        session_id,
        field="session_id",
        max_length=100,
    )

    if requested_conversation is None:
        raise _unavailable()

    row = (
        db.query(Conversation)
        .filter(
            Conversation.conversation_id == requested_conversation,
            Conversation.user_id == owner_id,
        )
        .one_or_none()
    )

    if row is None:
        raise _unavailable()

    scope = _scope_from_row(row, user_id=owner_id)

    if (
        requested_session is not None
        and requested_session != scope.session_id
    ):
        raise _unavailable()

    return scope


def resolve_conversation_scope(
    *,
    user_id: str,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> ConversationScope:
    """Resolve optional frontend identifiers before agent execution.

    Neither identifier:
        Create a conversation and session with server-generated UUIDs.

    Conversation identifier only:
        Verify ownership and recover the stored session identifier.

    Session identifier only:
        Resolve exactly one conversation owned by the caller.

    Both identifiers:
        Verify ownership and require the stored session to match.

    Unknown identifiers are rejected rather than silently creating or
    switching conversations.

    This function owns its database session. New conversations are
    committed before returning so workflow records may reference them.
    """

    owner_id = _authenticated_user_id(user_id)

    requested_conversation = _optional_identifier(
        conversation_id,
        field="conversation_id",
        max_length=36,
    )
    requested_session = _optional_identifier(
        session_id,
        field="session_id",
        max_length=100,
    )

    db = SessionLocal()

    try:
        if requested_conversation is not None:
            return require_owned_conversation(
                db,
                user_id=owner_id,
                conversation_id=requested_conversation,
                session_id=requested_session,
            )

        if requested_session is not None:
            rows = (
                db.query(Conversation)
                .filter(
                    Conversation.session_id == requested_session,
                    Conversation.user_id == owner_id,
                )
                .limit(2)
                .all()
            )

            if not rows:
                raise _unavailable()

            if len(rows) > 1:
                raise ConversationScopeError(
                    "This session contains multiple conversations. "
                    "Provide a conversation_id.",
                    409,
                )

            return _scope_from_row(rows[0], user_id=owner_id)

        row = Conversation(
            conversation_id=str(uuid4()),
            session_id=str(uuid4()),
            user_id=owner_id,
        )

        db.add(row)
        db.flush()

        scope = _scope_from_row(row, user_id=owner_id)
        db.commit()

        return scope

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()