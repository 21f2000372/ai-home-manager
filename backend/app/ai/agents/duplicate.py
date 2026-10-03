from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Tuple, Optional

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.inventory import GroceryItem, InventoryItem
from datetime import datetime, timezone
from app.ai.agents.permissions import is_authorized

from app.services.consistency import (
    BLOCKED,
    CLEAR,
    EXACT_DUPLICATE,
    POSSIBLE_DUPLICATE,
    check_consistency as check_shared_consistency,
)
DuplicateCheckResult = Tuple[
    str,
    Optional[str],
    Optional[Dict[str, Any]],
]


def _normalize(value: Optional[str]) -> str:
    return " ".join(
        (value or "").casefold().strip().split()
    )


def _number(value: Any) -> Optional[Decimal]:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None
    
def _parse_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    
    # Handle the 'Z' UTC suffix that earlier Python versions struggle with
    cleaned = dt_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        # Ensure it is timezone-aware. If naive, assume UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

def _check_grocery(
    args: Dict[str, Any],
) -> DuplicateCheckResult:
    requested_name = _normalize(
        args.get("name")
    )

    if not requested_name:
        return "NEW", None, None

    session = SessionLocal()

    try:
        rows = (
            session.query(GroceryItem)
            .filter(
                GroceryItem.purchased.is_(False)
            )
            .all()
        )

        matches = [
            row
            for row in rows
            if _normalize(row.name) == requested_name
        ]

        if not matches:
            return "NEW", None, None

        existing = matches[0]

        requested_quantity = _number(
            args.get("quantity", 1)
        )
        existing_quantity = _number(
            existing.quantity
        )

        requested_unit = _normalize(
            args.get("unit")
        )
        existing_unit = _normalize(
            existing.unit
        )

        exact_match = (
            requested_quantity == existing_quantity
            and requested_unit == existing_unit
        )

        existing_quantity_text = (
            "{0}{1}".format(
                existing.quantity,
                (" " + existing.unit) if existing.unit else "",
            )
        )

        requested_quantity_text = (
            "{0}{1}".format(
                args.get("quantity", 1),
                (" " + str(args.get("unit"))) if args.get("unit") else "",
            )
        )

        match = {
            "domain": "food",
            "record_type": "grocery_item",
            "record_id": str(existing.grocery_item_id),
            "record_id_arg": "grocery_item_id",
            "update_tool": "update_grocery_item",
            "name": existing.name,
            "quantity": (
                float(existing.quantity)
                if existing.quantity is not None
                else None
            ),
            "unit": existing.unit,
        }

        if exact_match:
            return (
                "DUPLICATE",
                (
                    "'{0}' is already on the active grocery list with "
                    "quantity {1}."
                ).format(
                    existing.name,
                    existing_quantity_text,
                ),
                match,
            )

        return (
            "CONFLICT",
            (
                "'{0}' is already on the active grocery list as {1}, "
                "while the revised request is {2} {3}."
            ).format(
                existing.name,
                existing_quantity_text,
                requested_quantity_text,
                args.get("name"),
            ),
            match,
        )

    finally:
        session.close()


def _check_inventory(
    args: Dict[str, Any],
) -> DuplicateCheckResult:
    requested_name = _normalize(
        args.get("name")
    )

    if not requested_name:
        return "NEW", None, None

    session = SessionLocal()

    try:
        rows = session.query(
            InventoryItem
        ).all()

        matches = [
            row
            for row in rows
            if _normalize(row.name) == requested_name
        ]

        if not matches:
            return "NEW", None, None

        existing = matches[0]

        requested_quantity = _number(
            args.get("quantity", 1)
        )
        existing_quantity = _number(
            existing.quantity
        )

        requested_unit = _normalize(
            args.get("unit")
        )
        existing_unit = _normalize(
            existing.unit
        )

        exact_match = (
            requested_quantity == existing_quantity
            and requested_unit == existing_unit
        )

        status = (
            "DUPLICATE"
            if exact_match
            else "CONFLICT"
        )

        details = (
            "'{0}' already exists in inventory with quantity {1}{2}."
        ).format(
            existing.name,
            existing.quantity,
            (" " + existing.unit) if existing.unit else "",
        )

        match = {
            "domain": "food",
            "record_type": "inventory_item",
            "record_id": str(existing.item_id),
            "record_id_arg": "item_id",
            "update_tool": "update_inventory_item",
            "name": existing.name,
            "quantity": (
                float(existing.quantity)
                if existing.quantity is not None
                else None
            ),
            "unit": existing.unit,
        }

        return status, details, match

    finally:
        session.close()

