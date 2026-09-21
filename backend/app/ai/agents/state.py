from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage,AIMessage
from langgraph.graph.message import add_messages


DEFAULT_MAX_ITERATIONS = 5


class ToolCall(TypedDict, total=False):
    name: str
    args: dict[str, Any]
    id: str

class PlannedAction(TypedDict, total=False):
    """
    One independent action extracted from the user's request.
    """

    domain: str
    domain_agent: str
    allowed_tools: list[str]
    shared_services: list[str]
    delegated_from: Optional[str]
    intent: str
    description: str

    # Filled in by the specialist when it decides which tool to use.
    tool_name: Optional[str]
    tool_args: dict[str, Any]

    # pending → running → completed / failed / unauthorized
    status: str

    # Result returned by the tool.
    result: Optional[str]


class AgentState(TypedDict, total=False):
    # ------------------------------------------------------------------
    # Request / user context
    # ------------------------------------------------------------------

    session_id: str
    user_id: str
    role: str
    conversation_id: Optional[str]
    current_datetime: str
    message: str

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------

    retrieved_context: list[str]

    # ------------------------------------------------------------------
    # Conversation / ReAct messages
    # ------------------------------------------------------------------

    messages: Annotated[list[BaseMessage], add_messages]

    # ------------------------------------------------------------------
    # Multi-domain planning
    # ------------------------------------------------------------------

    planned_actions: list[PlannedAction]

    # Index of the action currently being processed.
    current_action_index: int

    # ------------------------------------------------------------------
    # Current tool call
    # ------------------------------------------------------------------

    pending_tool_call: Optional[ToolCall]
    pending_ai_message: Optional[AIMessage]
    tool_result: Optional[str]

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    authorized: bool
    auth_error: Optional[str]


    # ------------------------------------------------------------------
    # Loop safety
    # ------------------------------------------------------------------

    iteration: int
    max_iterations: int
    finished: bool

    # ------------------------------------------------------------------
    # Final response / memory
    # ------------------------------------------------------------------

    response: str
    interaction_id: Optional[str]
    embedded: bool
