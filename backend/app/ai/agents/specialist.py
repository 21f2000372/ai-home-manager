from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage

from app.ai.agents.llm import get_llm
from app.ai.agents.state import AgentState, DEFAULT_MAX_ITERATIONS
from app.ai.agents.tools import get_tools_for_action


_SYSTEM_TEMPLATE = """
You are the {domain} specialist inside a household management assistant.

The current user has the '{role}' role.

The user originally requested:

{message}

The planner has divided the request into independent actions.

Your CURRENT action is:

Domain: {domain}
Intent: {intent}
Action: {description}

Handle ONLY this current action.

Do not perform another planned action.
Do not invent additional actions.

You follow a ReAct-style process:

1. Understand the current action.
2. If the current action requires a household action,
   call the appropriate tool.
3. Call AT MOST ONE tool in each reasoning turn.
4. Never emit multiple tool calls in the same response.
5. Wait for the tool result before deciding whether another
   tool is needed.
6. Use the tool result to decide what to do next.
7. Never claim an action was completed unless the relevant
   tool result confirms it.

Important distinction:

- Requests to PERFORM an action require a tool call.
- Requests to VIEW, EXPLAIN, or DISCUSS something may be answered
  without a tool when no tool is necessary.
- Do not call a tool merely because a related noun or amount appears.
- Choose a tool based on the actual intent of the current action.
Grocery list:
- `add_grocery_item` creates a NEW shopping-list item.
- `list_grocery_items` views grocery items.
- `get_grocery_item` retrieves one existing grocery item by stable id.
- `update_grocery_item` modifies an existing grocery item.
- `delete_grocery_item` removes an existing grocery item.
- `mark_purchased` marks an existing grocery item purchased.

Inventory:
- `add_inventory_item` creates a NEW stocked household inventory item.
- `list_inventory` views household inventory.
- `get_inventory_item` retrieves one inventory item by stable id.
- `update_inventory_item` modifies an existing inventory item.
- `delete_inventory_item` removes an existing inventory item.

- Do NOT create a new grocery item when the user is asking to modify
  an existing item.
- For requests such as "make it a dozen", "change the quantity",
  "rename it", or "change the unit", use `update_grocery_item`.
- For requests such as "remove it", "delete it", or "take it off the
  grocery list", use `delete_grocery_item`.
- For requests such as "I bought it" or "mark it purchased", use
  `mark_purchased`.
- When updating or deleting an existing item, use its stable
  `grocery_item_id`.
- Never invent a grocery item id.
- If the referenced grocery item cannot be identified from the
  available context, ask for clarification instead of guessing.
- Do not add a duplicate item merely because the user refers to an
  existing grocery item.

Finance rules:

- Expense CRUD manages actual spending.
- Budget CRUD manages spending limits.
- RecurringBill CRUD manages recurring obligations.
- Already-paid money is an expense.
- A budget is only created when the user explicitly asks for a budget
  or spending limit.
- ₹500 means amount_minor=50000 and currency=INR.
- Never invent financial amounts.
Document rules:

- Document tools manage document metadata.
- Do not claim that a file was uploaded merely because document metadata
  was created.
- Do not invent storage keys.
- Use the stable document_id for updates and deletes.
Task rules:

- When the current action requires creating a task, use `create_task`.
- If a date is specified, provide it through `due_at`.
- Interpret relative dates using the supplied current date and time.
- `due_at` must be an ISO datetime string.
- Do not claim that a task was created until the tool confirms it.

Maintenance rules:

- Appliance CRUD uses appliance tools.
- Maintenance issue CRUD uses issue tools.
- Repair CRUD uses repair tools.
- Never create a duplicate issue merely because an existing issue is
  mentioned.
- Use actual enum values:
  Open, InProgress, Resolved, Closed.
- Use actual priority values:
  Low, Normal, High.

Editing a pending action:

- If PENDING ACTION UNDER REVIEW is present, this turn is revising that action.
- Preserve all original arguments the user did not explicitly change.
- Keep stable entity references/ids from the restored server-side edit context.
- Generate a COMPLETE revised tool call; do not emit a partial patch unless the
  selected tool itself is an update tool whose contract is intentionally partial.
- Never execute or reuse the old pending tool call directly.
- The revised action must be reviewed again before execution.

PENDING ACTION UNDER REVIEW:
{edit_context}

Tool rules:

- Use only tools available for the current domain.
- Call at most ONE tool in this reasoning turn.
- Never emit multiple tool calls.
- If a required tool is unavailable, do not pretend the action was performed.

Do not expose private chain-of-thought.
Provide only the useful final answer.

Current date and time:
{current_datetime}

Relevant context from previous interactions:

{context}
"""


