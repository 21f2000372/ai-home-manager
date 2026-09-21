"""Router / orchestrator node (diagram: "Classifies intent, adds context").

Two jobs per turn:
1. Classify which domain specialist should handle the message.
2. Retrieve role-filtered context from the vector store to ground the
   specialist's reasoning in past interactions/documents.

NOTE: this assumes your VectorStore lives at app.rag.vector_store — adjust
the import below if your project places it elsewhere. Retrieval failures
(missing chromadb, empty collection, import error) are swallowed on purpose:
retrieval is an enhancement, never a reason to block a chat turn.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents.llm import get_llm
from app.ai.agents.state import AgentState
from app.models.enums import HouseholdRole

DOMAINS = ["finance", "tasks", "food", "maintenance", "general"]

_CLASSIFY_PROMPT = (
    "Classify the household assistant message into exactly one domain: "
    f"{', '.join(DOMAINS)}.\n\n"

    "Choose the domain based primarily on the user's INTENT and ACTION, "
    "not merely on the nouns or objects mentioned.\n\n"

    "finance = recording, viewing, or managing money-related information, "
    "including expenses, spending, budgets, bills, payments, or purchases "
    "when the user is asking about the MONEY spent.\n"

    "tasks = chores, to-dos, task creation, task completion, or scheduling.\n"

    "food = grocery-list management, food inventory, adding grocery items, "
    "marking grocery items as purchased, or checking household food stock.\n"

    "maintenance = appliances, repairs, maintenance, warranties, or "
    "reported household problems.\n"

    "general = anything else, including small talk or ambiguous requests.\n\n"

    "Important examples:\n"
    "- 'Log Rs 500 spent on groceries.' -> finance\n"
    "- 'I spent Rs 500 on milk.' -> finance\n"
    "- 'How much did I spend on groceries?' -> finance\n"
    "- 'Create a grocery budget of Rs 5000.' -> finance\n"
    "- 'Add milk to my grocery list.' -> food\n"
    "- 'Add bread to the grocery list.' -> food\n"
    "- 'Is milk in my inventory?' -> food\n"
    "- 'Mark milk as purchased.' -> food\n"
    "- 'Create a task to clean the kitchen.' -> tasks\n"
    "- 'The washing machine is leaking.' -> maintenance\n\n"

    "Reply with ONLY the domain word, nothing else."
)


def router_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)
    reply = llm.invoke(
        [SystemMessage(content=_CLASSIFY_PROMPT), HumanMessage(content=state["message"])]
    )
    domain = (reply.content or "").strip().lower()
    if domain not in DOMAINS:
        domain = "general"
    print("\n========== ROUTER DEBUG ==========")
    print("message:", state["message"])
    print("classified domain:", domain)
    print("==================================\n")
    retrieved: list[str] = []
    try:
        from app.rag.vector_store import get_default_store  # local import: optional dep

        store = get_default_store()
        role = HouseholdRole(state.get("role", HouseholdRole.GUEST.value))
        results = store.query(state["message"], role=role, n_results=4)
        docs = results.get("documents") or []
        retrieved = docs[0] if docs else []
    except Exception:
        retrieved = []

    return {
        "domain": domain,
        "retrieved_context": retrieved,
        "messages": [HumanMessage(content=state["message"])],
    }
