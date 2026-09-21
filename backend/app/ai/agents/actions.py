from __future__ import annotations

from app.ai.agents.state import AgentState


def _format_action_result(action: dict) -> str:
    description = action.get("description", "")
    status = action.get("status", "pending")
    result = action.get("result")

    if status == "completed":
        return (
            f"✓ {description}\n"
            f"  Result: {result}"
        )

    if status == "unauthorized":
        return (
            f"✗ {description}\n"
            f"  Not authorized: {result}"
        )

    if status == "failed":
        return (
            f"✗ {description}\n"
            f"  Failed: {result}"
        )

    return (
        f"• {description}\n"
        f"  Status: {status}"
    )


def _build_final_response(actions: list[dict]) -> str:
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

    next_index = index + 1

    if next_index >= len(updated_actions):
        return {
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

    return {
        "planned_actions": updated_actions,
        "current_action_index": next_index,

        "pending_tool_call": None,
        "pending_ai_message": None,
        "tool_result": None,

        "authorized": False,
        "auth_error": None,

        "finished": False,
    }


def route_after_action(state: AgentState) -> str:
    if state.get("finished"):
        return "save"

    return "specialist"