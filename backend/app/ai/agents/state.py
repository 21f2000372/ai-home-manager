"""Shared LangGraph state contracts for the AI Home Manager.

This module intentionally contains data-shape definitions only.  It must stay
free of application side effects so every graph node can import it safely.

Compatibility target: Python 3.8+.
"""

from typing import Any, Dict, List, Optional, TypedDict

try:
    # `typing.Annotated` is available in newer supported runtimes.
    from typing import Annotated
except ImportError:  # pragma: no cover - exercised only on Python 3.8
    from typing_extensions import Annotated

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.message import add_messages


DEFAULT_MAX_ITERATIONS = 5


class ToolCall(TypedDict, total=False):
    """A concrete tool call selected by a specialist/planner."""

    name: str
    args: Dict[str, Any]
    id: str


class PlannedAction(TypedDict, total=False):
    """One independent action extracted from the user's request."""

    domain: str
    intent: str
    description: str

    # Filled in by the specialist when it selects a concrete tool.
    tool_name: Optional[str]
    tool_args: Dict[str, Any]

    # pending -> running -> completed / failed / unauthorized / cancelled
    status: str

    # Raw tool result kept for server-side chaining, audit, and follow-ups.
    # It may contain stable internal identifiers and must not be exposed
    # directly to the user.
    result: Optional[str]

    # Natural, frontend-safe description of the action outcome. This should
    # name the resource in human terms and never expose internal UUIDs.
    display_result: Optional[str]

    # Provenance for loop prevention / cross-domain orchestration.
    # explicit | dependency | cross_domain_suggestion |
    # cross_domain_suggestion_continuation
    origin: Optional[str]

    # Trusted server-side prerequisite metadata. Never populate this directly
    # from user text. Current use: add an appliance record before resuming the
    # exact saved repair/service action.
    dependency_context: Optional[Dict[str, Any]]


