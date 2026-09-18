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
    """Retrieve recent conversation history for the current user/session."""
    session = SessionLocal()

    try:
        query = session.query(AgentInteraction)

        conversation_id = state.get("conversation_id")
        session_id = state.get("session_id")
        user_id = state.get("user_id")

        if conversation_id:
            query = query.filter(
                AgentInteraction.conversation_id == conversation_id
            )
        else:
            query = query.filter(
                AgentInteraction.session_id == session_id
            )

            if user_id:
                query = query.filter(
                    AgentInteraction.user_id == user_id
                )

        rows = (
            query
            .order_by(AgentInteraction.created_at.desc())
            .limit(10)
            .all()
        )

        if not rows:
            return {
                "retrieved_context": []
            }

        # Reverse so the oldest retrieved interaction appears first.
        rows.reverse()

        context = []

        for interaction in rows:
            context.append(
                (
                    f"Previous interaction:\n"
                    f"User: {interaction.message}\n"
                    f"Assistant: {interaction.response}"
                )
            )
        print("\n========== RETRIEVED CONTEXT ==========")
        for item in context:
            print(item)
        print("=======================================\n")
        return {
            "retrieved_context": context
        }

    finally:
        session.close()
