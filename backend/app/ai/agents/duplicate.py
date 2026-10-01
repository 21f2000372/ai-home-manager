from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.inventory import GroceryItem, InventoryItem


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


DUPLICATE_CHECKERS = {
    "add_grocery_item": _check_grocery,
    "add_inventory_item": _check_inventory,
}


def duplicate_check_node(
    state: AgentState,
) -> Dict[str, Any]:
    """Run duplicate checks and preserve the matched record structurally.

    ``duplicate_match`` is intentionally server-derived.  It allows a later
    explicit user resolution such as "update it to 3 kg" to target the exact
    existing row without asking the model to recover a database id from prose.
    """

    call = state.get("pending_tool_call")
    force_review = bool(
        state.get("force_action_review")
    )

    if not call:
        return {
            "duplicate_status": "NEW",
            "duplicate_details": None,
            "duplicate_match": None,
            "awaiting_confirmation": False,
        }

    tool_name = call.get("name", "")
    checker = DUPLICATE_CHECKERS.get(tool_name)

    status = "NEW"
    details = None
    match = None

    if checker is not None:
        status, details, match = checker(
            call.get("args", {})
        )

    needs_confirmation = (
        status in {"DUPLICATE", "CONFLICT"}
        or force_review
    )

    if status == "DUPLICATE":
        confirmation_kind = "duplicate"
    elif status == "CONFLICT":
        confirmation_kind = "conflict"
    elif state.get("confirmation_kind") == "suggestion":
        confirmation_kind = "suggestion"
    else:
        confirmation_kind = "action"

    if force_review and not details:
        details = (
            "You edited the pending action. The revised action must be "
            "reviewed again before it can execute."
        )

    return {
        "duplicate_status": status,
        "duplicate_details": details,
        "duplicate_match": match,
        "confirmation_kind": confirmation_kind,
        "awaiting_confirmation": needs_confirmation,
    }


def route_after_duplicate(
    state: AgentState,
) -> str:
    status = state.get("duplicate_status")

    if (
        status in {"DUPLICATE", "CONFLICT"}
        or state.get("force_action_review")
    ):
        return "request_confirmation"

    if state.get("confirmation_resolution") == "suggestion_confirmed":
        return "suggestion_approve"

    return "authorize"
