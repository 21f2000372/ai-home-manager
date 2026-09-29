from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage, AIMessage
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
    # Duplicate / conflict detection
    # ------------------------------------------------------------------

    # NEW | DUPLICATE | CONFLICT
    duplicate_status: Optional[str]

    # Human-readable information about the existing record.
    duplicate_details: Optional[str]

    # True when execution is waiting for explicit user confirmation.
    awaiting_confirmation: bool

    # none | confirmed | cancelled
    confirmation_resolution: Optional[str]

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
    # ------------------------------------------------------------------
    # Document ingestion
    # ------------------------------------------------------------------

    uploaded_file: Optional[Any]

    document_ingestion_result: Optional[dict[str, Any]]

    document_fields: Optional[dict[str, Any]]

    document_field_warnings: list[str]

    document_proposed_actions: list[dict[str, Any]]

    pending_document_id: Optional[str]

    document_preview: Optional[dict[str, Any]]

    # none | duplicate | document
    confirmation_kind: Optional[str]