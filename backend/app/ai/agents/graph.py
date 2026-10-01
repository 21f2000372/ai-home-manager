"""LangGraph orchestration for the AI Home Manager.

Step 5 of the production document-pipeline refactor.

Compatibility target: Python 3.8+.

The document branch now has one graph-level document validation node followed
by direct document interpretation, deterministic proposal checks, and review.
Normal chat routing is intentionally left unchanged in this step.
"""

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
from app.ai.agents.document_flow import (
    document_checks_node,
    document_edit_node,
    document_interpret_node,
    document_review_node,
    document_validation_node,
)
from app.ai.agents.duplicate import (
    duplicate_check_node,
    route_after_duplicate,
)
from app.ai.agents.execute import execute_node
from app.services.document_execution import document_execute_node
from app.ai.agents.memory import (
    embed_node,
    retrieve_node,
    save_node,
)
from app.ai.agents.planner import planner_node
from app.ai.agents.specialist import specialist_node
from app.ai.agents.suggestions import (
    cross_domain_suggestion_node,
    route_after_suggestion_approve,
    route_after_suggestion_authorize,
    suggestion_approve_node,
    suggestion_authorize_node,
)
from app.ai.agents.state import (
    AgentState,
    DEFAULT_MAX_ITERATIONS,
)


def route_after_retrieve(state: AgentState) -> str:
    """Route an upload to the document branch; otherwise use normal chat."""

    if state.get("document_edit_request"):
        return "document_edit"

    if state.get("uploaded_file") is not None:
        return "document_validation"

    return "planner"


def route_after_document_validation(state: AgentState) -> str:
    """Stop safely when validation rejected the upload; otherwise interpret."""

    result = state.get("document_ingestion_result") or {}

    if state.get("finished"):
        return "save"

    if not result.get("success", False):
        return "save"

    return "document_interpret"


def route_after_document_interpret(state: AgentState) -> str:
    """Skip later proposal work when interpretation failed safely."""

    if state.get("finished"):
        return "save"

    return "document_checks"


_READ_TOOL_PREFIXES = ("get_", "list_", "search_")


def route_after_execute(state: AgentState) -> str:
    """Avoid an unnecessary second LLM call after terminal mutations.

    Read tools can be intermediate steps: the specialist may need a returned
    row/list to resolve a later update/delete operation, so reads keep the
    existing ReAct follow-up. Mutations already have a concrete tool outcome
    and can be finalized deterministically by ``next_action_node``.
    """

    actions = state.get("planned_actions") or []
    index = int(state.get("current_action_index") or 0)

    if index < 0 or index >= len(actions):
        return "next_action"

    tool_name = str(actions[index].get("tool_name") or "").strip()

    if tool_name.startswith(_READ_TOOL_PREFIXES):
        return "specialist"

    return "next_action"