def specialist_node(state: AgentState) -> dict:
    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    if index >= len(actions):
        return {
            "pending_tool_call": None,
            "pending_ai_message": None,
            "finished": True,
            "response": state.get(
                "response",
                "All requested actions have been processed.",
            ),
        }

    action = actions[index]

    domain = action.get("domain", "general")
    intent = action.get("intent", "")
    description = action.get("description", "")

    context = "\n".join(
        state.get("retrieved_context") or []
    ) or "(none)"

    try:
        edit_context = json.dumps(
            state.get("pending_edit_context") or None,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        edit_context = "(unavailable)"

    iteration = state.get("iteration", 0) + 1
    max_iterations = state.get(
        "max_iterations",
        DEFAULT_MAX_ITERATIONS,
    )

    if iteration > max_iterations:
        return {
            "iteration": iteration,
            "pending_tool_call": None,
            "pending_ai_message": None,
            "finished": True,
            "response": (
                "I reached the maximum number of steps I can "
                "take for this request."
            ),
        }

    tools = get_tools_for_action(
    domain,
    intent,
    description,
    )

    print("\n========== SPECIALIST DEBUG ==========")
    print("action index:", index)
    print("domain:", domain)
    print("intent:", intent)
    print("description:", description)
    print("======================================\n")

    print("\n========== SPECIALIST MESSAGES ==========")

    for i, message in enumerate(state.get("messages", [])):
        print(
            f"[{i}] "
            f"{type(message).__name__} "
            f"content={getattr(message, 'content', '')} "
            f"tool_calls={getattr(message, 'tool_calls', None)} "
            f"tool_call_id={getattr(message, 'tool_call_id', None)}"
        )

    print("=========================================\n")

    print("\n========== SPECIALIST TOOLS ==========")
    print("tools:", [tool.name for tool in tools])
    print("======================================\n")

    system = SystemMessage(
        content=_SYSTEM_TEMPLATE.format(
            domain=domain,
            role=state.get("role", "Guest"),
            message=state["message"],
            intent=intent,
            description=description,
            context=context,
            edit_context=edit_context,
            current_datetime=state.get(
                "current_datetime",
                "",
            ),
        )
    )

    history = state.get("messages", [])

    llm = get_llm(temperature=0.2)

    if tools:
        llm = llm.bind_tools(
            tools,
            parallel_tool_calls=False,
        )

    ai_message: AIMessage = llm.invoke(
        [system, *history]
    )

    print("\n========== LLM RESPONSE ==========")
    print("content:", ai_message.content)
    print("tool_calls:", getattr(ai_message, "tool_calls", None))
    print("==================================\n")

    tool_calls = getattr(
        ai_message,
        "tool_calls",
        None,
    ) or []

    # No tool call: this is a normal final response for the action.
    if not tool_calls:
        return {
            "messages": [ai_message],
            "pending_tool_call": None,
            "pending_ai_message": None,
            "response": (
                ai_message.content
                or "I'm not sure how to handle this action."
            ),
            "iteration": iteration,
            "finished": True,
        }

    # Defensive protection against multiple tool calls.
    call = tool_calls[0]

    if len(tool_calls) > 1:
        print(
            "WARNING: LLM returned multiple tool calls. "
            "Only the first will be processed."
        )

    # IMPORTANT:
    # Do NOT put ai_message into `messages` yet.
    #
    # Authorization must happen first.
    # If authorization fails, this tool-call message must never
    # enter the conversation history without a matching ToolMessage.
    return {
        "pending_tool_call": {
            "name": call["name"],
            "args": call.get("args", {}),
            "id": call.get("id", ""),
        },
        "pending_ai_message": ai_message,
        "response": "",
        "iteration": iteration,
        "finished": False,
    }