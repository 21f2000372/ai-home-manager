from __future__ import annotations

import inspect
import json
from typing import List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.ai.agents.llm import get_llm, invoke_with_telemetry
from app.ai.agents.state import AgentState


def _role_llm(role: str, temperature: float):
    """Use role-aware Qwen clients when available, with pre-migration fallback."""

    params = inspect.signature(get_llm).parameters
    if "role" in params:
        return get_llm(temperature=temperature, role=role)
    return get_llm(temperature=temperature)


def _invoke_role_telemetry(runnable, messages, *, node: str, role: str):
    params = inspect.signature(invoke_with_telemetry).parameters
    kwargs = {"node": node}
    if "model_role" in params:
        kwargs["model_role"] = role
    return invoke_with_telemetry(runnable, messages, **kwargs)


class PlannedActionModel(BaseModel):
    domain: Literal[
        "finance",
        "tasks",
        "food",
        "maintenance",
        "documents",
        "general",
    ] = Field(description="The single domain for this action")

    intent: str = Field(description="Short description of the requested action")
    description: str = Field(description="The specific action the user wants performed")


class PlanModel(BaseModel):
    actions: List[PlannedActionModel]


_PLANNER_PROMPT = """
You plan CURRENT requests for a household-management assistant.
Return only the structured plan.

Domains:
- finance: expenses, payments, budgets, recurring bills, spending
- tasks: to-dos, chores, reminders, calendar/scheduled activities
- food: grocery list and household food inventory
- maintenance: appliances, issues, maintenance and repairs
- documents: document metadata/records
- general: no household action or unresolved ambiguity

Rules:
- A single user message MAY contain actions from multiple domains.
- Extract every distinct explicit action in the CURRENT request, preserving the user's order.
- Keep one domain per action. Never collapse independent finance, food, tasks,
  maintenance, or document actions into one action.
- Do not add cross-domain follow-up suggestions here; those are generated later
  by deterministic application code after the explicit plan completes.
- Use intent, not just nouns. Do not invent actions or facts.
- Preserve material amounts, dates, quantities, units, names and references.
- Previous context may resolve references such as "it", "that", "the previous
  one", "make it two", or "delete that"; it is never a new request.
- If a reference cannot be resolved safely, use general and describe the
  ambiguity rather than guessing.
- "remind me/person" is tasks; preserve relative times.
- "add X to inventory" is stocked inventory; "add X to grocery list" is a
  shopping-list action. Do not interchange them.
- A statement such as "I bought 2 kg apples" describes acquired household stock
  and should be planned as a food/inventory action unless the user explicitly
  says it is only a shopping-list item. The cross-domain layer can later offer
  to log the expense.
- A statement centered on money already spent/paid, such as "I spent Rs 300 on
  apples", is finance. The cross-domain layer can later offer the inventory
  follow-up; do not invent that second action here.
- Already-paid spending is finance. Create a budget only when explicitly asked.
- Document CRUD/metadata requests are documents.

Accepted cross-domain follow-up:
- If ACCEPTED CROSS-DOMAIN FOLLOW-UP CONTEXT is present, the user has already
  accepted that follow-up and the CURRENT USER REQUEST supplies its missing
  details. Plan only the actions needed to complete that follow-up.
- An open-ended follow-up may legitimately expand into multiple actions (for
  example several grocery items for one dinner event). Preserve the trusted
  event facts supplied in that context.

Pending-action edit:
- If PENDING ACTION UNDER REVIEW is present, return exactly ONE complete revised
  action for that pending action.
- Apply only the requested change and preserve every unchanged material value
  and stable reference from the restored server-side context.
- Do not execute anything. If the edit is ambiguous, return a general action
  requesting clarification.
""".strip()


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


def _build_planner_user_message(state: AgentState) -> str:
    parts = []

    context_items = [
        str(item).strip()
        for item in (state.get("retrieved_context") or [])
        if str(item).strip()
    ]
    if context_items:
        parts.append(
            "RELEVANT PREVIOUS CONTEXT:\n" + "\n".join(context_items)
        )

    suggestion_context = state.get("suggestion_context")
    if suggestion_context:
        parts.append(
            "ACCEPTED CROSS-DOMAIN FOLLOW-UP CONTEXT:\n"
            + _safe_json(suggestion_context)
        )

    edit_context = state.get("pending_edit_context")
    if edit_context:
        parts.append(
            "PENDING ACTION UNDER REVIEW:\n" + _safe_json(edit_context)
        )

    parts.append(
        "CURRENT USER REQUEST:\n" + str(state.get("message") or "")
    )

    return "\n\n".join(parts)


def planner_node(state: AgentState) -> dict:
    llm = _role_llm("planner", temperature=0.0)
    structured_llm = llm.with_structured_output(
        PlanModel,
        method="function_calling",
    )

    result = _invoke_role_telemetry(
        structured_llm,
        [
            SystemMessage(content=_PLANNER_PROMPT),
            HumanMessage(content=_build_planner_user_message(state)),
        ],
        node="planner",
        role="planner",
    )

    actions = [
        {
            "domain": action.domain,
            "intent": action.intent,
            "description": action.description,
            "status": "pending",
            "result": None,
            "origin": (
                "cross_domain_suggestion"
                if (
                    isinstance(state.get("pending_edit_context"), dict)
                    and state.get("pending_edit_context", {}).get(
                        "confirmation_kind"
                    ) == "suggestion"
                )
                else (
                    "cross_domain_suggestion_continuation"
                    if state.get("suggestion_context")
                    else "explicit"
                )
            ),
        }
        for action in result.actions
    ]

    return {
        "planned_actions": actions,
        "current_action_index": 0,
    }
