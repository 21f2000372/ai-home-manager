from __future__ import annotations

from app.ai.agents.permissions import is_authorized
from app.ai.agents.state import AgentState


def authorize_node(state: AgentState) -> dict:
    call = state.get("pending_tool_call")

    print("\n========== AUTHORIZE DEBUG ==========")
    print("action index:", state.get("current_action_index"))
    print("pending_tool_call:", call)
    print("authorized:", state.get("authorized"))
    print("=====================================\n")

    if call is None:
        return {
            "authorized": True,
            "auth_error": None,
        }

    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    if index >= len(actions):
        return {
            "authorized": False,
            "auth_error": "No current planned action exists.",
        }

    action = actions[index]

    domain = action.get("domain", "general")
    tool_name = call["name"]
    role = state.get("role", "")

    ok = is_authorized(
        role,
        domain,
        tool_name,
    )

    if ok:
        return {
            "authorized": True,
            "auth_error": None,
        }

    error = (
        f"Role '{role}' isn't permitted to do "
        f"'{tool_name}' in {domain}."
    )

    return {
        "authorized": False,
        "auth_error": error,
    }


def route_after_specialist(state: AgentState) -> str:
    if state.get("pending_tool_call"):
        # Cross-domain suggestion continuations receive an RBAC gate BEFORE
        # duplicate/conflict lookup so a model revision cannot cause reads in
        # a target domain the current role is not allowed to act on.
        if state.get("confirmation_kind") == "suggestion":
            return "suggestion_authorize"
        return "authorize"

    return "next_action"


def route_after_authorize(state: AgentState) -> str:
    if state.get("authorized"):
        return "execute"

    return "next_action"