from typing import Any, Dict, List, Tuple
# (Keep your existing imports)

def _check_expense_overlap(args: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    amount = args.get("amount_minor")
    occurred_at = str(args.get("occurred_at") or "").strip()[:10]
    results = []

    if amount is None or not occurred_at:
        return "CLEAR", results

    session = SessionLocal()
    try:
        from app.models.finance import Expense
        expenses = session.query(Expense).all()

        for expense in expenses:
            existing_date = str(expense.occurred_at)[:10] 
            if existing_date == occurred_at and int(expense.amount_minor) == int(amount):
                match = {
                    "domain": "finance",
                    "record_type": "expense",
                    "record_id": str(expense.expense_id), 
                    "record_id_arg": "expense_id",
                    "update_tool": "update_expense",
                }
                results.append({
                    "severity": "CONFLICT",
                    "details": f"An expense for {amount} was already logged on {occurred_at}. Is this a duplicate?",
                    "match": match
                })

        return "CONFLICT" if results else "CLEAR", results
    except Exception:
        return "CLEAR", []
    finally:
        session.close()


def _check_repair_overlap(args: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    appliance_id = str(args.get("appliance_id") or "").strip()
    serviced_at = str(args.get("serviced_at") or "").strip()[:10]
    results = []

    if not appliance_id or not serviced_at:
        return "CLEAR", results

    session = SessionLocal()
    try:
        from app.models.maintenance import Repair
        repairs = session.query(Repair).filter(Repair.appliance_id == appliance_id).all()

        for repair in repairs:
            existing_date = str(repair.serviced_at)[:10]
            if existing_date == serviced_at:
                match = {
                    "domain": "maintenance",
                    "record_type": "repair",
                    "record_id": str(repair.repair_id),
                    "record_id_arg": "repair_id",
                    "update_tool": "update_repair",
                }
                results.append({
                    "severity": "CONFLICT",
                    "details": f"A repair is already logged for this appliance on {serviced_at}.",
                    "match": match
                })

        return "CONFLICT" if results else "CLEAR", results
    except Exception:
        return "CLEAR", []
    finally:
        session.close()


def _check_calendar_overlap(args: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    requested_title = _normalize(args.get("title"))
    starts_at_dt = _parse_datetime(args.get("starts_at") or "")
    ends_at_dt = _parse_datetime(args.get("ends_at") or "")
    results = []

    if not starts_at_dt or not ends_at_dt:
        return "CLEAR", results

    session = SessionLocal()
    try:
        from app.models.tasks import CalendarEvent, Task
        
        # 1. SQL filter for Calendar Events (Overlap: existing_start < new_end AND existing_end > new_start)
        events = session.query(CalendarEvent).filter(
            CalendarEvent.starts_at < ends_at_dt,
            CalendarEvent.ends_at > starts_at_dt
        ).all()
        
        for event in events:
            existing_title = _normalize(event.title)
            is_similar_name = (requested_title in existing_title or existing_title in requested_title)
            
            match = {
                "domain": "tasks",
                "record_type": "calendar_event",
                "record_id": str(event.event_id),
                "record_id_arg": "event_id",
                "update_tool": "update_calendar_event",
                "title": event.title,
            }
            if is_similar_name:
                results.append({"severity": "DUPLICATE", "details": f"A similar event '{event.title}' is already scheduled at this time. Should I update it?", "match": match})
            else:
                results.append({"severity": "CONFLICT", "details": f"This time conflicts with your existing event '{event.title}'.", "match": match})

        # 2. SQL filter for scheduled Tasks within the new event's time window
        tasks = session.query(Task).filter(
            Task.due_at >= starts_at_dt,
            Task.due_at <= ends_at_dt
        ).all()
        
        for task in tasks:
            status_val = str(task.status.value).upper() if hasattr(task.status, 'value') else str(task.status).upper()
            if status_val == "COMPLETED":
                continue
                
            match = {
                "domain": "tasks",
                "record_type": "task",
                "record_id": str(task.task_id),
                "record_id_arg": "task_id",
                "update_tool": "update_task",
                "title": task.title,
            }
            results.append({"severity": "CONFLICT", "details": f"This event overlaps with your scheduled task '{task.title}' due at {task.due_at}.", "match": match})

        overall = "DUPLICATE" if any(r["severity"] == "DUPLICATE" for r in results) else ("CONFLICT" if results else "CLEAR")
        return overall, results

    except Exception:
        return "CLEAR", []
    finally:
        session.close()


def _check_task_overlap(args: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    requested_title = _normalize(args.get("title"))
    due_at_dt = _parse_datetime(args.get("due_at") or "")
    results = []

    if not requested_title:
        return "CLEAR", results

    session = SessionLocal()
    try:
        from app.models.tasks import CalendarEvent, Task
        
        if due_at_dt:
            # 1. SQL filter for incomplete Tasks with the exact same deadline
            tasks = session.query(Task).filter(Task.due_at == due_at_dt).all()
            for task in tasks:
                status_val = str(task.status.value).upper() if hasattr(task.status, 'value') else str(task.status).upper()
                if status_val == "COMPLETED":
                    continue
                    
                existing_title = _normalize(task.title)
                is_similar_name = (requested_title in existing_title or existing_title in requested_title)
                
                if is_similar_name:
                    match = {
                        "domain": "tasks",
                        "record_type": "task",
                        "record_id": str(task.task_id),
                        "record_id_arg": "task_id",
                        "update_tool": "update_task",
                        "title": task.title,
                    }
                    results.append({"severity": "DUPLICATE", "details": f"You already have a similar task '{task.title}' scheduled for this time.", "match": match})

            # 2. SQL filter for Calendar Events blocking this specific task time
            events = session.query(CalendarEvent).filter(
                CalendarEvent.starts_at <= due_at_dt,
                CalendarEvent.ends_at >= due_at_dt
            ).all()
            
            for event in events:
                match = {
                    "domain": "tasks",
                    "record_type": "calendar_event",
                    "record_id": str(event.event_id),
                    "record_id_arg": "event_id",
                    "update_tool": "update_calendar_event",
                    "title": event.title,
                }
                results.append({"severity": "CONFLICT", "details": f"Your task '{requested_title}' is scheduled during your event '{event.title}'.", "match": match})

        overall = "DUPLICATE" if any(r["severity"] == "DUPLICATE" for r in results) else ("CONFLICT" if results else "CLEAR")
        return overall, results

    except Exception:
        return "CLEAR", []
    finally:
        session.close()

DUPLICATE_CHECKERS = {
    
    "create_calendar_event": _check_calendar_overlap,
    "create_task": _check_task_overlap,
}

def check_consistency(
    domain: str,
    operation: str,
    arguments: Dict[str, Any],
    user_id: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Compatibility adapter around the shared consistency service.

    Grocery, inventory, finance, task creation, and Maintenance create
    operations use the shared service. Remaining legacy operations stay on
    their existing checkers until they are migrated.
    """

    if operation in {
        "add_grocery_item",
        "add_inventory_item",
        "log_expense",
        "create_task",
        "add_appliance",
        "report_issue",
        "log_repair",
    }:
        shared_result = check_shared_consistency(
            domain=domain,
            operation=operation,
            arguments=arguments,
            user_id=user_id,
        )

        legacy_status = _legacy_consistency_status(
            shared_result.status
        )

        ordered_findings = sorted(
            shared_result.findings,
            key=lambda finding: finding.priority,
            reverse=True,
        )

        results = []

        for finding in ordered_findings:
            results.append(
                {
                    "severity": (
                        _legacy_consistency_status(
                            finding.status
                        )
                    ),
                    "details": finding.details,
                    "match": dict(finding.match),

                    # Preserve new metadata for the clarification
                    # migration that comes next.
                    "consistency_code": finding.code,
                    "consistency_status": finding.status,
                    "confidence": finding.confidence,
                    "signals": dict(finding.signals),
                    "resolution_type": (
                        finding.resolution_type
                    ),
                    "allowed_resolutions": list(
                        finding.allowed_resolutions
                    ),
                }
            )

        return legacy_status, results

    checker = DUPLICATE_CHECKERS.get(
        operation
    )

    if not checker:
        return "CLEAR", []

    result = checker(arguments)

    # Compatibility bridge for legacy checkers that return either:
    #   (status, results_list)
    # or:
    #   (status, details, match)
    #
    # Never allow this adapter to fall through and implicitly return None.
    if not isinstance(result, tuple):
        return "CLEAR", []

    if len(result) == 3:
        status, details, match = result

        if status == "NEW":
            status = "CLEAR"

        if status != "CLEAR" and match:
            return status, [
                {
                    "severity": status,
                    "details": details,
                    "match": match,
                }
            ]

        return "CLEAR", []

    if len(result) == 2:
        status, results = result

        if not isinstance(results, list):
            return "CLEAR", []

        return status, results

    return "CLEAR", []

def _legacy_consistency_status(
        status: str,
    ) -> str:
    """
    Translate the new shared consistency contract into the
    graph's temporary legacy status vocabulary.
    """

    if status == CLEAR:
        return "CLEAR"

    if status == EXACT_DUPLICATE:
        return "DUPLICATE"

    if status == POSSIBLE_DUPLICATE:
        return "POSSIBLE_DUPLICATE"

    if status == BLOCKED:
        return "CONFLICT"

    # QUANTITY_CONFLICT, TIME_CONFLICT, STATE_CONFLICT,
    # RELATION_CONFLICT, VERSION_CONFLICT, etc.
    return "CONFLICT"

def duplicate_check_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Run centralized consistency checks and preserve matched records."""
    call = state.get("pending_tool_call")
    force_review = bool(state.get("force_action_review"))

    if not call:
        return {
            "consistency_status": "CLEAR",
            "consistency_results": [],
            "duplicate_status": "CLEAR",
            "duplicate_details": None,
            "duplicate_match": None,
            "awaiting_confirmation": False,
        }

    tool_name = call.get("name", "")
    args = call.get("args", {})
    
    actions = state.get("planned_actions") or []
    index = state.get("current_action_index", 0)
    domain = actions[index].get("domain", "general") if 0 <= index < len(actions) else "general"
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")

    # GUARD: Prevent unauthorized data leaks during duplicate lookup
    if not is_authorized(role, domain, tool_name):
        return {
            "consistency_status": "CLEAR", 
            "consistency_results": [],
            "duplicate_status": "UNAUTHORIZED", 
            "duplicate_details": None,
            "duplicate_match": None, 
            "awaiting_confirmation": False
        }

    status, results = check_consistency(domain, tool_name, args, user_id)

    needs_confirmation = (status in {"DUPLICATE", "CONFLICT", "POSSIBLE_DUPLICATE"} or force_review)

    if status in {"DUPLICATE", "CONFLICT", "POSSIBLE_DUPLICATE"}:
        confirmation_kind = "conflict" if status == "CONFLICT" else "duplicate"
    elif state.get("confirmation_kind") == "suggestion":
        confirmation_kind = "suggestion"
    else:
        confirmation_kind = "action"

    primary_details = results[0]["details"] if results else None
    primary_match = results[0]["match"] if results else None

    if force_review and not primary_details:
        primary_details = "You edited the pending action. The revised action must be reviewed again before it can execute."

    return {
        "consistency_status": status,
        "consistency_results": results,
        "duplicate_status": status,
        "duplicate_details": primary_details,
        "duplicate_match": primary_match,
        "confirmation_kind": confirmation_kind,
        "awaiting_confirmation": needs_confirmation,
    }

def route_after_duplicate(state: AgentState) -> str:
    # Route unauthorized requests straight to the authorize node to fail normally
    if state.get("duplicate_status") == "UNAUTHORIZED":
        return "authorize"

    status = state.get("consistency_status") or state.get("duplicate_status")

    if (
        status in {"DUPLICATE", "CONFLICT", "POSSIBLE_DUPLICATE"}
        or state.get("force_action_review")
    ):
        return "request_confirmation"

    if state.get("confirmation_resolution") == "suggestion_confirmed":
        return "suggestion_approve"

    return "authorize"