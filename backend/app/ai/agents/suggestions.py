"""Deterministic cross-domain follow-up suggestions.

The model is not allowed to invent follow-up actions here.  Suggestions are
created from completed tool calls in the current request, filtered through
RBAC before they are shown, persisted durably, and executed only after user
approval and a fresh authorization check.

Refactor notes
--------------
* Keyword detection uses whole-word matching (with simple plurals).  The old
  substring matching let "ac" match "back" and "oil" match "toilet".
* Rules are small per-tool functions registered in ``_RULES`` instead of one
  long if-chain, so each rule can be tested and extended in isolation.
* Calendar events that look like hosting (dinner, party, guests ...) offer a
  grocery follow-up, now carrying the guest count and end time into the
  replan context.  Eating-out events ("dinner at a restaurant") do not.

Public API is unchanged: ``build_cross_domain_suggestion``,
``cross_domain_suggestion_node``, ``suggestion_authorize_node``,
``suggestion_approve_node``, ``route_after_suggestion_authorize``,
and ``route_after_suggestion_approve``.

Compatibility target: Python 3.8+.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Tuple

from app.ai.agents.authorize import authorize_node
from app.ai.agents.permissions import is_authorized
from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.maintenance import MaintenanceIssue
from app.services.suggestion_workflow import (
    SuggestionWorkflowError,
    approve_exact_suggestion,
    persist_suggestion_offer,
    reject_suggestion_for_authorization,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CURRENCY = "INR"
MAX_PLAUSIBLE_GUESTS = 500

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
    "dinner", "lunch", "breakfast", "brunch", "party", "parties",
    "birthday", "anniversary", "celebration", "housewarming", "gathering",
    "potluck", "barbecue", "bbq", "cookout", "guests", "guest",
    "get-together", "get together", "meal",
}
# Events that are about eating somewhere else do not need a grocery run.
_EATING_OUT_WORDS = {
    "restaurant", "eat out", "eating out", "dine out", "dining out",
    "takeout", "take-out", "takeaway", "take away", "order in",
    "swiggy", "zomato", "cafe", "café",
}

_GENERIC_ITEM_WORDS = {"groceries", "grocery", "stuff", "things", "supplies"}

# Purchases that must never be inferred as food/grocery inventory merely
# because the user used "buy", "bought", "order", or a broad expense category.
_NON_GROCERY_PURCHASE_WORDS = {
    "medicine", "medicines", "medication", "medications",
    "tablet", "tablets", "pill", "pills",
    "prescription", "prescriptions", "pharmacy", "chemist",
}

_TEMPORAL_ITEM_SUFFIX_RE = re.compile(
    r"\s+(?:today|yesterday|tomorrow|tonight|"
    r"this\s+(?:morning|afternoon|evening))\s*$",
    re.IGNORECASE,
)

_PURCHASE_SUBJECT_RE = re.compile(
    r"\b(?:bought|purchased|buy|ordered|order)\s+(.+?)"
    r"(?:\s+(?:today|yesterday|tomorrow|tonight|"
    r"this\s+(?:morning|afternoon|evening)))?"
    r"(?:[.,]|$)",
    re.IGNORECASE,
)

_QUANTITY_UNITS = (
    r"kg|kgs|g|gm|gms|grams?|litres?|liters?|l|ml|packs?|boxes?|cartons?|"
    r"pieces?|pcs?|count"
)
_QUANTITY_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(" + _QUANTITY_UNITS + r")?\b",
    re.IGNORECASE,
)
_LEADING_QUANTITY_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(" + _QUANTITY_UNITS + r")\b",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Guest-count patterns, most specific first.  The "for/of N" patterns refuse
# to match times, dates and durations such as "for 8 pm" or "lunch for 3 days".
_NOT_TIME_OR_DATE = (
    r"(?!\s*(?:am|pm|a\.m|p\.m|:|%|hours?|hrs?|mins?|minutes?|days?|nights?|"
    r"weeks?|(?:st|nd|rd|th)\b|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)))"
)
_GUEST_COUNT_PATTERNS = (
    re.compile(
        r"\b(\d{1,3})\s*(?:guests?|people|persons?|pax|friends|folks|adults|"
        r"kids|children|members|relatives)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:party|group|table|dinner|lunch|gathering)\s+(?:of|for)\s+"
        r"(\d{1,3})\b" + _NOT_TIME_OR_DATE,
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:for|with)\s+(\d{1,3})\b" + _NOT_TIME_OR_DATE,
        re.IGNORECASE,
    ),
)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _lower(value: Any) -> str:
    return _normalize(value).casefold()


def _compile_words(words: Iterable[str]) -> Pattern:
    """Whole-word, plural-tolerant, case-insensitive pattern for ``words``."""

    alternatives = []
    cleaned = {
        str(word).strip().casefold()
        for word in words
        if str(word).strip()
    }
    for word in sorted(cleaned, key=lambda item: (-len(item), item)):
        alternatives.append(
            r"\s+".join(re.escape(part) for part in word.split())
        )
    return re.compile(
        r"(?<!\w)(?:%s)(?:s|es)?(?!\w)" % "|".join(alternatives),
        re.IGNORECASE,
    )


_PATTERN_CACHE: Dict[frozenset, Pattern] = {}


def _contains_any(text: str, words) -> bool:
    """True when any of ``words`` appears as a whole word/phrase in ``text``."""

    if not text:
        return False
    key = frozenset(words)
    if not key:
        return False
    pattern = _PATTERN_CACHE.get(key)
    if pattern is None:
        pattern = _compile_words(key)
        _PATTERN_CACHE[key] = pattern
    return pattern.search(text) is not None


def _action_text(action: Dict[str, Any]) -> str:
    args = action.get("tool_args") or {}
    return " ".join(
        part
        for part in (
            _normalize(action.get("description")),
            _normalize(action.get("intent")),
            _normalize(args.get("description")),
            _normalize(args.get("category")),
        )
        if part
    )


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


def _clean_food_item_candidate(value: Any) -> Optional[str]:
    """Return a concrete grocery/food subject or None.

    This deliberately rejects generic category words and known non-grocery
    purchases such as medicine. Temporal wording is stripped so a phrase like
    "grocery today" cannot become an inventory item.
    """

    subject = _normalize(value)
    if not subject:
        return None

    subject = re.sub(
        r"^(?:the\s+)?(?:purchase\s+of\s+)?",
        "",
        subject,
        flags=re.IGNORECASE,
    )

    subject = re.sub(
        r"^(?:rs\.?|₹|inr)\s*\d+(?:\.\d+)?\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    )

    quantity = _LEADING_QUANTITY_RE.match(subject)
    if quantity:
        subject = subject[quantity.end():].strip()

    subject = _TEMPORAL_ITEM_SUFFIX_RE.sub(
        "",
        subject,
    ).strip(" .,")

    if not subject:
        return None

    lowered = subject.casefold()

    if lowered in _GENERIC_ITEM_WORDS:
        return None

    if _contains_any(
        subject,
        _NON_GROCERY_PURCHASE_WORDS,
    ):
        return None

    return subject


def _extract_food_subject(action: Dict[str, Any]) -> Optional[str]:
    args = dict(action.get("tool_args") or {})
    description = _normalize(args.get("description"))
    action_description = _normalize(action.get("description"))

    # Prefer the semantic tool description. Finance normalization now stores
    # the expense subject here when it is known (e.g. "rice", "apples").
    if description:
        subject = _subject_after_for_or_on(description)
        cleaned = _clean_food_item_candidate(
            subject if subject else description
        )
        if cleaned:
            return cleaned

    if action_description:
        subject = _subject_after_for_or_on(
            action_description
        )
        cleaned = _clean_food_item_candidate(
            subject
        )
        if cleaned:
            return cleaned

        # Also support natural purchase phrasing such as "bought rice today".
        purchase_match = _PURCHASE_SUBJECT_RE.search(
            action_description
        )
        if purchase_match:
            cleaned = _clean_food_item_candidate(
                purchase_match.group(1)
            )
            if cleaned:
                return cleaned

    # Do not use Finance category as an item name. A category such as
    # "Grocery" says what kind of expense this was, not what was purchased.
    return None


def _extract_quantity(
    action: Dict[str, Any],
) -> Tuple[Optional[float], Optional[str]]:
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
    return int(round(major * 100)), DEFAULT_CURRENCY


def _extract_guest_count(text: str) -> Optional[int]:
    """Best-effort guest count from free text such as "party for 12"."""

    if not text:
        return None
    for pattern in _GUEST_COUNT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                count = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if 1 <= count <= MAX_PLAUSIBLE_GUESTS:
                return count
    return None


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


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

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
    chain_context: Optional[Dict[str, Any]] = None,
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
        "chain_context": (
            dict(chain_context)
            if isinstance(chain_context, dict)
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Batch rule (spans several actions)
# ---------------------------------------------------------------------------

def _batch_grocery_suggestion(
    actions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
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


def _active_maintenance_issues(
    appliance_id: str,
) -> List[Dict[str, Any]]:
    """Return active Open/InProgress issues for one appliance."""

    appliance_id = _normalize(appliance_id)
    if not appliance_id:
        return []

    session = SessionLocal()

    try:
        rows = (
            session.query(MaintenanceIssue)
            .filter(
                MaintenanceIssue.appliance_id
                == appliance_id
            )
            .all()
        )

        active = []

        for issue in rows:
            status = _normalize(
                getattr(
                    getattr(issue, "status", None),
                    "value",
                    getattr(issue, "status", None),
                )
            ).casefold()

            if status not in {
                "open",
                "inprogress",
                "in_progress",
                "in progress",
            }:
                continue

            active.append(
                {
                    "issue_id": str(
                        issue.issue_id
                    ),
                    "description": _normalize(
                        issue.description
                    ),
                    "status": _normalize(
                        getattr(
                            getattr(issue, "status", None),
                            "value",
                            getattr(issue, "status", None),
                        )
                    ),
                }
            )

        return active

    finally:
        session.close()


def _repair_expense_followup(
    action: Dict[str, Any],
    args: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return trusted Finance follow-up details for one repair.

    Repairs originating from an accepted Finance -> Maintenance continuation
    already have their expense recorded and must not create the reverse
    suggestion again.
    """

    if (
        str(action.get("origin") or "").strip()
        == "cross_domain_suggestion_continuation"
    ):
        return None

    known_args: Dict[str, Any] = {
        "category": "Repair",
        "description": (
            _normalize(args.get("notes"))
            or "Household repair"
        ),
    }

    if args.get("serviced_at"):
        known_args["occurred_at"] = (
            args.get("serviced_at")
        )

    amount = args.get("cost_minor")
    try:
        has_cost = (
            amount is not None
            and int(amount) > 0
        )
    except (TypeError, ValueError):
        has_cost = False

    if has_cost:
        known_args["amount_minor"] = int(amount)
        known_args["currency"] = (
            _normalize(args.get("currency"))
            or DEFAULT_CURRENCY
        )
        missing_fields: List[str] = []
        detail_prompt = None
        continuation_mode = "exact"
    else:
        # Do not trust the repair tool's default currency when the user did
        # not supply a repair cost. Ask for both amount and currency.
        missing_fields = [
            "amount_minor",
            "currency",
        ]
        detail_prompt = (
            "How much did the repair cost? "
            "Please include the currency."
        )
        continuation_mode = "collect_exact"

    return {
        "known_args": known_args,
        "missing_fields": missing_fields,
        "detail_prompt": detail_prompt,
        "continuation_mode": continuation_mode,
    }


