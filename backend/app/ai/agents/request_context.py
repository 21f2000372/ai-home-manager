"""Authenticated identity context for one agent invocation.

Only the HTTP route may bind this context. Agent tools read it instead of
accepting user_id or role from model-generated arguments.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from app.models.enums import HouseholdRole


class AgentRequestContextError(RuntimeError):
    """Raised when authenticated agent identity is unavailable or invalid."""


@dataclass(frozen=True)
class AgentRequestIdentity:
    """Server-verified identity available to tools during one agent run."""

    user_id: str
    role: str


_agent_user_id: ContextVar[Optional[str]] = ContextVar(
    "agent_request_user_id",
    default=None,
)
_agent_role: ContextVar[Optional[str]] = ContextVar(
    "agent_request_role",
    default=None,
)


def _validated_user_id(value: Any) -> str:
    if not isinstance(value, str):
        raise AgentRequestContextError(
            "Authenticated agent identity is required."
        )

    cleaned = value.strip()
    if (
        not cleaned
        or cleaned != value
        or len(cleaned) > 36
        or any(
            character.isspace()
            or not character.isprintable()
            for character in cleaned
        )
    ):
        raise AgentRequestContextError(
            "Authenticated agent identity is required."
        )

    return cleaned


def _validated_role(value: Any) -> str:
    try:
        parsed = (
            value
            if isinstance(value, HouseholdRole)
            else HouseholdRole(value)
        )
    except (TypeError, ValueError):
        raise AgentRequestContextError(
            "Authenticated agent role is required."
        ) from None

    return str(parsed.value)


def set_agent_request_identity(
    user_id: str,
    role: Any,
) -> Tuple[Token, Token]:
    """Bind verified identity and return tokens required for exact reset."""

    scoped_user_id = _validated_user_id(user_id)
    scoped_role = _validated_role(role)

    user_token = _agent_user_id.set(scoped_user_id)
    try:
        role_token = _agent_role.set(scoped_role)
    except Exception:
        _agent_user_id.reset(user_token)
        raise

    return user_token, role_token


def reset_agent_request_identity(
    tokens: Tuple[Token, Token],
) -> None:
    """Restore the context that existed before the matching bind call."""

    if (
        not isinstance(tokens, tuple)
        or len(tokens) != 2
    ):
        raise AgentRequestContextError(
            "Agent request context reset token is invalid."
        )

    user_token, role_token = tokens
    _agent_role.reset(role_token)
    _agent_user_id.reset(user_token)


def get_agent_request_identity() -> AgentRequestIdentity:
    """Return verified identity or fail closed outside an agent invocation."""

    user_id = _agent_user_id.get()
    role = _agent_role.get()

    if user_id is None or role is None:
        raise AgentRequestContextError(
            "Authenticated agent identity is unavailable."
        )

    return AgentRequestIdentity(
        user_id=_validated_user_id(user_id),
        role=_validated_role(role),
    )
