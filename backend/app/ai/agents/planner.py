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




_REPAIR_EXPENSE_WORD_RE = re.compile(
    r"\b(?:repair|repairs|repaired|service|servicing|maintenance)\b",
    re.IGNORECASE,
)

_REPAIR_EXPENSE_FINANCE_VERB_RE = re.compile(
    r"\b(?:log|record|spent|spend|paid|expense)\b",
    re.IGNORECASE,
)

_REPAIR_EXPENSE_MONEY_RE = re.compile(
    r"(?:"
    r"₹\s*\d+(?:\.\d{1,2})?"
    r"|\b(?:rs\.?|inr)\s*\d+(?:\.\d{1,2})?\b"
    r"|\b\d+(?:\.\d{1,2})?\s*(?:rs\.?|inr)\b"
    r")",
    re.IGNORECASE,
)


_REPAIR_EXPLICIT_FINANCE_RE = re.compile(
    r"\b(?:expense|expenses|spent|spend|paid|payment|payments|"
    r"cost|costs|price|charged|charge)\b",
    re.IGNORECASE,
)


_CALENDAR_EVENT_WORD_RE = re.compile(
    r"\b(?:appointment|appointments|meeting|meetings|party|parties)\b",
    re.IGNORECASE,
)

_EXPLICIT_TASK_WORD_RE = re.compile(
    r"\b(?:task|tasks|to[- ]?do|reminder|reminders|remind)\b",
    re.IGNORECASE,
)


def _apply_calendar_event_routing(
    actions: List[dict],
) -> List[dict]:
    """Prefer calendar-event tools for event nouns inside the tasks domain.

    Appointment, meeting and party are treated as calendar events by default.
    Explicit task/to-do/reminder wording wins, so requests such as
    "remind me about my appointment" remain task/reminder actions.
    """

    routed = []

    for action in actions:
        updated = dict(action)

        if (
            str(updated.get("domain") or "").strip().casefold()
            != "tasks"
        ):
            routed.append(updated)
            continue

        intent = str(
            updated.get("intent") or ""
        ).strip()
        description = str(
            updated.get("description") or ""
        ).strip()

        context = "{} {}".format(
            intent,
            description,
        )

        if (
            _CALENDAR_EVENT_WORD_RE.search(context)
            and not _EXPLICIT_TASK_WORD_RE.search(context)
            and "calendar" not in context.casefold()
        ):
            updated["intent"] = (
                "calendar event {}".format(intent).strip()
            )

        routed.append(updated)

    return routed


def _is_finance_first_repair_expense(message: str) -> bool:
    """Return True for explicit paid/logged repair expenses.

    Supported money forms include both prefix and suffix currency notation,
    for example ``Rs 2500``, ``2500 Rs``, ``INR 2500``, ``2500 INR`` and
    ``₹2500``.  A bare repair/service request remains Maintenance.
    """

    text = " ".join(str(message or "").split())
    if not text:
        return False

    return bool(
        _REPAIR_EXPENSE_WORD_RE.search(text)
        and _REPAIR_EXPENSE_FINANCE_VERB_RE.search(text)
        and _REPAIR_EXPENSE_MONEY_RE.search(text)
    )


def _is_bare_repair_request(message: str) -> bool:
    """Return True for repair/service intent with no explicit finance facts.

    This is evaluated only from the CURRENT user message. It deliberately
    ignores planner output and retrieved context so a prior amount cannot leak
    into a fresh repair request.
    """

    text = " ".join(str(message or "").split())
    if not text:
        return False

    return bool(
        _REPAIR_EXPENSE_WORD_RE.search(text)
        and not _REPAIR_EXPENSE_MONEY_RE.search(text)
        and not _REPAIR_EXPLICIT_FINANCE_RE.search(text)
    )


def _apply_finance_first_repair_routing(
    state: AgentState,
    actions: List[dict],
) -> List[dict]:
    """Apply deterministic repair routing from the CURRENT user message.

    - Explicit currency amount + repair/service -> Finance first.
    - Bare repair/service with no money/payment facts -> Maintenance.

    Cross-domain continuations and pending edits are intentionally excluded so
    an accepted Finance -> Maintenance follow-up cannot be routed back to
    Finance again.
    """

    if state.get("suggestion_context") or state.get("pending_edit_context"):
        return actions

    if len(actions) != 1:
        return actions

    message = str(state.get("message") or "").strip()

    if _is_finance_first_repair_expense(message):
        updated = dict(actions[0])
        updated["domain"] = "finance"
        return [updated]

    # Defensive reverse guard: if the LLM invents an amount or copies a prior
    # Finance repair example, trust the current user message instead.
    if (
        _is_bare_repair_request(message)
        and str(actions[0].get("domain") or "").strip().casefold() == "finance"
    ):
        updated = dict(actions[0])
        updated["domain"] = "maintenance"
        updated["intent"] = (
            "log repair"
            if re.search(r"\b(?:log|record)\b", message, re.IGNORECASE)
            else "maintenance request"
        )
        updated["description"] = message
        return [updated]

    return actions


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
- Appointment, meeting, and party are calendar-event concepts by default and
  should use calendar-event tooling when scheduled/created/updated/deleted.
- Explicit task/to-do/reminder wording takes precedence; for example, a task to
  prepare for a party or a reminder about an appointment remains a task.
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
- A repair/service request is Finance first only when the CURRENT USER REQUEST
  itself explicitly contains a monetary amount with a currency marker, or
  explicitly states an expense/payment/spending intent.
- Never infer, copy, or carry an amount or currency from examples, retrieved
  context, or an earlier request into the current request.
- A repair/service request with no explicit monetary/payment facts belongs to
  Maintenance. Do not invent a Finance action for it.
- Do not add a second explicit Maintenance action for the same paid-repair
  request; deterministic cross-domain logic may offer Maintenance afterward.
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

    actions = _apply_finance_first_repair_routing(
        state,
        actions,
    )

    actions = _apply_calendar_event_routing(
        actions,
    )

    return {
        "planned_actions": actions,
        "current_action_index": 0,
    }
