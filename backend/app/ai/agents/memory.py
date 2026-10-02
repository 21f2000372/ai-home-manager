"""Conversation persistence and owner-scoped retrieval.

SQLite is the system of record. Semantic memory is best effort and is
queried only when the current request depends on previous conversation.

All reads, writes, and embeddings are scoped to the authenticated user,
conversation, and session.

Compatible with Python 3.9.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.documents import AgentInteraction
from app.services.conversation_scope import (
    ConversationScope,
    require_owned_conversation,
)


logger = logging.getLogger(__name__)

MAX_CONTEXT_ITEMS = 4
MAX_CONTEXT_CHARS = 4800
MAX_CONTEXT_ITEM_CHARS = 1600
RECENT_CONTEXT_LIMIT = 3
SEMANTIC_CONTEXT_LIMIT = 3


_CONTEXT_PATTERNS = (
    re.compile(
        r"\b(it|that|this|them|those|these|one|ones)\b",
        re.I,
    ),
    re.compile(
        r"\b(previous|earlier|before|again|same|prior|"
        r"another|more|also)\b",
        re.I,
    ),
    re.compile(
        r"\b(last one|last time|the last|the previous)\b",
        re.I,
    ),
    re.compile(
        r"\b(continue|continuing|follow up|follow-up)\b",
        re.I,
    ),
    re.compile(
        r"\b(what did i|what was i|what were we|"
        r"what did we)\b",
        re.I,
    ),
    re.compile(
        r"\b(what about|how about)\b",
        re.I,
    ),
    re.compile(
        r"^\s*(make|change|update|delete|remove|mark)\b",
        re.I,
    ),
    re.compile(
        r"\b(make|change|update|delete|remove|mark)\s+"
        r"(it|that|this|them)\b",
        re.I,
    ),
)

_DIRECT_REFERENCE_PATTERNS = (
    re.compile(
        r"\b(it|that|this|them|those|these)\b",
        re.I,
    ),
    re.compile(
        r"^\s*(add|make|change|update|delete|remove|"
        r"mark|complete)\s+(it|that|this|them)\b",
        re.I,
    ),
)


def _is_direct_reference_followup(
    message: str,
) -> bool:
    """Return whether the message directly references an earlier turn."""

    return any(
        pattern.search(message)
        for pattern in _DIRECT_REFERENCE_PATTERNS
    )


def _needs_conversation_context(
    state: AgentState,
) -> bool:
    """Return whether previous dialogue may affect the request."""

    message = str(
        state.get("message") or ""
    ).strip()

    if not message:
        return False

    return any(
        pattern.search(message)
        for pattern in _CONTEXT_PATTERNS
    )


def _clip_context_item(
    value: Any,
) -> str:
    """Limit one retrieved context item."""

    text = str(value or "").strip()

    if len(text) <= MAX_CONTEXT_ITEM_CHARS:
        return text

    return (
        text[
            : MAX_CONTEXT_ITEM_CHARS - 1
        ].rstrip()
        + "…"
    )


def _bound_context(
    items: Iterable[Any],
) -> List[str]:
    """Deduplicate and enforce context-size limits."""

    result: List[str] = []
    seen = set()
    total_chars = 0

    for raw in items:
        item = _clip_context_item(raw)

        if not item:
            continue

        normalized = " ".join(
            item.casefold().split()
        )

        if normalized in seen:
            continue

        remaining = (
            MAX_CONTEXT_CHARS
            - total_chars
        )

        if remaining <= 0:
            break

        if len(item) > remaining:
            if remaining < 80:
                break

            item = (
                item[: remaining - 1].rstrip()
                + "…"
            )

        seen.add(normalized)
        result.append(item)
        total_chars += len(item)

        if len(result) >= MAX_CONTEXT_ITEMS:
            break

    return result


def _interaction_domains(
    intent_value: Any,
) -> List[str]:
    """Parse domain-prefixed interaction intents."""

    domains: List[str] = []

    for raw in str(
        intent_value or ""
    ).split(";"):
        part = raw.strip()

        if ":" not in part:
            continue

        domain = (
            part.split(":", 1)[0]
            .strip()
            .casefold()
        )

        if (
            domain
            in {
                "finance",
                "tasks",
                "food",
                "maintenance",
                "documents",
                "general",
            }
            and domain not in domains
        ):
            domains.append(domain)

    return domains


def _recent_interaction_visible(
    intent_value: Any,
    role_value: str,
) -> bool:
    """Apply role visibility to recent SQLite interactions."""

    from app.ai.agents.permissions import (
        ROLE_RANK,
        domain_min_role,
    )
    from app.models.enums import HouseholdRole

    try:
        role = HouseholdRole(role_value)
    except (TypeError, ValueError):
        return False

    domains = _interaction_domains(
        intent_value
    )

    if not domains:
        # Legacy interactions lack domain prefixes. Treat them
        # as Adult-sensitive because they may contain private
        # finance or document text.
        return (
            ROLE_RANK[role]
            >= ROLE_RANK[HouseholdRole.ADULT]
        )

    required_role = max(
        (
            domain_min_role(domain)
            for domain in domains
        ),
        key=lambda value: ROLE_RANK[value],
    )

    return (
        ROLE_RANK[role]
        >= ROLE_RANK[required_role]
    )


def _require_memory_scope(
    session,
    state: AgentState,
) -> ConversationScope:
    """Validate graph-state identifiers against the database."""

    return require_owned_conversation(
        session,
        user_id=state.get("user_id"),
        conversation_id=state.get(
            "conversation_id"
        ),
        session_id=state.get("session_id"),
    )


def save_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Persist one interaction in a verified conversation.

    The route creates new conversations before graph execution.
    This node therefore never creates or claims a conversation.
    """

    session = SessionLocal()

    try:
        scope = _require_memory_scope(
            session,
            state,
        )

        actions = (
            state.get("planned_actions")
            or []
        )

        intents = [
            "{0}:{1}".format(
                str(
                    action.get("domain")
                    or "general"
                ).casefold(),
                action.get("intent"),
            )
            for action in actions
            if (
                isinstance(action, dict)
                and action.get("intent")
            )
        ]

        intent = (
            "; ".join(intents)
            if intents
            else "general:general"
        )

        # The current model column is String(120). A separate
        # schema change is required before this limit can grow.
        intent = intent[:120]

        interaction = AgentInteraction(
            conversation_id=(
                scope.conversation_id
            ),
            session_id=scope.session_id,
            user_id=scope.user_id,
            intent=intent,
            message=state.get("message"),
            response=state.get("response"),
        )

        session.add(interaction)
        session.commit()

        return {
            "conversation_id": (
                scope.conversation_id
            ),
            "interaction_id": (
                interaction.interaction_id
            ),
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def embed_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Embed the committed interaction with owner metadata."""

    interaction_id = state.get(
        "interaction_id"
    )

    if not interaction_id:
        return {
            "embedded": False
        }

    session = SessionLocal()

    try:
        scope = _require_memory_scope(
            session,
            state,
        )

        interaction = (
            session.query(AgentInteraction)
            .filter(
                AgentInteraction.interaction_id
                == interaction_id,
                AgentInteraction.conversation_id
                == scope.conversation_id,
                AgentInteraction.session_id
                == scope.session_id,
                AgentInteraction.user_id
                == scope.user_id,
            )
            .one_or_none()
        )

        if interaction is None:
            logger.warning(
                "Conversation embedding skipped: "
                "interaction is outside verified scope"
            )
            return {
                "embedded": False
            }

        from app.ai.agents.permissions import (
            ROLE_RANK,
            domain_min_role,
        )
        from app.rag.vector_store import (
            get_default_store,
        )

        domains = _interaction_domains(
            interaction.intent
        )

        if not domains:
            domains = ["general"]

        required_role = max(
            (
                domain_min_role(domain)
                for domain in domains
            ),
            key=lambda value: ROLE_RANK[value],
        )

        text = (
            "User asked: {0}\n"
            "Assistant replied: {1}"
        ).format(
            interaction.message,
            interaction.response,
        )

        get_default_store().add_texts(
            ids=[
                interaction.interaction_id
            ],
            texts=[text],
            source_domain="conversation",
            min_role=required_role,
            extra_metadata=[
                {
                    "domain": ",".join(
                        domains
                    ),
                    "user_id": scope.user_id,
                    "conversation_id": (
                        scope.conversation_id
                    ),
                    "session_id": (
                        scope.session_id
                    ),
                }
            ],
        )

        return {
            "embedded": True
        }

    except Exception:
        # Embedding is helpful but must not turn a successfully
        # persisted interaction into a failed request.
        logger.exception(
            "Conversation embedding failed"
        )

        return {
            "embedded": False
        }

    finally:
        session.close()


def retrieve_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Retrieve bounded context from the verified conversation."""

    if state.get("suggestion_context"):
        logger.info(
            "memory_retrieval mode=skipped "
            "reason=trusted_suggestion_context"
        )

        return {
            "retrieved_context": []
        }

    if not _needs_conversation_context(
        state
    ):
        logger.info(
            "memory_retrieval mode=skipped "
            "reason=self_contained "
            "message_chars=%s",
            len(
                str(
                    state.get("message")
                    or ""
                )
            ),
        )

        return {
            "retrieved_context": []
        }

    session = SessionLocal()
    recent_context: List[str] = []
    semantic_context: List[str] = []

    current_message = str(
        state.get("message") or ""
    ).strip()

    direct_reference = (
        _is_direct_reference_followup(
            current_message
        )
    )

    try:
        scope = _require_memory_scope(
            session,
            state,
        )

        # All three identifiers are applied even though
        # conversation_id is normally unique. This makes the
        # ownership boundary explicit at the read itself.
        query = (
            session.query(AgentInteraction)
            .filter(
                AgentInteraction.conversation_id
                == scope.conversation_id,
                AgentInteraction.session_id
                == scope.session_id,
                AgentInteraction.user_id
                == scope.user_id,
            )
        )

        scan_limit = (
            8
            if direct_reference
            else 16
        )

        rows = (
            query.order_by(
                AgentInteraction.created_at.desc()
            )
            .limit(scan_limit)
            .all()
        )

        allowed_rows = []

        wanted = (
            1
            if direct_reference
            else RECENT_CONTEXT_LIMIT
        )

        for interaction in rows:
            if not _recent_interaction_visible(
                interaction.intent,
                str(
                    state.get("role")
                    or ""
                ),
            ):
                continue

            allowed_rows.append(
                interaction
            )

            if len(allowed_rows) >= wanted:
                break

        allowed_rows.reverse()

        for interaction in allowed_rows:
            recent_context.append(
                (
                    "Previous interaction:\n"
                    "User: {0}\n"
                    "Assistant: {1}"
                ).format(
                    interaction.message,
                    interaction.response,
                )
            )

    finally:
        session.close()

    role_value = state.get(
        "role",
        "",
    )

    if (
        current_message
        and not direct_reference
    ):
        try:
            from app.models.enums import (
                HouseholdRole,
            )
            from app.rag.vector_store import (
                get_default_store,
            )

            try:
                role = HouseholdRole(
                    role_value
                )
            except (TypeError, ValueError):
                role = HouseholdRole.GUEST

            results = (
                get_default_store().query(
                    current_message,
                    role=role,
                    n_results=(
                        SEMANTIC_CONTEXT_LIMIT
                    ),
                    source_domain=(
                        "conversation"
                    ),
                    user_id=scope.user_id,
                    conversation_id=(
                        scope.conversation_id
                    ),
                )
            )

            documents = (
                results.get(
                    "documents",
                    [],
                )
                or []
            )

            if documents:
                documents = documents[0]

            for value in documents:
                if value:
                    semantic_context.append(
                        (
                            "Semantically relevant "
                            "previous conversation:\n"
                        )
                        + str(value)
                    )

        except Exception:
            # Semantic recall is best effort. Exact recent
            # conversation retrieval has already been scoped.
            logger.exception(
                "Semantic conversation "
                "retrieval failed"
            )

    combined = _bound_context(
        recent_context
        + semantic_context
    )

    logger.info(
        "memory_retrieval mode=enabled "
        "direct_reference=%s recent=%s "
        "semantic=%s returned=%s chars=%s",
        direct_reference,
        len(recent_context),
        len(semantic_context),
        len(combined),
        sum(
            len(item)
            for item in combined
        ),
    )

    return {
        "retrieved_context": combined
    }