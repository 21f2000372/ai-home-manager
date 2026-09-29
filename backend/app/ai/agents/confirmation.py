from __future__ import annotations

from threading import Lock
from typing import Any

from app.ai.agents.state import AgentState


# ------------------------------------------------------------------
# Temporary in-memory pending confirmation store
# ------------------------------------------------------------------

_PENDING: dict[str, dict[str, Any]] = {}
_LOCK = Lock()


YES_RESPONSES = {
    "yes",
    "y",
    "yeah",
    "yep",
    "confirm",
    "confirmed",
    "proceed",
    "do it",
    "add it",
    "continue",
}


NO_RESPONSES = {
    "no",
    "n",
    "nope",
    "cancel",
    "stop",
    "don't",
    "do not",
    "skip it",
}


def _confirmation_key(
    state: AgentState,
) -> str:
    """
    Prefer session_id because it normally identifies
    the active user conversation.
    """

    return str(
        state.get("session_id")
        or state.get("conversation_id")
        or ""
    )


def _parse_decision(
    message: str,
) -> str | None:
    value = " ".join(
        (message or "")
        .casefold()
        .strip()
        .split()
    )

    if value in YES_RESPONSES:
        return "yes"

    if value in NO_RESPONSES:
        return "no"

    return None


def store_pending_confirmation(
    state: AgentState,
) -> None:
    key = _confirmation_key(state)

    if not key:
        return

    payload = {
        # Most important part:
        # preserve the EXACT tool call selected previously.
        "pending_tool_call": state.get(
            "pending_tool_call"
        ),

        "pending_ai_message": state.get(
            "pending_ai_message"
        ),

        "planned_actions": state.get(
            "planned_actions",
            [],
        ),

        "current_action_index": state.get(
            "current_action_index",
            0,
        ),

        "duplicate_status": state.get(
            "duplicate_status"
        ),

        "duplicate_details": state.get(
            "duplicate_details"
        ),
    }

    with _LOCK:
        _PENDING[key] = payload


def resume_confirmation_node(
    state: AgentState,
) -> dict:
    """
    Runs before normal retrieval/planning.

    If there is a pending duplicate confirmation and the user
    says yes/no, restore the previous tool call instead of
    asking the LLM to recreate it.
    """

    key = _confirmation_key(state)

    if not key:
        return {
            "confirmation_resolution": "none"
        }

    with _LOCK:
        pending = _PENDING.get(key)

    if not pending:
        return {
            "confirmation_resolution": "none"
        }

    decision = _parse_decision(
        state.get("message", "")
    )

    # User sent some unrelated/new request rather than yes/no.
    # Process it normally.
    if decision is None:
        return {
            "confirmation_resolution": "none"
        }

    with _LOCK:
        _PENDING.pop(
            key,
            None,
        )

    actions = list(
        pending.get(
            "planned_actions",
            [],
        )
    )

    index = int(
        pending.get(
            "current_action_index",
            0,
        )
    )

    # ----------------------------------------------------------
    # YES
    # ----------------------------------------------------------

    if decision == "yes":
        return {
            "confirmation_resolution": "confirmed",

            "planned_actions": actions,
            "current_action_index": index,

            # Restore the EXACT proposed tool call.
            "pending_tool_call": pending.get(
                "pending_tool_call"
            ),

            "pending_ai_message": pending.get(
                "pending_ai_message"
            ),

            "duplicate_status": pending.get(
                "duplicate_status"
            ),

            "duplicate_details": pending.get(
                "duplicate_details"
            ),

            "awaiting_confirmation": False,
            "response": "",
            "finished": False,
        }

    # ----------------------------------------------------------
    # NO
    # ----------------------------------------------------------

    if index < len(actions):
        action = dict(
            actions[index]
        )

        action["status"] = "cancelled"

        action["result"] = (
            "Cancelled because the user did not "
            "confirm the duplicate/conflicting action."
        )

        actions[index] = action

    return {
        "confirmation_resolution": "cancelled",

        "planned_actions": actions,
        "current_action_index": index,

        "pending_tool_call": None,
        "pending_ai_message": None,

        "awaiting_confirmation": False,

        "finished": True,

        "response": (
            "Okay, I won't perform that action."
        ),
    }


def route_after_resume(
    state: AgentState,
) -> str:
    resolution = state.get(
        "confirmation_resolution",
        "none",
    )

    if resolution == "confirmed":
        return "authorize"

    if resolution == "cancelled":
        return "save"

    return "retrieve"


def request_confirmation_node(
    state: AgentState,
) -> dict:
    """
    Store pending exact tool call and return a question to the user.
    """

    store_pending_confirmation(
        state
    )

    details = (
        state.get("duplicate_details")
        or "A similar record already exists."
    )

    return {
        "awaiting_confirmation": True,
        "finished": True,
        "response": (
            f"{details}\n"
            "Do you want me to continue anyway? "
            "Reply yes or no."
        ),
    }