class AgentState(TypedDict, total=False):
    """State shared by all LangGraph nodes.

    `total=False` is deliberate: nodes return partial state updates and
    LangGraph merges those updates into the existing state.

    The document section contains the new proposal-based contract introduced
    by the production document-pipeline refactor.  A few legacy document keys
    remain temporarily so the existing graph can stay bootable until Step 5
    rewires the graph topology.  They are marked clearly below and should not
    be used by new code.
    """

    # ------------------------------------------------------------------
    # Request / authenticated user context
    # ------------------------------------------------------------------

    session_id: str
    user_id: str
    role: str
    conversation_id: Optional[str]
    current_datetime: str
    message: str

    # ------------------------------------------------------------------
    # Retrieval / memory
    # ------------------------------------------------------------------

    retrieved_context: List[str]

    # ------------------------------------------------------------------
    # Conversation / ReAct messages
    # ------------------------------------------------------------------

    messages: Annotated[List[BaseMessage], add_messages]

    # ------------------------------------------------------------------
    # Multi-domain planning
    # ------------------------------------------------------------------

    planned_actions: List[PlannedAction]

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
    # Existing duplicate/conflict state
    # ------------------------------------------------------------------
    # Kept until the shared consistency service is introduced.  Do not add
    # more domain-specific duplicate logic to these fields.

    # NEW | DUPLICATE | CONFLICT
    duplicate_status: Optional[str]

    # Human-readable information about the existing record.
    duplicate_details: Optional[str]

    # Server-derived structured identity of the matched duplicate/conflict.
    # Never accept this id from user text. It is used for safe resolutions
    # such as "update the existing grocery item to 3 kg".
    duplicate_match: Optional[Dict[str, Any]]

    # ------------------------------------------------------------------
    # Future shared consistency state
    # ------------------------------------------------------------------
    # Step 10 will make these authoritative for cross-domain checks.

    # CLEAR | RELATED | POSSIBLE_DUPLICATE | CONFLICT
    consistency_status: Optional[str]
    consistency_results: List[Dict[str, Any]]

    # ------------------------------------------------------------------
    # Cross-domain follow-up suggestion state
    # ------------------------------------------------------------------

    # Frontend-safe current suggestion generated from completed tool actions.
    active_suggestion: Optional[Dict[str, Any]]

    # Trusted server-side context carried into a user-accepted follow-up.
    # This is never accepted directly from client input.
    suggestion_context: Optional[Dict[str, Any]]
    # ------------------------------------------------------------------
    # Clarification
    # ------------------------------------------------------------------
    clarification_needed: bool
    clarification_context: Optional[Dict[str, Any]]
    # ------------------------------------------------------------------
    # Confirmation / durable-review handoff
    # ------------------------------------------------------------------

    # True when execution is waiting for explicit user confirmation.
    awaiting_confirmation: bool

    # none | confirmed | cancelled | edit | edit_prompt | error
    confirmation_resolution: Optional[str]

    # none | duplicate | conflict | action | document | suggestion
    confirmation_kind: Optional[str]

    # Durable proposal identifier.
    workflow_proposal_id: Optional[str]

    # Set while the user is revising a pending normal-chat action. The value
    # comes only from restored server-side workflow state, never from a user-
    # supplied proposal id.
    editing_workflow_proposal_id: Optional[str]

    # Exact pending action/revision restored for natural-language editing.
    pending_edit_context: Optional[Dict[str, Any]]

    # Forces a revised action back through review even if duplicate checking
    # no longer finds a conflict. Edits never execute silently.
    force_action_review: bool

    # ------------------------------------------------------------------
    # Loop safety
    # ------------------------------------------------------------------

    iteration: int
    max_iterations: int
    finished: bool

    # ------------------------------------------------------------------
    # Final response / memory persistence
    # ------------------------------------------------------------------

    response: str
    interaction_id: Optional[str]
    embedded: bool

    # ------------------------------------------------------------------
    # Document upload / validation
    # ------------------------------------------------------------------

    # Werkzeug FileStorage (or an equivalent upload object).  `Any` avoids
    # coupling the shared graph-state contract to Flask/Werkzeug at import
    # time.
    uploaded_file: Optional[Any]

    # Output from the single document-validation node.  It contains staging,
    # extraction, classification, guardrail, and duplicate-fingerprint data.
    document_ingestion_result: Optional[Dict[str, Any]]

    # Temporary PendingDocumentUpload primary key created during validation.
    pending_document_id: Optional[str]

    # ------------------------------------------------------------------
    # Proposal-based document interpretation
    # ------------------------------------------------------------------

    # Direct output of the tool-less document interpreter.  This is a
    # DocumentProposal-shaped dictionary, not a generic invoice/receipt
    # extraction schema.
    document_proposal: Optional[Dict[str, Any]]

    # Deterministic validation/check results for proposed document actions.
    document_check_results: List[Dict[str, Any]]

    # Renderable, user-facing review payload derived from the checked
    # proposal.  It must not itself perform mutations.
    document_review: Optional[Dict[str, Any]]

    # True when policy/checks require the document proposal to stop at review
    # rather than continue automatically.  Later steps will set this from
    # code-level approval policy.
    document_requires_review: bool

    # Natural-language revision request for a durable document proposal.
    # The proposal id itself comes only from restored server-side state.
    document_edit_request: Optional[str]

    # Results of approved document actions.  Ledger-backed in Step 8B.
    document_execution_results: List[Dict[str, Any]]

    # None | REVIEW_REQUIRED | COMPLETED | FAILED
    document_execution_status: Optional[str]

    # Permanent Document primary key after the approved original is archived.
    archived_document_id: Optional[str]

    # ------------------------------------------------------------------
    # Temporary compatibility keys -- remove after graph/workflow migration
    # ------------------------------------------------------------------
    # The old graph still initializes/reads some of these keys.  New code
    # must use document_proposal/document_check_results/document_review.

    # DEPRECATED: old prerequisite extraction schema.
    document_fields: Optional[Dict[str, Any]]

    # DEPRECATED: old extracted-field warnings.
    document_field_warnings: List[str]

    # DEPRECATED: old hard-coded action list.
    document_proposed_actions: List[Dict[str, Any]]

    # DEPRECATED: compatibility alias for document_review during Step 3-5.
    document_preview: Optional[Dict[str, Any]]
    
