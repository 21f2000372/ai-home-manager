from __future__ import annotations

import json
from typing import List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.ai.agents.llm import get_llm
from app.ai.agents.state import AgentState


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
    actions: List[PlannedActionModel]


_PLANNER_PROMPT = """
You are the planning component of a household management assistant.
Break the user's CURRENT request into independent actions.

Available domains:
- finance: expenses, payments, advances already paid, budgets, bills, spending
- tasks: to-dos, chores, reminders, scheduled activities, task management
- food: groceries, grocery lists, food inventory
- maintenance: appliances, household problems, maintenance issues, repairs
- documents: uploaded document metadata, receipts, bills, warranties,
  document records
- general: questions or requests that do not require a household action

The user may be continuing a previous conversation. Relevant context from
previous interactions may be provided below. Use that context ONLY to resolve
references such as "it", "that", "them", "the previous one", "make it two",
"change its quantity", "remove it", or "delete that". Do NOT treat previous
context as a new user request. The CURRENT user message always takes priority.

EDITING A PENDING ACTION
If a PENDING ACTION UNDER REVIEW is supplied, the current request is an edit to
that exact pending action. In that case:
1. Return exactly ONE revised action for the pending action.
2. Apply only the changes explicitly requested by the user.
3. Preserve every material value/reference that the user did not change,
   including stable entity ids, amounts, dates, quantities, units, assignees,
   and the operation's original purpose.
4. Do not create a second action merely because the user phrased the edit as
   "change", "make it", "instead", "assign", or "move".
5. Do not execute anything. The revised action must go back through specialist,
   consistency checks, and review.
6. If the requested edit is ambiguous, return a general action explaining what
   needs clarification rather than guessing.

General rules:
1. Identify EVERY distinct action requested by the CURRENT user.
2. A single user message may contain multiple actions, except while editing a
   pending action, where exactly one revised action must be returned.
3. Each action must have exactly ONE domain.
4. Never return combined domains such as "maintenance/tasks".
5. Use the user's INTENT, not merely the object mentioned.
6. Do not invent actions.
7. An already-paid advance is a finance action.
8. Creating a budget is a finance action ONLY when explicitly requested.
9. Preserve amounts, dates, items and descriptions.
10. If the current request modifies/deletes/completes an existing item from
    context, preserve the identity/reference needed by the specialist.
11. Do not reinterpret a previous completed action as a new action.
12. If a reference cannot be resolved reliably, classify as general and
    explain the ambiguity rather than inventing an entity.

Reminder rules:
13. "remind me", "remind [person]", "set a reminder" and equivalents are tasks.
14. "Remind me to X" should create a task with X as the title and reminder time.
15. "Remind [person] to/about X" should use the resolved household member.
16. Preserve relative times such as tomorrow, Saturday, or in two hours.
17. Do not classify reminders as calendar events unless explicitly requested.

Inventory rules:
18. "Add X to inventory" means add a stocked household item.
19. "Add X to the grocery list" means add a shopping-list item.
20. Never substitute a grocery action for an inventory action.

Documents:
21. Requests to create/view/update/delete document metadata are documents.

Return only the structured plan.
"""


def _safe_json(value) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        return "(unavailable)"


def planner_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(PlanModel)

    context = "\n".join(
        state.get("retrieved_context") or []
    ) or "(none)"

    edit_context = state.get("pending_edit_context")
    edit_block = (
        _safe_json(edit_context)
        if edit_context
        else "(none)"
    )

    user_message = """
Relevant context from previous interactions:

{context}

PENDING ACTION UNDER REVIEW:

{edit_block}

CURRENT USER REQUEST:

{message}
""".format(
        context=context,
        edit_block=edit_block,
        message=state.get("message", ""),
    )

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