@lru_cache(maxsize=1)
def build_graph():
    """Build and compile the current application graph."""

    graph = StateGraph(AgentState)

    # ------------------------------------------------------------------
    # Shared / normal-chat nodes
    # ------------------------------------------------------------------

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
        "cross_domain_suggestion",
        cross_domain_suggestion_node,
    )

    graph.add_node(
        "suggestion_authorize",
        suggestion_authorize_node,
    )

    graph.add_node(
        "suggestion_approve",
        suggestion_approve_node,
    )

    graph.add_node(
        "save",
        save_node,
    )

    graph.add_node(
        "embed",
        embed_node,
    )

    # ------------------------------------------------------------------
    # Document branch
    # ------------------------------------------------------------------
    #
    # Important architecture boundary:
    # - `document_validation` is the ONLY graph-level document validation
    #   node. File validation, hashing, OCR, classification, content
    #   guardrails, and duplicate fingerprinting are internal utilities
    #   invoked by that node.
    # - The interpreter is tool-less. It produces a proposal; it does not
    #   mutate household state.
    # - `document_checks` validates the proposal, not the raw upload.
    # ------------------------------------------------------------------

    graph.add_node(
        "document_validation",
        document_validation_node,
    )

    graph.add_node(
        "document_interpret",
        document_interpret_node,
    )

    graph.add_node(
        "document_edit",
        document_edit_node,
    )

    graph.add_node(
        "document_checks",
        document_checks_node,
    )

    graph.add_node(
        "document_review_step",
        document_review_node,
    )

    graph.add_node(
        "document_execute",
        document_execute_node,
    )

    # ------------------------------------------------------------------
    # Entry / pending confirmation
    # ------------------------------------------------------------------

    graph.set_entry_point("resume_confirmation")

    graph.add_conditional_edges(
        "resume_confirmation",
        route_after_resume,
        {
            "retrieve": "retrieve",
            "authorize": "authorize",
            "suggestion_authorize": "suggestion_authorize",
            "document_execute": "document_execute",
            "save": "save",
        },
    )

    # ------------------------------------------------------------------
    # Request routing
    # ------------------------------------------------------------------

    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "planner": "planner",
            "document_validation": "document_validation",
            "document_edit": "document_edit",
        },
    )

    # ------------------------------------------------------------------
    # Normal chat / action path (unchanged in Step 5)
    # ------------------------------------------------------------------

    graph.add_edge(
        "planner",
        "specialist",
    )

    graph.add_conditional_edges(
        "specialist",
        route_after_specialist,
        {
            # Keep the existing public route name. The duplicate node still
            # intercepts the call before authorization in this refactor step.
            "authorize": "duplicate_check",
            "suggestion_authorize": "suggestion_authorize",
            "next_action": "next_action",
        },
    )

    graph.add_conditional_edges(
        "duplicate_check",
        route_after_duplicate,
        {
            "authorize": "authorize",
            "request_confirmation": "request_confirmation",
            "suggestion_approve": "suggestion_approve",
        },
    )

    # Review is durably persisted before this turn ends. A later yes/no/edit
    # reply is restored by `resume_confirmation`.
    graph.add_edge(
        "request_confirmation",
        "save",
    )

    graph.add_conditional_edges(
        "authorize",
        route_after_authorize,
        {
            "execute": "execute",
            "next_action": "next_action",
        },
    )

    # Read tools may be intermediate lookup steps and therefore keep the
    # existing ReAct follow-up. Mutation tools already have a concrete outcome,
    # so they skip the redundant second specialist LLM call and go straight to
    # deterministic action finalization.
    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "specialist": "specialist",
            "next_action": "next_action",
        },
    )

    graph.add_conditional_edges(
        "next_action",
        route_after_action,
        {
            "specialist": "specialist",
            "cross_domain_suggestion": "cross_domain_suggestion",
        },
    )

    # Cross-domain suggestions are generated only after the complete explicit
    # multi-action plan finishes. The suggestion node itself never mutates a
    # target domain; it persists one RBAC-filtered proposal for a later yes/no.
    graph.add_edge(
        "cross_domain_suggestion",
        "save",
    )

    graph.add_conditional_edges(
        "suggestion_authorize",
        route_after_suggestion_authorize,
        {
            "duplicate_check": "duplicate_check",
            "next_action": "next_action",
        },
    )

    graph.add_conditional_edges(
        "suggestion_approve",
        route_after_suggestion_approve,
        {
            "execute": "execute",
            "next_action": "next_action",
        },
    )

    # ------------------------------------------------------------------
    # Document path
    # ------------------------------------------------------------------

    # A natural-language edit restores the durable document proposal and
    # staged source, then re-runs deterministic checks before a new review
    # revision is persisted.
    graph.add_edge(
        "document_edit",
        "document_checks",
    )

    graph.add_conditional_edges(
        "document_validation",
        route_after_document_validation,
        {
            "document_interpret": "document_interpret",
            "save": "save",
        },
    )

    graph.add_conditional_edges(
        "document_interpret",
        route_after_document_interpret,
        {
            "document_checks": "document_checks",
            "save": "save",
        },
    )

    graph.add_edge(
        "document_checks",
        "document_review_step",
    )

    # The review node durably persists the exact document proposal before
    # this turn ends. It still performs no household/domain mutation in 8A.
    graph.add_edge(
        "document_review_step",
        "save",
    )

    # Exact approved document revisions execute through application code, not
    # through an LLM/tool-call loop.  The execution service rechecks access
    # and freshness, archives the original, and writes ledger-backed actions.
    graph.add_edge(
        "document_execute",
        "save",
    )

    # ------------------------------------------------------------------
    # Persistence / semantic embedding
    # ------------------------------------------------------------------

    graph.add_edge(
        "save",
        "embed",
    )

    graph.add_edge(
        "embed",
        END,
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
    """Invoke the compiled graph with a fresh request-scoped state."""

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

        # Existing normal-chat duplicate state. This remains authoritative
        # until the shared consistency service is introduced.
        "duplicate_status": None,
        "duplicate_details": None,
        "duplicate_match": None,

        # Prepared for the later shared cross-domain consistency service.
        "consistency_status": None,
        "consistency_results": [],

        # Cross-domain follow-up state. Suggestions are generated only after
        # explicit actions finish and are RBAC-filtered before disclosure.
        "active_suggestion": None,
        "suggestion_context": None,

        # Upload / proposal-based document state.
        "uploaded_file": uploaded_file,
        "document_ingestion_result": None,
        "pending_document_id": None,
        "document_proposal": None,
        "document_check_results": [],
        "document_review": None,
        "document_requires_review": False,
        "document_edit_request": None,
        "document_execution_results": [],
        "document_execution_status": None,
        "archived_document_id": None,
        "workflow_proposal_id": None,
        "editing_workflow_proposal_id": None,
        "pending_edit_context": None,
        "force_action_review": False,

        # Confirmation / editable review state.
        "confirmation_kind": None,
        "awaiting_confirmation": False,
        "confirmation_resolution": None,

        "current_datetime": datetime.now().astimezone().isoformat(),
        "iteration": 0,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "finished": False,
        "response": "",
        "embedded": False,
    }

    return app_graph.invoke(initial_state)
