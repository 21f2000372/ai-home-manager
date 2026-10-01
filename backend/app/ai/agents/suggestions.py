"""Deterministic cross-domain follow-up suggestions.

The model is not allowed to invent follow-up actions here.  Suggestions are
created from completed tool calls in the current request, filtered through
RBAC before they are shown, persisted durably, and executed only after user
approval and a fresh authorization check.

Compatibility target: Python 3.8+.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.ai.agents.authorize import authorize_node
from app.ai.agents.permissions import is_authorized
from app.ai.agents.state import AgentState
from app.services.suggestion_workflow import (
    SuggestionWorkflowError,
    approve_exact_suggestion,
    persist_suggestion_offer,
    reject_suggestion_for_authorization,
)


_FOOD_WORDS = {
    "food", "grocery", "groceries", "fruit", "vegetable", "vegetables",
    "apple", "apples", "banana", "bananas", "milk", "rice", "bread",
    "flour", "atta", "dal", "oil", "eggs", "egg", "snack", "snacks",
}
_REPAIR_WORDS = {
    "repair", "service", "maintenance", "technician", "plumber",
    "electrician", "appliance", "fan", "ac", "washing machine",
}
_EVENT_GROCERY_WORDS = {
    "dinner", "lunch", "breakfast", "party", "birthday", "guests",
    "guest", "get-together", "get together", "meal",
}
_QUANTITY_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|grams?|litres?|liters?|l|ml|packs?|boxes?|cartons?|pieces?|pcs?|count)?\b",
    re.IGNORECASE,
)
_LEADING_QUANTITY_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|grams?|litres?|liters?|l|ml|packs?|boxes?|cartons?|pieces?|pcs?|count)\b",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _lower(value: Any) -> str:
    return _normalize(value).casefold()


def _action_text(action: Dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            _normalize(action.get("description")),
            _normalize(action.get("intent")),
            _normalize((action.get("tool_args") or {}).get("description")),
            _normalize((action.get("tool_args") or {}).get("category")),
        )
        if part
    )


def _contains_any(text: str, words) -> bool:
    lowered = text.casefold()
    return any(word in lowered for word in words)


def _subject_after_for_or_on(text: str) -> Optional[str]:
    match = re.search(
        r"\b(?:for|on)\s+(.+?)(?:\s+(?:made|paid|on|at)\b|[.,]|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    subject = _normalize(match.group(1))
    subject = re.sub(
        r"^(?:the\s+)?(?:purchase\s+of\s+)?",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    return subject or None


def _extract_food_subject(action: Dict[str, Any]) -> Optional[str]:
    args = dict(action.get("tool_args") or {})
    description = _normalize(args.get("description"))
    action_description = _normalize(action.get("description"))

    for candidate in (description, action_description):
        if not candidate:
            continue
        subject = _subject_after_for_or_on(candidate)
        if subject:
            # Remove obvious money/quantity prefixes while preserving the item.
            subject = re.sub(
                r"^(?:rs\.?|₹|inr)\s*\d+(?:\.\d+)?\s*",
                "",
                subject,
                flags=re.IGNORECASE,
            )
            quantity = _LEADING_QUANTITY_RE.match(subject)
            if quantity:
                subject = subject[quantity.end():].strip()
            if subject:
                return subject

    category = _normalize(args.get("category"))
    if category and category.casefold() not in {"food", "grocery", "groceries"}:
        return category
    return None


def _extract_quantity(action: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    text = _normalize(action.get("description"))

    # Prefer an explicit physical/count unit so a money amount such as
    # "Rs 300" is never mistaken for "300 apples".
    for match in _QUANTITY_RE.finditer(text):
        unit = _normalize(match.group(2)) or None
        if not unit:
            continue
        try:
            quantity = float(match.group(1))
        except (TypeError, ValueError):
            continue
        return quantity, unit

    return None, None


def _extract_money_from_action(
    action: Dict[str, Any],
) -> Tuple[Optional[int], Optional[str]]:
    text = _normalize(action.get("description"))
    match = _MONEY_RE.search(text)
    if not match:
        return None, None
    try:
        major = float(match.group(1))
    except (TypeError, ValueError):
        return None, None
    if major < 0:
        return None, None
    return int(round(major * 100)), "INR"


def _repair_subject(action: Dict[str, Any]) -> str:
    args = dict(action.get("tool_args") or {})
    action_description = _normalize(action.get("description"))
    tool_description = _normalize(args.get("description"))

    for candidate in (action_description, tool_description):
        if not candidate:
            continue
        subject = _subject_after_for_or_on(candidate)
        if subject:
            return subject

    if tool_description:
        cleaned = re.sub(
            r"\b(advance|payment|paid|expense)\b",
            "",
            tool_description,
            flags=re.IGNORECASE,
        )
        cleaned = _normalize(cleaned)
        if cleaned:
            return cleaned

    return "the repair"


def _known_tool_names(actions: List[Dict[str, Any]]) -> set:
    return {
        str(action.get("tool_name") or "").strip()
        for action in actions
        if str(action.get("tool_name") or "").strip()
    }


def _completed_actions(state: AgentState) -> List[Dict[str, Any]]:
    return [
        dict(action)
        for action in (state.get("planned_actions") or [])
        if isinstance(action, dict)
        and action.get("status") == "completed"
        and action.get("tool_name")
    ]


def _make_suggestion(
    *,
    target_domain: str,
    target_tool: Optional[str],
    permission_tool: str,
    description: str,
    prompt: str,
    known_args: Optional[Dict[str, Any]] = None,
    missing_fields: Optional[List[str]] = None,
    detail_prompt: Optional[str] = None,
    continuation_mode: str = "exact",
    source_tool: str,
    source_description: str,
    context_text: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "target_domain": target_domain,
        "target_tool": target_tool,
        "permission_tool": permission_tool,
        "description": description,
        "prompt": prompt,
        "known_args": dict(known_args or {}),
        "missing_fields": list(missing_fields or []),
        "detail_prompt": detail_prompt,
        "continuation_mode": continuation_mode,
        "source_tool": source_tool,
        "source_description": source_description,
        "context_text": context_text,
    }


def _batch_grocery_suggestion(actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    grocery = [
        action for action in actions
        if action.get("tool_name") == "add_grocery_item"
    ]
    if len(grocery) < 2:
        return None

    names = [
        _normalize((action.get("tool_args") or {}).get("name"))
        for action in grocery
    ]
    names = [name for name in names if name]
    if len(names) < 2:
        return None

    display = ", ".join(names[:6])
    if len(names) > 6:
        display += ", and {0} more".format(len(names) - 6)

    return _make_suggestion(
        target_domain="tasks",
        target_tool="create_task",
        permission_tool="create_task",
        description="Create a reminder to order the grocery batch.",
        prompt=(
            "Would you like a reminder to order these {0} grocery items?"
        ).format(len(names)),
        known_args={
            "title": "Order grocery items: {0}".format(display),
        },
        missing_fields=["due_at"],
        detail_prompt="When should I remind you to order them?",
        continuation_mode="collect_exact",
        source_tool="add_grocery_item",
        source_description="Added multiple grocery items.",
        context_text="Grocery batch: {0}".format(display),
    )


def _rule_for_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool = str(action.get("tool_name") or "")
    args = dict(action.get("tool_args") or {})
    text = _action_text(action)
    source_description = _normalize(action.get("description"))

    if tool == "log_expense":
        category = _lower(args.get("category"))

        if (
            category in {"repair", "maintenance"}
            or _contains_any(text, _REPAIR_WORDS)
        ):
            subject = _repair_subject(action)
            return _make_suggestion(
                target_domain="tasks",
                target_tool="create_task",
                permission_tool="create_task",
                description="Create a follow-up task for {0}.".format(subject),
                prompt=(
                    "Would you like me to add a task to follow up on {0}?"
                ).format(subject),
                known_args={
                    "title": "Follow up on {0}".format(subject),
                },
                continuation_mode="exact",
                source_tool=tool,
                source_description=source_description,
            )

        if (
            category in {"food", "grocery", "groceries"}
            or _contains_any(text, _FOOD_WORDS)
        ):
            item = _extract_food_subject(action)
            if not item:
                return None
            quantity, unit = _extract_quantity(action)
            known_args: Dict[str, Any] = {"name": item}
            missing = []
            if quantity is None:
                missing.append("quantity")
            else:
                known_args["quantity"] = quantity
            if unit:
                known_args["unit"] = unit

            return _make_suggestion(
                target_domain="food",
                target_tool="add_inventory_item",
                permission_tool="add_inventory_item",
                description="Add {0} to household inventory.".format(item),
                prompt=(
                    "Would you like me to add {0} to household inventory?"
                ).format(item),
                known_args=known_args,
                missing_fields=missing,
                detail_prompt=(
                    "What quantity of {0} should I add to inventory?"
                ).format(item) if missing else None,
                continuation_mode="collect_exact" if missing else "exact",
                source_tool=tool,
                source_description=source_description,
            )

    if tool == "add_inventory_item":
        item = _normalize(args.get("name")) or "this purchase"
        quantity = args.get("quantity")
        unit = _normalize(args.get("unit"))
        item_text = item
        if quantity is not None:
            item_text = "{0}{1} {2}".format(
                quantity,
                (" " + unit) if unit else "",
                item,
            )

        amount_minor, currency = _extract_money_from_action(action)
        expense_args: Dict[str, Any] = {
            "category": "Grocery",
            "description": "Purchase of {0}".format(item_text),
        }
        missing = []
        if amount_minor is None:
            missing.extend(["amount_minor", "currency"])
        else:
            expense_args["amount_minor"] = amount_minor
            expense_args["currency"] = currency or "INR"

        return _make_suggestion(
            target_domain="finance",
            target_tool="log_expense",
            permission_tool="log_expense",
            description="Log the purchase expense for {0}.".format(item_text),
            prompt=(
                "Would you like me to log the expense for {0}?"
            ).format(item_text),
            known_args=expense_args,
            missing_fields=missing,
            detail_prompt=(
                "How much did you pay for {0}? Please include the currency."
            ).format(item_text) if missing else None,
            continuation_mode="collect_exact" if missing else "exact",
            source_tool=tool,
            source_description=source_description,
        )

    if tool == "log_repair":
        amount = args.get("cost_minor")
        try:
            has_cost = amount is not None and int(amount) > 0
        except (TypeError, ValueError):
            has_cost = False
        if has_cost:
            description = _normalize(args.get("notes")) or "Household repair"
            expense_args: Dict[str, Any] = {
                "amount_minor": int(amount),
                "currency": _normalize(args.get("currency")) or "USD",
                "category": "Repair",
                "description": description,
            }
            if args.get("serviced_at"):
                expense_args["occurred_at"] = args.get("serviced_at")
            return _make_suggestion(
                target_domain="finance",
                target_tool="log_expense",
                permission_tool="log_expense",
                description="Log the repair cost as an expense.",
                prompt="Would you like me to log this repair cost as an expense?",
                known_args=expense_args,
                continuation_mode="exact",
                source_tool=tool,
                source_description=source_description,
            )

    if tool == "report_issue":
        issue = _normalize(args.get("description")) or "the maintenance issue"
        return _make_suggestion(
            target_domain="tasks",
            target_tool="create_task",
            permission_tool="create_task",
            description="Create a follow-up task for the maintenance issue.",
            prompt="Would you like me to add a follow-up task for this issue?",
            known_args={"title": "Follow up: {0}".format(issue)},
            continuation_mode="exact",
            source_tool=tool,
            source_description=source_description,
        )

    if tool == "create_recurring_bill":
        payee = _normalize(args.get("payee")) or "recurring bill"
        due_at = _normalize(args.get("due_at"))
        if due_at:
            return _make_suggestion(
                target_domain="tasks",
                target_tool="create_task",
                permission_tool="create_task",
                description="Create a reminder for the recurring bill.",
                prompt=(
                    "Would you like a reminder for the {0} bill?"
                ).format(payee),
                known_args={
                    "title": "Pay {0}".format(payee),
                    "due_at": due_at,
                },
                continuation_mode="exact",
                source_tool=tool,
                source_description=source_description,
            )

    if tool == "create_task":
        title = _normalize(args.get("title"))
        title_lower = title.casefold()

        if title_lower.startswith(("buy ", "order ")):
            item = re.sub(
                r"^(?:buy|order)\s+",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()
            if item:
                return _make_suggestion(
                    target_domain="food",
                    target_tool="add_grocery_item",
                    permission_tool="add_grocery_item",
                    description="Add {0} to the grocery list.".format(item),
                    prompt=(
                        "Would you like me to add {0} to the grocery list?"
                    ).format(item),
                    known_args={"name": item},
                    missing_fields=["quantity"],
                    detail_prompt=(
                        "What quantity of {0} should I add to the grocery list?"
                    ).format(item),
                    continuation_mode="collect_exact",
                    source_tool=tool,
                    source_description=source_description,
                )

        if title and _contains_any(title, _REPAIR_WORDS):
            return _make_suggestion(
                target_domain="maintenance",
                target_tool="report_issue",
                permission_tool="report_issue",
                description="Record the task as a maintenance issue.",
                prompt=(
                    "Would you like me to record this as a maintenance issue too?"
                ),
                known_args={
                    "description": title,
                    "priority": _normalize(args.get("priority")) or "Normal",
                },
                continuation_mode="exact",
                source_tool=tool,
                source_description=source_description,
            )

    if tool == "add_appliance":
        name = _normalize(args.get("name")) or "the appliance"
        warranty_end = _normalize(args.get("warranty_ends_at"))
        if warranty_end:
            return _make_suggestion(
                target_domain="tasks",
                target_tool="create_task",
                permission_tool="create_task",
                description="Create a warranty-expiry reminder for {0}.".format(name),
                prompt=(
                    "Would you like a reminder before the warranty for {0} expires?"
                ).format(name),
                known_args={
                    "title": "Warranty expiry: {0}".format(name),
                    "due_at": warranty_end,
                },
                continuation_mode="exact",
                source_tool=tool,
                source_description=source_description,
            )

    if tool == "create_calendar_event":
        title = _normalize(args.get("title"))
        if title and _contains_any(title, _EVENT_GROCERY_WORDS):
            when = _normalize(args.get("starts_at"))
            context = "Event: {0}".format(title)
            if when:
                context += "; starts at {0}".format(when)
            return _make_suggestion(
                target_domain="food",
                target_tool=None,
                permission_tool="add_grocery_item",
                description="Add grocery items for {0}.".format(title),
                prompt=(
                    "Would you like me to add grocery items for {0}?"
                ).format(title),
                known_args={},
                missing_fields=["items"],
                detail_prompt=(
                    "Which items should I add to the grocery list for {0}?"
                ).format(title),
                continuation_mode="replan",
                source_tool=tool,
                source_description=source_description,
                context_text=context,
            )

    return None


def build_cross_domain_suggestion(state: AgentState) -> Optional[Dict[str, Any]]:
    """Return at most one useful, RBAC-allowed suggestion for this turn."""

    actions = _completed_actions(state)
    if not actions:
        return None

    if any(
        str(action.get("origin") or "") == "cross_domain_suggestion"
        for action in actions
    ):
        # Exact accepted suggestions do not immediately generate a reverse
        # suggestion. Open-ended continuations may still produce a new useful
        # event (for example dinner groceries -> one ordering reminder).
        return None

    explicit_tools = _known_tool_names(actions)

    candidates: List[Dict[str, Any]] = []
    batch = _batch_grocery_suggestion(actions)
    if batch is not None:
        candidates.append(batch)

    for action in actions:
        suggestion = _rule_for_action(action)
        if suggestion is not None:
            candidates.append(suggestion)

    role = str(state.get("role") or "")
    for suggestion in candidates:
        permission_tool = str(suggestion.get("permission_tool") or "")
        target_domain = str(suggestion.get("target_domain") or "")

        # Do not suggest an operation the user already explicitly requested.
        target_tool = str(suggestion.get("target_tool") or "")
        capability_tool = target_tool or permission_tool
        if capability_tool and capability_tool in explicit_tools:
            continue

        # RBAC applies before disclosure.  An unauthorized user is not offered
        # a follow-up action they cannot execute.
        if not is_authorized(role, target_domain, permission_tool):
            continue

        return suggestion

    return None


def _synthetic_ai_message(tool_name: str, args: Dict[str, Any]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": tool_name,
                "args": dict(args),
                "id": "suggestion_{0}".format(uuid4().hex),
            }
        ],
    )


def cross_domain_suggestion_node(state: AgentState) -> Dict[str, Any]:
    suggestion = build_cross_domain_suggestion(state)
    if suggestion is None:
        return {
            "active_suggestion": None,
            "awaiting_confirmation": False,
        }

    try:
        proposal_id = persist_suggestion_offer(state, suggestion)
    except SuggestionWorkflowError:
        # Suggestions must never break an otherwise successful user request.
        return {
            "active_suggestion": None,
            "awaiting_confirmation": False,
        }

    response = str(state.get("response") or "").rstrip()
    prompt = str(suggestion.get("prompt") or "").strip()
    if prompt:
        response = (response + "\n\n" + prompt + "\nReply yes or no.").strip()

    return {
        "active_suggestion": suggestion,
        "workflow_proposal_id": proposal_id,
        "confirmation_kind": "suggestion",
        "awaiting_confirmation": True,
        "finished": True,
        "response": response,
    }


def suggestion_authorize_node(state: AgentState) -> Dict[str, Any]:
    result = authorize_node(state)
    if not result.get("authorized"):
        reject_suggestion_for_authorization(state)
    return result


def suggestion_approve_node(state: AgentState) -> Dict[str, Any]:
    try:
        approve_exact_suggestion(state)
    except SuggestionWorkflowError as exc:
        return {
            "authorized": False,
            "auth_error": str(exc),
            "finished": False,
        }

    return {
        "editing_workflow_proposal_id": None,
        "awaiting_confirmation": False,
        "finished": False,
    }


def route_after_suggestion_authorize(state: AgentState) -> str:
    if state.get("authorized"):
        return "duplicate_check"
    return "next_action"


def route_after_suggestion_approve(state: AgentState) -> str:
    if state.get("auth_error"):
        return "next_action"
    return "execute"
