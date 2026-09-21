from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph
from typing import Optional
from app.ai.agents.actions import (
    next_action_node,
    route_after_action,
)
from app.ai.agents.authorize import (
    authorize_node,
    route_after_authorize,
    route_after_specialist,
)

from app.ai.agents.execute import execute_node
from app.ai.agents.memory import embed_node, save_node, retrieve_node
from app.ai.agents.planner import planner_node
from app.ai.agents.specialist import specialist_node
from app.ai.agents.state import AgentState, DEFAULT_MAX_ITERATIONS
from datetime import datetime

@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(AgentState)

    # ---------------------------------------------------------------
    # Nodes
    # ---------------------------------------------------------------

    graph.add_node("planner", planner_node)
    graph.add_node("specialist", specialist_node)
    graph.add_node("authorize", authorize_node)
    graph.add_node("execute", execute_node)
    graph.add_node("next_action", next_action_node)
    graph.add_node("save", save_node)
    graph.add_node("embed", embed_node)
    graph.add_node("retrieve", retrieve_node)
    # ---------------------------------------------------------------
    # Entry
    # ---------------------------------------------------------------

    graph.set_entry_point("retrieve")
    # ---------------------------------------------------------------
    # Planning
    # ---------------------------------------------------------------
    graph.add_edge("retrieve", "planner")
    graph.add_edge("planner", "specialist")
    
    # ---------------------------------------------------------------
    # Specialist
    #
    # If a tool is required:
    #     specialist → authorize
    #
    # If no tool is required:
    #     specialist → next_action
    # ---------------------------------------------------------------

    graph.add_conditional_edges(
        "specialist",
        route_after_specialist,
        {
            "authorize": "authorize",
            "next_action": "next_action",
        },
    )

    # ---------------------------------------------------------------
    # Authorization
    #
    # Authorized:
    #     authorize → execute
    #
    # Unauthorized:
    #     authorize → next_action
    # ---------------------------------------------------------------

    graph.add_conditional_edges(
        "authorize",
        route_after_authorize,
        {
            "execute": "execute",
            "next_action": "next_action",
        },
    )

    # ---------------------------------------------------------------
    # Execute
    #
    # After a tool executes, return to the specialist so it can inspect
    # the ToolMessage and decide whether the current action is complete.
    # ---------------------------------------------------------------

    graph.add_edge("execute", "specialist")

    # ---------------------------------------------------------------
    # Move to the next planned action
    # ---------------------------------------------------------------

    graph.add_conditional_edges(
        "next_action",
        route_after_action,
        {
            "specialist": "specialist",
            "save": "save",
        },
    )

    # ---------------------------------------------------------------
    # Memory
    # ---------------------------------------------------------------

    graph.add_edge("save", "embed")
    graph.add_edge("embed", END)

    return graph.compile()


def run_agent(
    *,
    message: str,
    session_id: str,
    user_id: str,
    role: str,
    conversation_id: Optional[str] = None,
) -> AgentState:
    """Entry point used by the Flask route: runs one full turn through the graph."""
    app_graph = build_graph()
    current_datetime = datetime.now().astimezone().isoformat()
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

        "current_datetime": current_datetime,

        "iteration": 0,
        "max_iterations": DEFAULT_MAX_ITERATIONS,

        "finished": False,
        "response": "",
        "embedded": False,
    }
    return app_graph.invoke(initial_state)