def _repair_issue_close_suggestion(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    """Offer to close active issues after a repair for the same appliance."""

    appliance_id = _normalize(
        args.get("appliance_id")
    )

    if not appliance_id:
        return None

    issues = _active_maintenance_issues(
        appliance_id
    )

    if not issues:
        return None

    if len(issues) == 1:
        issue = issues[0]
        description = (
            issue.get("description")
            or "the active maintenance issue"
        )

        expense_followup = (
            _repair_expense_followup(
                action,
                args,
            )
        )

        chain_context = None
        if expense_followup is not None:
            chain_context = {
                "kind": "repair_issue_close",
                "deferred_expense": (
                    expense_followup
                ),
            }

        return _make_suggestion(
            target_domain="maintenance",
            target_tool="update_issue",
            permission_tool="update_issue",
            description=(
                "Close the resolved maintenance issue: {0}."
            ).format(description),
            prompt=(
                "There is still an active maintenance issue for this "
                "appliance: {0}. Would you like me to close it?"
            ).format(description),
            known_args={
                "issue_id": issue["issue_id"],
                "status": "Closed",
            },
            missing_fields=[],
            continuation_mode="exact",
            source_tool="log_repair",
            source_description=source_description,
            context_text=(
                "The repair was completed for appliance_id {0}. "
                "The active issue '{1}' belongs to the same appliance."
            ).format(
                appliance_id,
                description,
            ),
            chain_context=chain_context,
        )

    issue_descriptions = [
        issue.get("description")
        or "maintenance issue"
        for issue in issues
    ]

    display = "; ".join(
        issue_descriptions[:4]
    )

    if len(issue_descriptions) > 4:
        display += "; and {0} more".format(
            len(issue_descriptions) - 4
        )

    # Multiple issue closures are replanned only after explicit approval.
    # Stable IDs stay in trusted continuation context and are not exposed
    # in the user-facing prompt.
    context_lines = [
        (
            "The repair was completed for appliance_id {0}. "
            "The following active maintenance issues belong to that "
            "same appliance and the user approved closing them:"
        ).format(appliance_id)
    ]

    for issue in issues:
        context_lines.append(
            "- issue_id={0}; description={1}; status={2}".format(
                issue["issue_id"],
                issue.get("description") or "",
                issue.get("status") or "",
            )
        )

    context_lines.append(
        "Plan one update_issue action per listed issue, setting status "
        "to Closed. Do not modify unrelated issues."
    )

    return _make_suggestion(
        target_domain="maintenance",
        target_tool=None,
        permission_tool="update_issue",
        description=(
            "Close the active maintenance issues for the repaired appliance."
        ),
        prompt=(
            "There are {0} active maintenance issues for this appliance: "
            "{1}. Would you like me to close them?"
        ).format(
            len(issues),
            display,
        ),
        known_args={},
        missing_fields=[],
        continuation_mode="replan",
        source_tool="log_repair",
        source_description=source_description,
        context_text="\n".join(
            context_lines
        ),
    )


# ---------------------------------------------------------------------------
# Per-tool rules
#
# Each rule receives (action, args, source_description) and returns a
# suggestion dict or None.  Register new rules in _RULES at the bottom.
# ---------------------------------------------------------------------------

RuleFn = Callable[[Dict[str, Any], Dict[str, Any], str], Optional[Dict[str, Any]]]


def _rule_log_expense(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    tool = "log_expense"
    text = _action_text(action)
    category = _lower(args.get("category"))

    if category in {"repair", "maintenance"} or _contains_any(text, _REPAIR_WORDS):
        subject = _repair_subject(action)

        amount_minor = args.get("amount_minor")
        amount_text = ""
        try:
            amount_value = int(amount_minor)
            if amount_value > 0:
                amount_text = "{0:.2f}".format(amount_value / 100.0)
        except (TypeError, ValueError):
            amount_text = ""

        currency = _normalize(args.get("currency")) or DEFAULT_CURRENCY
        occurred_at = _normalize(args.get("occurred_at"))
        expense_description = (
            _normalize(args.get("description"))
            or source_description
            or subject
        )

        context_parts = [
            "The user already logged the finance expense for this repair.",
            "Repair subject/reference: {0}.".format(subject),
            "Expense description: {0}.".format(expense_description),
        ]
        if amount_text:
            context_parts.append(
                "Repair cost already logged in finance: {0} {1}.".format(
                    amount_text,
                    currency,
                )
            )
        if occurred_at:
            context_parts.append(
                "Repair/expense date: {0}.".format(occurred_at)
            )
        context_parts.append(
            "The user accepted recording the same repair in Maintenance. "
            "Plan a maintenance repair action only; do not log another finance "
            "expense. Resolve the appliance through the normal maintenance "
            "clarification flow when needed."
        )

        return _make_suggestion(
            target_domain="maintenance",
            target_tool=None,
            permission_tool="log_repair",
            description="Record the repair for {0} in Maintenance.".format(
                subject
            ),
            prompt=(
                "Would you like me to also record this repair in Maintenance?"
            ),
            known_args={},
            missing_fields=[],
            continuation_mode="replan",
            source_tool=tool,
            source_description=source_description,
            context_text=" ".join(context_parts),
        )

    # A broad Finance category is not enough to infer food inventory.
    # Explicit non-grocery purchases (e.g. medicine) always suppress this route.
    if _contains_any(
        text,
        _NON_GROCERY_PURCHASE_WORDS,
    ):
        return None

    if category in {"food", "grocery", "groceries"} or _contains_any(text, _FOOD_WORDS):
        item = _extract_food_subject(action)
        if not item:
            return None
        # A purchased description can contain several grocery items.
        # One add_inventory_item call cannot safely represent different
        # quantities/units for each item, so replan the accepted follow-up.
        is_multi_item = bool(
            re.search(
                r"(?:[,;]|\band\b|&)",
                item,
                flags=re.IGNORECASE,
            )
        )

        if is_multi_item:
            return _make_suggestion(
                target_domain="food",
                target_tool=None,
                permission_tool="add_inventory_item",
                description=(
                    "Add purchased grocery items to household inventory."
                ),
                prompt=(
                    "Would you like me to add {0} "
                    "to household inventory?"
                ).format(item),
                known_args={},
                missing_fields=["items"],
                detail_prompt=(
                    "Please give the quantity and unit for each item "
                    "you want added to inventory."
                ),
                continuation_mode="replan",
                source_tool=tool,
                source_description=source_description,
                context_text=(
                    "The user accepted adding these purchased grocery "
                    "items to household inventory: {0}. "
                    "Create separate inventory actions for each item, "
                    "preserving each item's quantity and unit."
                ).format(item),
            )
        
        quantity, unit = _extract_quantity(action)
        known_args: Dict[str, Any] = {"name": item}
        missing: List[str] = []
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

    return None


def _rule_add_inventory_item(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
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
    missing: List[str] = []
    if amount_minor is None:
        missing.extend(["amount_minor", "currency"])
    else:
        expense_args["amount_minor"] = amount_minor
        expense_args["currency"] = currency or DEFAULT_CURRENCY

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
        source_tool="add_inventory_item",
        source_description=source_description,
    )


def _rule_log_repair(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    # Closing active issues for the repaired appliance is the most directly
    # related follow-up, so it takes precedence over the Finance suggestion.
    issue_suggestion = _repair_issue_close_suggestion(
        action,
        args,
        source_description,
    )
    if issue_suggestion is not None:
        return issue_suggestion

    expense_followup = _repair_expense_followup(
        action,
        args,
    )
    if expense_followup is None:
        return None

    return _make_suggestion(
        target_domain="finance",
        target_tool="log_expense",
        permission_tool="log_expense",
        description="Log the repair cost as an expense.",
        prompt=(
            "Would you like me to log this repair as an expense?"
        ),
        known_args=expense_followup["known_args"],
        missing_fields=expense_followup[
            "missing_fields"
        ],
        detail_prompt=expense_followup[
            "detail_prompt"
        ],
        continuation_mode=expense_followup[
            "continuation_mode"
        ],
        source_tool="log_repair",
        source_description=source_description,
    )


def _rule_report_issue(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    issue = _normalize(args.get("description")) or "the maintenance issue"
    return _make_suggestion(
        target_domain="tasks",
        target_tool="create_task",
        permission_tool="create_task",
        description="Create a follow-up task for the maintenance issue.",
        prompt="Would you like me to add a follow-up task for this issue?",
        known_args={"title": "Follow up: {0}".format(issue)},
        missing_fields=["due_at"],
        detail_prompt="When should I schedule the follow-up task?",
        continuation_mode="collect_exact",
        source_tool="report_issue",
        source_description=source_description,
    )


def _rule_create_recurring_bill(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    payee = _normalize(args.get("payee")) or "recurring bill"
    due_at = _normalize(args.get("due_at"))
    if not due_at:
        return None
    return _make_suggestion(
        target_domain="tasks",
        target_tool="create_task",
        permission_tool="create_task",
        description="Create a reminder for the recurring bill.",
        prompt="Would you like a reminder for the {0} bill?".format(payee),
        known_args={"title": "Pay {0}".format(payee), "due_at": due_at},
        continuation_mode="exact",
        source_tool="create_recurring_bill",
        source_description=source_description,
    )


def _rule_create_task(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    tool = "create_task"
    title = _normalize(args.get("title"))
    if not title:
        return None

    if title.casefold().startswith(("buy ", "order ")):
        item = re.sub(
            r"^(?:buy|order)\s+",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        # Buying medicine/medication is a valid task, but it is not grocery
        # intent and must not create a food-domain follow-up.
        if _contains_any(
            item,
            _NON_GROCERY_PURCHASE_WORDS,
        ):
            return None

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

    if _contains_any(title, _REPAIR_WORDS):
        return _make_suggestion(
            target_domain="maintenance",
            target_tool="report_issue",
            permission_tool="report_issue",
            description="Record the task as a maintenance issue.",
            prompt="Would you like me to record this as a maintenance issue too?",
            known_args={
                "description": title,
                "priority": _normalize(args.get("priority")) or "Normal",
            },
            continuation_mode="exact",
            source_tool=tool,
            source_description=source_description,
        )

    return None


def _rule_add_appliance(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    name = _normalize(args.get("name")) or "the appliance"
    warranty_end = _normalize(args.get("warranty_ends_at"))
    if not warranty_end:
        return None
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
        source_tool="add_appliance",
        source_description=source_description,
    )


def _rule_create_calendar_event(
    action: Dict[str, Any],
    args: Dict[str, Any],
    source_description: str,
) -> Optional[Dict[str, Any]]:
    """Hosting-style events (dinner, party, guests ...) -> grocery follow-up."""

    title = _normalize(args.get("title"))
    if not title:
        return None

    details = " ".join(
        part
        for part in (
            title,
            _normalize(args.get("description")),
            source_description,
        )
        if part
    )

    if not _contains_any(details, _EVENT_GROCERY_WORDS):
        return None

    # "Dinner at a restaurant" needs no groceries.
    if _contains_any(details, _EATING_OUT_WORDS):
        return None

    guests = _extract_guest_count(details)
    label = (
        "{0} ({1} guests)".format(title, guests) if guests else title
    )

    context = "Event: {0}".format(title)
    starts_at = _normalize(args.get("starts_at"))
    ends_at = _normalize(args.get("ends_at"))
    if starts_at:
        context += "; starts at {0}".format(starts_at)
    if ends_at:
        context += "; ends at {0}".format(ends_at)
    if guests:
        context += "; about {0} guests".format(guests)

    return _make_suggestion(
        target_domain="food",
        target_tool=None,
        permission_tool="add_grocery_item",
        description="Add grocery items for {0}.".format(title),
        prompt=(
            "Would you like me to add grocery items for {0}?"
        ).format(label),
        known_args={},
        missing_fields=["items"],
        detail_prompt=(
            "Which items should I add to the grocery list for {0}?"
        ).format(label),
        continuation_mode="replan",
        source_tool="create_calendar_event",
        source_description=source_description,
        context_text=context,
    )


_RULES: Dict[str, RuleFn] = {
    "log_expense": _rule_log_expense,
    "add_inventory_item": _rule_add_inventory_item,
    "log_repair": _rule_log_repair,
    "report_issue": _rule_report_issue,
    "create_recurring_bill": _rule_create_recurring_bill,
    "create_task": _rule_create_task,
    "add_appliance": _rule_add_appliance,
    "create_calendar_event": _rule_create_calendar_event,
}


def _rule_for_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool = str(action.get("tool_name") or "")
    rule = _RULES.get(tool)
    if rule is None:
        return None
    args = dict(action.get("tool_args") or {})
    source_description = _normalize(action.get("description"))
    return rule(action, args, source_description)


def _deferred_repair_expense_suggestion(
    actions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Offer the saved repair expense only after issue/task closure completes."""

    for action in reversed(actions):
        chain_context = action.get(
            "suggestion_chain_context"
        )

        if not isinstance(
            chain_context,
            dict,
        ):
            continue

        if (
            str(
                chain_context.get("kind")
                or ""
            ).strip()
            != "repair_issue_close"
        ):
            continue

        deferred = chain_context.get(
            "deferred_expense"
        )

        if not isinstance(
            deferred,
            dict,
        ):
            return None

        # If a linked follow-up task was found, actions.py carries the same
        # chain context onto complete_task and we wait for that cascade.
        linked_task_id = str(
            chain_context.get(
                "linked_followup_task_id"
            )
            or ""
        ).strip()

        tool_name = str(
            action.get("tool_name")
            or ""
        ).strip()

        if linked_task_id:
            if tool_name != "complete_task":
                continue
        elif tool_name != "update_issue":
            continue

        known_args = dict(
            deferred.get("known_args")
            or {}
        )
        missing_fields = list(
            deferred.get("missing_fields")
            or []
        )

        prompt = (
            "The maintenance issue and its follow-up task are closed. "
            "Would you like me to log the repair as an expense?"
            if linked_task_id
            else (
                "The maintenance issue is closed. "
                "Would you like me to log the repair as an expense?"
            )
        )

        return _make_suggestion(
            target_domain="finance",
            target_tool="log_expense",
            permission_tool="log_expense",
            description=(
                "Log the repair cost as an expense."
            ),
            prompt=prompt,
            known_args=known_args,
            missing_fields=missing_fields,
            detail_prompt=deferred.get(
                "detail_prompt"
            ),
            continuation_mode=str(
                deferred.get(
                    "continuation_mode"
                )
                or (
                    "collect_exact"
                    if missing_fields
                    else "exact"
                )
            ),
            source_tool=tool_name,
            source_description=str(
                action.get("description")
                or ""
            ),
        )

    return None


# ---------------------------------------------------------------------------
# Suggestion selection
# ---------------------------------------------------------------------------

def build_cross_domain_suggestion(
    state: AgentState,
) -> Optional[Dict[str, Any]]:
    """Return at most one useful, RBAC-allowed suggestion for this turn."""

    actions = _completed_actions(state)
    if not actions:
        return None

    deferred_expense = (
        _deferred_repair_expense_suggestion(
            actions
        )
    )

    if deferred_expense is None and any(
        str(action.get("origin") or "")
        == "cross_domain_suggestion"
        for action in actions
    ):
        # Exact accepted suggestions normally do not generate another
        # suggestion. The repair -> close issue -> close task -> expense
        # sequence above is the one explicit deterministic exception.
        return None

    explicit_tools = _known_tool_names(actions)

    candidates: List[Dict[str, Any]] = []

    if deferred_expense is not None:
        candidates.append(
            deferred_expense
        )
    if deferred_expense is None:
        batch = _batch_grocery_suggestion(
            actions
        )
        if batch is not None:
            candidates.append(batch)

        for action in actions:
            suggestion = _rule_for_action(
                action
            )
            if suggestion is not None:
                candidates.append(
                    suggestion
                )

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


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def cross_domain_suggestion_node(state: AgentState) -> Dict[str, Any]:
    suggestion = build_cross_domain_suggestion(state)
    if suggestion is None:
        return {
            "active_suggestion": None,
            "awaiting_confirmation": False,
        }

    try:
        proposal_id = persist_suggestion_offer(state, suggestion)
    except SuggestionWorkflowError as exc:
        # Suggestions must never break an otherwise successful user request,
        # but log why one was dropped (e.g. another review is still open).
        logger.info("cross-domain suggestion not offered: %s", exc)
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