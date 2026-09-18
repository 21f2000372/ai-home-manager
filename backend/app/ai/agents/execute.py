from __future__ import annotations

from langchain_core.messages import ToolMessage

from app.ai.agents.state import AgentState
from app.ai.agents.tools import ALL_TOOLS_BY_NAME


def execute_node(state: AgentState) -> dict:
    call = state.get("pending_tool_call")
    ai_message = state.get("pending_ai_message")

    print("\n========== EXECUTE DEBUG ==========")
    print("action index:", state.get("current_action_index"))
    print("pending_tool_call:", call)
    print("===================================\n")

    if not call:
        return {
            "tool_result": None,
            "pending_ai_message": None,
        }

    tool_name = call["name"]
    tool_args = call.get("args", {})
    tool_call_id = call.get("id", "")

    tool_fn = ALL_TOOLS_BY_NAME.get(tool_name)

    if tool_fn is None:
        result = f"Unknown tool '{tool_name}'."
    else:
        try:
            result = tool_fn.invoke(tool_args)
        except Exception as exc:
            result = f"That action failed: {exc}"

    result = str(result)

    print("\n========== EXECUTE RESULT ==========")
    print("tool_name:", tool_name)
    print("tool_result:", result)
    print("tool_call_id:", tool_call_id)
    print("====================================\n")

    tool_message = ToolMessage(
        content=result,
        tool_call_id=tool_call_id,
    )

    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    updated_actions = list(actions)

    if index < len(updated_actions):
        updated_action = dict(updated_actions[index])

        updated_action["tool_name"] = tool_name
        updated_action["tool_args"] = tool_args
        updated_action["status"] = "running"

        updated_actions[index] = updated_action

    messages = []

    # The AIMessage containing the tool call is added ONLY now,
    # because authorization has succeeded.
    if ai_message is not None:
        messages.append(ai_message)

    messages.append(tool_message)

    return {
        "tool_result": result,
        "messages": messages,
        "pending_tool_call": None,
        "pending_ai_message": None,
        "planned_actions": updated_actions,
    }