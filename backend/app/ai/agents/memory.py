"""Save + Embed nodes (diagram: "Save AgentInteraction" -> "embed" -> Vector store).

Persists the turn as a Conversation/AgentInteraction row (system of record)
and, best-effort, embeds a text summary of it into the Chroma vector store
tagged with the user's role so future retrieval respects RBAC.

Embedding failures never roll back or block the save — the interaction is
already durably recorded in SQLite by the time embed_node runs.
"""
from __future__ import annotations

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.documents import AgentInteraction, Conversation


def save_node(state: AgentState) -> dict:
    session = SessionLocal()

    try:
        conversation_id = state.get("conversation_id")

        if not conversation_id:
            conversation = Conversation(
                session_id=state["session_id"],
                user_id=state.get("user_id"),
            )

            session.add(conversation)
            session.flush()

            conversation_id = conversation.conversation_id

        actions = state.get("planned_actions", [])

        intents = [
            action.get("intent")
            for action in actions
            if action.get("intent")
        ]

        intent = "; ".join(intents) if intents else "general"

        interaction = AgentInteraction(
            conversation_id=conversation_id,
            session_id=state["session_id"],
            user_id=state.get("user_id"),
            intent=intent,
            message=state.get("message"),
            response=state.get("response"),
        )

        session.add(interaction)
        session.commit()

        return {
            "conversation_id": conversation_id,
            "interaction_id": interaction.interaction_id,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def embed_node(state: AgentState) -> dict:
    interaction_id = state.get("interaction_id")
    if not interaction_id:
        return {"embedded":False}
    try:
        from app.ai.agents.permissions import domain_min_role
        from app.rag.vector_store import get_default_store  # see NOTE in router.py

        store = get_default_store()
        domain = state.get("domain", "general")
        text = f"User asked: {state.get('message')}\nAssistant replied: {state.get('response')}"
        store.add_texts(
            ids=[interaction_id],
            texts=[text],
            source_domain="conversation",
            # Sensitivity comes from the domain, not from the caller's own
            # role — a finance chat should be retrievable by any Adult, not
            # just the specific Admin who happened to trigger it.
            min_role=domain_min_role(domain),
            extra_metadata=[{"domain": domain}],
        )
        return {"embedded":True}
    except Exception:
        return {"embedded":False}
def retrieve_node(state: AgentState) -> dict:
    """
    Retrieve conversation context using:

    1. Recent SQLite conversation history
    2. Semantic similarity search over embedded past conversations

    Both are merged into state["retrieved_context"].

    Semantic retrieval is RBAC-filtered by VectorStore.query().
    """

    session = SessionLocal()

    recent_context = []
    semantic_context = []

    try:
        # =====================================================
        # 1. Recent conversation history from SQLite
        # =====================================================

        query = session.query(
            AgentInteraction
        )

        conversation_id = state.get(
            "conversation_id"
        )

        session_id = state.get(
            "session_id"
        )

        user_id = state.get(
            "user_id"
        )

        if conversation_id:
            query = query.filter(
                AgentInteraction.conversation_id
                == conversation_id
            )

        else:
            query = query.filter(
                AgentInteraction.session_id
                == session_id
            )

            if user_id:
                query = query.filter(
                    AgentInteraction.user_id
                    == user_id
                )

        rows = (
            query
            .order_by(
                AgentInteraction.created_at.desc()
            )
            .limit(5)
            .all()
        )

        # Oldest first.
        rows.reverse()

        for interaction in rows:
            recent_context.append(
                (
                    "Previous interaction:\n"
                    f"User: {interaction.message}\n"
                    f"Assistant: {interaction.response}"
                )
            )

    finally:
        session.close()

    # =========================================================
    # 2. Semantic retrieval from Chroma
    # =========================================================

    current_message = (
        state.get("message")
        or ""
    ).strip()

    role_value = state.get(
        "role",
        "",
    )

    if current_message:
        try:
            from app.rag.vector_store import (
                get_default_store,
            )
            from app.models.enums import (
                HouseholdRole,
            )

            try:
                role = HouseholdRole(
                    role_value
                )
            except ValueError:
                role = HouseholdRole.GUEST

            store = get_default_store()

            results = store.query(
                current_message,
                role=role,
                n_results=5,
                source_domain="conversation",
            )

            documents = (
                results.get(
                    "documents",
                    []
                )
                or []
            )

            # Chroma returns one nested list because
            # we send one query_text.
            if documents:
                documents = documents[0]

            for text in documents:
                if not text:
                    continue

                semantic_context.append(
                    (
                        "Semantically relevant previous "
                        "conversation:\n"
                        + str(text)
                    )
                )

        except Exception as exc:
            # Semantic retrieval should never break the agent.
            print(
                "\n========== SEMANTIC RETRIEVAL ERROR =========="
            )
            print(exc)
            print(
                "==============================================\n"
            )

    # =========================================================
    # 3. Merge + deduplicate
    # =========================================================

    combined = []

    seen = set()

    for item in (
        recent_context
        + semantic_context
    ):
        normalized = " ".join(
            item.casefold().split()
        )

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        combined.append(
            item
        )

    # Keep context bounded.
    combined = combined[:8]

    # =========================================================
    # Debug
    # =========================================================

    print(
        "\n========== RETRIEVED CONTEXT =========="
    )

    print(
        "Recent:",
        len(recent_context),
    )

    print(
        "Semantic:",
        len(semantic_context),
    )

    for item in combined:
        print(item)
        print("---")

    print(
        "=======================================\n"
    )

    return {
        "retrieved_context": combined
    }
