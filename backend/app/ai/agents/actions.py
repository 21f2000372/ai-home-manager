from __future__ import annotations

import re
from typing import Dict, List

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal, utcnow
from app.models.workflows import WorkflowProposal


_UUID_PATTERN = (
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}"
)

# Common tool result format:
#   "(pending, id=<uuid>)"
# Remove only the internal id fragment, preserving the useful row state and
# its surrounding punctuation.
_INTERNAL_ID_FIELD_RE = re.compile(
    r",?\s*\bid\s*[=:]\s*" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_WITH_ID_RE = re.compile(
    r"\s+\bwith\s+id\s+" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_BARE_UUID_RE = re.compile(
    _UUID_PATTERN,
    re.IGNORECASE,
)


def _sanitize_user_facing_result(value: object) -> str:
    """Hide internal identifiers while preserving readable row formatting."""

    raw = str(value or "")

    raw = _INTERNAL_ID_FIELD_RE.sub("", raw)
    raw = _INTERNAL_WITH_ID_RE.sub("", raw)
    raw = _INTERNAL_BARE_UUID_RE.sub("[internal-id]", raw)

    # Preserve list/newline structure returned by read tools. Only normalize
    # whitespace inside each individual line.
    lines = [
        " ".join(line.split())
        for line in raw.splitlines()
    ]

    return "\n".join(
        line
        for line in lines
        if line
    ).strip()


def _format_action_result(action: Dict) -> str:
    description = action.get("description", "")
    status = action.get("status", "pending")
    result = action.get("result")

    if status == "completed":
        return (
            "✓ {0}\n"
            "  Result: {1}".format(
                description,
                _sanitize_user_facing_result(result),
            )
        )

    if status == "unauthorized":
        return (
            "✗ {0}\n"
            "  Not authorized: {1}".format(
                description,
                _sanitize_user_facing_result(result),
            )
        )

    if status == "failed":
        return (
            "✗ {0}\n"
            "  Failed: {1}".format(
                description,
                _sanitize_user_facing_result(result),
            )
        )

    return (
        "• {0}\n"
        "  Status: {1}".format(description, status)
    )


def _build_final_response(actions: List[Dict]) -> str:
    if not actions:
        return "No actions were identified."

    lines = [
        "Here is the result of your request:",
        "",
    ]

    for action in actions:
        lines.append(
            _format_action_result(action)
        )
        lines.append("")

    return "\n".join(lines).strip()


def _finalize_approved_workflow(
    state: AgentState,
    action: Dict,
) -> bool:
    """Close the durable normal-chat proposal after its action finishes.

    Normal-chat confirmations persist one current action. Once that approved
    action has actually completed (or failed authorization/execution), its
    workflow row must not remain indefinitely in APPROVED state.
    """

    proposal_id = str(
        state.get("workflow_proposal_id") or ""
    ).strip()

    if not proposal_id:
        return False

    action_status = str(action.get("status") or "")
    if action_status not in {
        "completed",
        "failed",
        "unauthorized",
    }:
        return False

    session = SessionLocal()

    try:
        row = session.get(
            WorkflowProposal,
            proposal_id,
        )

        if row is None or row.status != "APPROVED":
            return False

        if action_status == "completed":
            row.status = "COMPLETED"
            row.last_error = None
        else:
            row.status = "FAILED"
            row.last_error = str(
                action.get("result")
                or "The approved action did not complete."
            )

        row.updated_at = utcnow()
        session.commit()
        return True

    except Exception:
        session.rollback()
        # The domain action result is already known. Do not rewrite it as a
        # success/failure based on audit-row cleanup. Codex will later move
        # normal-chat writes under the shared execution ledger.
        return False

    finally:
        session.close()


def next_action_node(state: AgentState) -> dict:
    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    if index >= len(actions):
        return {
            "finished": True,
            "response": _build_final_response(actions),
        }

    current_action = dict(actions[index])

    # ---------------------------------------------------------
    # Unauthorized action
    # ---------------------------------------------------------
    if (
        state.get("authorized") is False
        and state.get("auth_error")
    ):
        current_action["status"] = "unauthorized"
        current_action["result"] = state["auth_error"]

    # ---------------------------------------------------------
    # Successfully executed tool
    # ---------------------------------------------------------
    elif state.get("tool_result") is not None:
        tool_result = state["tool_result"]

        if tool_result.startswith("That action failed:"):
            current_action["status"] = "failed"
        elif tool_result.startswith("Unknown tool"):
            current_action["status"] = "failed"
        else:
            current_action["status"] = "completed"

        current_action["result"] = tool_result

    # ---------------------------------------------------------
    # Specialist answered without a tool
    # ---------------------------------------------------------
    else:
        current_action["status"] = "completed"
        current_action["result"] = state.get(
            "response",
            "Action completed.",
        )

    updated_actions = list(actions)
    updated_actions[index] = current_action

    # If this action came from a durable normal-chat approval, close that
    # exact proposal now that the approved operation has a real outcome.
    proposal_finalized = _finalize_approved_workflow(
        state,
        current_action,
    )

    next_index = index + 1

    if next_index >= len(updated_actions):
        result = {
            "planned_actions": updated_actions,
            "current_action_index": next_index,

            "pending_tool_call": None,
            "pending_ai_message": None,
            "tool_result": None,

            "authorized": False,
            "auth_error": None,

            "finished": True,
            "response": _build_final_response(
                updated_actions
            ),
        }
        if proposal_finalized:
            result["workflow_proposal_id"] = None
        return result

    result = {
        "planned_actions": updated_actions,
        "current_action_index": next_index,

        "pending_tool_call": None,
        "pending_ai_message": None,
        "tool_result": None,

        "authorized": False,
        "auth_error": None,

        "finished": False,
    }
    if proposal_finalized:
        result["workflow_proposal_id"] = None
    return result


def route_after_action(state: AgentState) -> str:
    if state.get("finished"):
        return "save"

    return "specialist"
