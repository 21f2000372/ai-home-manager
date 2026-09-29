from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Optional

from langgraph.graph import END, StateGraph

from app.ai.agents.actions import (
    next_action_node,
    route_after_action,
)
from app.ai.agents.authorize import (
    authorize_node,
    route_after_authorize,
    route_after_specialist,
)
from app.ai.agents.confirmation import (
    request_confirmation_node,
    resume_confirmation_node,
    route_after_resume,
)
from app.ai.agents.duplicate import (
    duplicate_check_node,
    route_after_duplicate,
)
from app.ai.agents.execute import execute_node
from app.ai.agents.memory import (
    embed_node,
    retrieve_node,
    save_node,
)
from app.ai.agents.planner import planner_node
from app.ai.agents.specialist import specialist_node
from app.ai.agents.state import (
    AgentState,
    DEFAULT_MAX_ITERATIONS,
)
from app.ai.agents.document_flow import (
    document_extract_node,
    document_ingestion_node,
    document_validate_node,
    document_actions_node,
    document_preview_node,
)

def route_after_retrieve(
    state: AgentState,
) -> str:
    """
    After conversation memory is retrieved, decide whether
    this is normal chat or an uploaded-document request.
    """

    if state.get("uploaded_file") is not None:
        return "document_ingestion"

    return "planner"



@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(
        AgentState
    )

    # --------------------------------------------------------------
    # Nodes
    # --------------------------------------------------------------
    
    graph.add_node(
        "resume_confirmation",
        resume_confirmation_node,
    )

    graph.add_node(
        "retrieve",
        retrieve_node,
    )

    graph.add_node(
        "planner",
        planner_node,
    )

    graph.add_node(
        "specialist",
        specialist_node,
    )

    graph.add_node(
        "duplicate_check",
        duplicate_check_node,
    )

    graph.add_node(
        "request_confirmation",
        request_confirmation_node,
    )

    graph.add_node(
        "authorize",
        authorize_node,
    )

    graph.add_node(
        "execute",
        execute_node,
    )

    graph.add_node(
        "next_action",
        next_action_node,
    )

    graph.add_node(
        "save",
        save_node,
    )

    graph.add_node(
        "embed",
        embed_node,
    )
    graph.add_node(
        "document_ingestion",
        document_ingestion_node,
    )
    graph.add_node(
        "document_extract",
        document_extract_node,
    )
    graph.add_node(
        "document_validate",
        document_validate_node,
    )
    graph.add_node(
        "document_actions",
        document_actions_node,
    )
    graph.add_node(
        "document_preview",
        document_preview_node,
    )
    # --------------------------------------------------------------
    # Entry
    # --------------------------------------------------------------

    # Every message first checks whether it is a response to
    # a previously pending confirmation.
    graph.set_entry_point(
        "resume_confirmation"
    )
     
    graph.add_conditional_edges(
        "resume_confirmation",
        route_after_resume,
        {
            "retrieve": "retrieve",
            "authorize": "authorize",
            "save": "save",
        },
    )

    # --------------------------------------------------------------
    # Normal request
    # --------------------------------------------------------------

    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "planner": "planner",
            "document_ingestion": "document_ingestion",
        },
    )   
    graph.add_edge(
        "planner",
        "specialist",
    )

    # --------------------------------------------------------------
    # Specialist proposed tool
    # --------------------------------------------------------------

    graph.add_conditional_edges(
        "specialist",
        route_after_specialist,
        {
            # Important:
            # the existing route name remains "authorize",
            # but we intercept it with duplicate_check.
            "authorize": "duplicate_check",

            "next_action": "next_action",
        },
    )

    # --------------------------------------------------------------
    # Duplicate detection
    # --------------------------------------------------------------

    graph.add_conditional_edges(
        "duplicate_check",
        route_after_duplicate,
        {
            "authorize": "authorize",

            "request_confirmation":
                "request_confirmation",
        },
    )

    # Stop this invocation after asking the user.
    graph.add_edge(
        "request_confirmation",
        "save",
    )

    # --------------------------------------------------------------
    # Authorization
    # --------------------------------------------------------------

    graph.add_conditional_edges(
        "authorize",
        route_after_authorize,
        {
            "execute": "execute",
            "next_action": "next_action",
        },
    )

    # --------------------------------------------------------------
    # Execution
    # --------------------------------------------------------------

    # Keep this for Phase 1.
    #
    # We will optimize this next so simple mutations don't
    # require another LLM call.
    graph.add_edge(
        "execute",
        "specialist",
    )

    # --------------------------------------------------------------
    # Multi-action progression
    # --------------------------------------------------------------

    graph.add_conditional_edges(
        "next_action",
        route_after_action,
        {
            "specialist": "specialist",
            "save": "save",
        },
    )

    # --------------------------------------------------------------
    # Persistence / embeddings
    # --------------------------------------------------------------

    graph.add_edge(
        "save",
        "embed",
    )

    graph.add_edge(
        "embed",
        END,
    )
    graph.add_edge(
        "document_ingestion",
        "document_extract",
    )

    graph.add_edge(
        "document_extract",
        "document_validate",
    )

    graph.add_edge(
        "document_validate",
        "document_actions",
    )

    graph.add_edge(
        "document_actions",
        "document_preview",
    )

    graph.add_edge(
        "document_preview",
        "save",
    )

    return graph.compile()


def run_agent(
    *,
    message: str,
    session_id: str,
    user_id: str,
    role: str,
    conversation_id: Optional[str] = None,
    uploaded_file=None,
) -> AgentState:

    app_graph = build_graph()

    initial_state: AgentState = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "conversation_id": conversation_id,

        "message": message,

        "messages": [],

        "retrieved_context": [],

        "planned_actions": [],
        "current_action_index": 0,

        "pending_tool_call": None,
        "pending_ai_message": None,

        "tool_result": None,

        "authorized": False,
        "auth_error": None,

        "duplicate_status": None,
        "duplicate_details": None,
        "uploaded_file": uploaded_file,

        "document_ingestion_result": None,
        "document_fields": None,
        "document_field_warnings": [],
        "document_proposed_actions": [],
        "pending_document_id": None,
        "document_preview": None,

        "confirmation_kind": None,
        "awaiting_confirmation": False,
        "confirmation_resolution": None,

        "current_datetime": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "iteration": 0,

        "max_iterations":
            DEFAULT_MAX_ITERATIONS,

        "finished": False,

        "response": "",

        "embedded": False,
    }

    return app_graph.invoke(
        initial_state
    )