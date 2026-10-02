from __future__ import annotations

import inspect
import json
import re
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
- documents: search, list, read, retrieve, view, download,
  or inspect previously uploaded/approved household documents,
  including document metadata and records
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
- Repair/service intent takes precedence over incidental price information:
  a request whose primary action is to log or record an appliance repair/service
  is maintenance even when it includes provider, date, or cost. Example:
  "Log today's geyser repair for Rs 2500 by CoolCare" is ONE maintenance action.
  The deterministic cross-domain layer may later offer to log the repair cost
  as a finance expense; do not convert the repair itself into an expense here.
- Spending-centered repair language remains finance. Example:
  "I spent Rs 2500 on geyser repair today" or an explicit request to
  "log the repair expense" is finance.
- Requests to search for, find, list, read, retrieve, view,
  download, inspect, or get a previously uploaded document
  MUST use the documents domain.
- A request such as "get my previous electricity bill",
  "find the invoice from ABC", "show the uploaded warranty",
  or "retrieve that document" is a documents action.
- A previous failed tool result such as "unavailable",
  "not found", or "try again later" is historical context only.
  Never copy that previous failure into the current action or
  assume the document is currently unavailable without executing
  the appropriate document tool again.

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


_REPAIR_OR_SERVICE_RE = re.compile(
    r"\b(?:repair|repairs|repaired|repairing|service|serviced|servicing)\b",
    flags=re.IGNORECASE,
)

_REPAIR_RECORD_COMMAND_RE = re.compile(
    r"\b(?:log|record|add)\b.{0,90}\b(?:repair|repairs|service)\b",
    flags=re.IGNORECASE,
)

_PASSIVE_REPAIR_RECORD_RE = re.compile(
    r"\b(?:was|were|has been|have been)?\s*(?:repaired|serviced)\b",
    flags=re.IGNORECASE,
)

_EXPLICIT_FINANCE_REQUEST_RE = re.compile(
    r"\b(?:log|record|add)\b.{0,60}\b(?:expense|payment)\b"
    r"|\b(?:expense|payment)\b.{0,60}\b(?:log|record|add)\b",
    flags=re.IGNORECASE,
)

_SPENDING_CENTERED_RE = re.compile(
    r"^\s*(?:i|we)\s+(?:spent|paid|spend|pay)\b"
    r"|\b(?:repair|service)\s+bill\b"
    r"|\bbill\s+for\s+(?:the\s+)?(?:repair|service)\b",
    flags=re.IGNORECASE,
)


def _apply_repair_domain_guard(
    message: str,
    actions: List[dict],
) -> List[dict]:
    """Correct one narrow planner ambiguity deterministically.

    A repair/service record remains Maintenance when price/provider metadata is
    incidental. Explicit expense/payment or spending-centered requests remain
    Finance. Multi-action plans are never rewritten here.
    """

    if len(actions) != 1:
        return actions

    raw_message = str(message or "").strip()
    if not raw_message:
        return actions

    if _REPAIR_OR_SERVICE_RE.search(raw_message) is None:
        return actions

    current = actions[0]
    if not isinstance(current, dict):
        return actions

    # Only correct the observed misclassification. Never rewrite another
    # non-finance domain or an already-correct Maintenance action.
    if str(current.get("domain") or "").strip() != "finance":
        return actions

    explicit_finance_request = (
        _EXPLICIT_FINANCE_REQUEST_RE.search(raw_message)
        is not None
    )

    spending_centered = (
        _SPENDING_CENTERED_RE.search(raw_message)
        is not None
    )

    repair_record_request = (
        _REPAIR_RECORD_COMMAND_RE.search(raw_message)
        is not None
        or _PASSIVE_REPAIR_RECORD_RE.search(raw_message)
        is not None
    )

    if (
        not repair_record_request
        or explicit_finance_request
        or spending_centered
    ):
        return actions

    corrected = dict(current)
    corrected["domain"] = "maintenance"
    corrected["intent"] = "log repair"

    return [corrected]


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

    if (
        not state.get("pending_edit_context")
        and not state.get("suggestion_context")
    ):
        actions = _apply_repair_domain_guard(
            str(state.get("message") or ""),
            actions,
        )

    return {
        "planned_actions": actions,
        "current_action_index": 0,
    }
