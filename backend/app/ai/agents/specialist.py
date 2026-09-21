from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from app.ai.agents.domain_mesh import allowed_tool_names_for_domain, build_mesh_summary, get_domain_spec
from app.ai.agents.llm import get_llm
from app.ai.agents.prompt_builder import PromptContext, ToolPromptBuilder
from app.ai.agents.state import AgentState, DEFAULT_MAX_ITERATIONS
from app.ai.agents.tool_catalog import ToolCatalogRepository
from app.ai.agents.tools import ALL_TOOLS_BY_NAME, TOOLSETS


_SYSTEM_TEMPLATE = """
You are the {domain} specialist inside a household management assistant.

You are running inside a Federated Agent Mesh. Your domain graph owns its
own context and may only use tools exposed by its mesh contract.

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

Mesh contract:

{mesh_summary}

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
- Bill extraction uses `extract_bill_information` when readable bill text
  is available in the user's message or retrieved context.
- If readable bill text is not available, create/update document metadata
  only and ask for the bill text/OCR/file pipeline to extract details.
- A bill document can be linked to a finance or maintenance record through
  `link_document_to_record`.
Task rules:

- When the current action requires creating a task, use `create_task`.
- When updating a task and the user gives title/description/details instead
  of a task id, use `update_task_by_search` or `search_tasks`.
- If multiple tasks match a search, ask for clarification and do not update.
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

    spec = get_domain_spec(domain)
    allowed_tool_names = allowed_tool_names_for_domain(domain)
    candidates = []
    try:
        from app.rag.service import get_default_service

        candidates = ToolCatalogRepository(get_default_service()).search(
            f"{intent} {description}",
            role=state.get("role", "Guest"),
            tenant_id=state.get("user_id") or "global",
            domain=domain,
            n_results=5,
        )
    except Exception:
        candidates = []
    candidate_tools = [
        ALL_TOOLS_BY_NAME[item["tool_name"]]
        for item in candidates
        if item["tool_name"] in ALL_TOOLS_BY_NAME
        and item["tool_name"] in allowed_tool_names
    ]
    mesh_tools = [
        ALL_TOOLS_BY_NAME[name]
        for name in spec.exposed_tools
        if name in ALL_TOOLS_BY_NAME
    ]
    if candidate_tools:
        seen = {tool.name for tool in candidate_tools}
        tools = [*candidate_tools, *(tool for tool in mesh_tools if tool.name not in seen)]
    else:
        tools = mesh_tools or [
            tool
            for tool in TOOLSETS.get(domain, [])
            if tool.name in allowed_tool_names
        ]

    compact_prompt = ToolPromptBuilder().build(PromptContext(
        role=state.get("role", "Guest"),
        tenant_id=state.get("user_id") or "global",
        action={"domain": domain, "intent": intent, "description": description},
        candidates=[
            {"name": tool.name, "purpose": (tool.description or "").split(".")[0]}
            for tool in tools
        ],
        entity_context=[item for item in context.splitlines() if item and item != "(none)"][:5],
        result=state.get("tool_result") or "",
        current_datetime=state.get("current_datetime", ""),
    ))
    mesh_prompt = "\n".join((
        "Federated mesh:",
        build_mesh_summary(domain),
        "Rules:",
        "- Handle only the current action.",
        "- Use owned tools or public proxy tools only.",
        "- Call at most one tool per reasoning turn.",
        "- Never claim completion until a tool result confirms it.",
        "- For bills, extract readable bill text before logging finance records.",
        "- Ask for missing IDs, amounts, dates, readable bill text, or permissions instead of guessing.",
    ))
    system = SystemMessage(content=f"{compact_prompt}\n\n{mesh_prompt}")

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
