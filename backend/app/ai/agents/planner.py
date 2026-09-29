from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.agents.llm import get_llm
from app.ai.agents.state import AgentState
from typing import Literal

class PlannedActionModel(BaseModel):
    domain: Literal[
        "finance",
        "tasks",
        "food",
        "maintenance",
        "documents",
        "general",
    ] = Field(
        description="The single domain for this action"
    )

    intent: str = Field(
        description="Short description of the requested action"
    )

    description: str = Field(
        description="The specific action the user wants performed"
    )


class PlanModel(BaseModel):
    actions: list[PlannedActionModel]


_PLANNER_PROMPT = """
You are the planning component of a household management assistant.
Break the user's CURRENT request into independent actions.
Available domains:
- finance:
  expenses, payments, advances already paid, budgets, bills, spending
- tasks:
  to-dos, chores, reminders, scheduled activities, task management
- food:
  groceries, grocery lists, food inventory
- maintenance:
  appliances, household problems, maintenance issues, repairs
- documents:
  uploaded document metadata, receipts, bills, warranties,
  document records
- general:
  questions or requests that do not require a household action
The user may be continuing a previous conversation.
Relevant context from previous interactions may be provided below.
Use that context ONLY to resolve references such as:
- "it"
- "that"
- "them"
- "those"
- "the previous one"
- "make it two"
- "change its quantity"
- "remove it"
- "delete that"
Do NOT treat previous context as a new user request.
The CURRENT user message always takes priority.
Rules:
1. Identify EVERY distinct action requested by the CURRENT user.
2. A single user message may contain multiple actions.
3. Each action must have exactly ONE domain.
4. Never return values such as "maintenance/tasks".
5. Use the user's INTENT, not merely the object mentioned.
6. Do not invent actions.
7. An already-paid advance is a finance action.
8. Creating a budget is a finance action ONLY when the user explicitly
   requests a budget or spending limit.
9. Preserve amounts, dates, items and descriptions.
10. If the current request modifies, deletes, completes, or otherwise
    acts on an existing item mentioned in previous context, preserve
    the identity/reference needed by the specialist.
11. Do not reinterpret a previous completed action as a new action.
12. If a reference cannot be resolved reliably from the available
    context, classify the request as general and explain the ambiguity
    in the action description rather than inventing an entity.
Reminder rules:
13. A request beginning with or containing "remind me", "remind mom",
    "remind [person]", "set a reminder", or equivalent is a tasks action.
14. "Remind me to X" should create a task with X as the task title
    and a reminder time.
15. "Remind [person] to/about X" should create a task with the
    specified household member as assigned_to when that identity can
    be resolved.
16. Relative time expressions such as "tomorrow", "this Saturday",
    "in 2 hours", "in the morning", and "tomorrow evening" must be
    preserved in the action description for the specialist to resolve.
17. Do not classify a reminder as a calendar event unless the user
    explicitly requests an event/calendar appointment.
Inventory rules:
18. "Add X to inventory" means add an existing/stocked household item
    using add_inventory_item.
19. "Add X to the grocery list" means add a shopping-list item using
    add_grocery_item.
20. Never substitute a grocery action for an inventory action.
Documents:
21. Requests to create, view, update, or delete document metadata belong
    to the documents domain.
Grocery examples:
Previous context:
"Add bananas to the grocery list."
Assistant:
"Added 1 bananas to the grocery list. Grocery item id: abc123"
Current user:
"Make it a dozen."
Correct action:
domain = food
intent = Update existing grocery item quantity
description = Update grocery item abc123 (bananas) to quantity 12.
Current user:
"Remove them."
Correct action:
domain = food
intent = Delete existing grocery item
description = Delete grocery item abc123 (bananas).
Current user:
"Add apples too."
Correct action:
domain = food
intent = Add grocery item
description = Add apples to the grocery list.
Important:
"Add apples too" creates a NEW action.
"Make it a dozen" modifies the EXISTING referenced item.
Example:
User:
"Schedule an AC repair for Saturday and log the ₹500 advance I paid."
Actions:
1. domain = tasks
   Schedule/create a household task for the AC repair on Saturday.
2. domain = finance
   Record the ₹500 advance that has already been paid.
Return only the structured plan.
"""


def planner_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)

    structured_llm = llm.with_structured_output(PlanModel)

    context = "\n".join(
        state.get("retrieved_context") or []
    ) or "(none)"

    user_message = f"""
Relevant context from previous interactions:

{context}

CURRENT USER REQUEST:

{state["message"]}
"""

    result = structured_llm.invoke(
        [
            SystemMessage(content=_PLANNER_PROMPT),
            HumanMessage(content=user_message),
        ]
    )

    actions = [
        {
            "domain": action.domain,
            "intent": action.intent,
            "description": action.description,
            "status": "pending",
            "result": None,
        }
        for action in result.actions
    ]

    return {
        "planned_actions": actions,
        "current_action_index": 0,
    }