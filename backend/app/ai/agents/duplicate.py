from __future__ import annotations

from decimal import Decimal

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal
from app.models.inventory import GroceryItem, InventoryItem


def _normalize(value: str | None) -> str:
    """
    Normalize names/units for deterministic comparison.

    Examples:
        " Apples " -> "apples"
        "RED   Apples" -> "red apples"
    """
    return " ".join(
        (value or "").casefold().strip().split()
    )


def _number(value) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _check_grocery(
    args: dict,
) -> tuple[str, str | None]:
    """
    Check whether an active grocery item with the same name exists.

    Returns:
        ("NEW", None)
        ("DUPLICATE", details)
        ("CONFLICT", details)
    """

    requested_name = _normalize(
        args.get("name")
    )

    if not requested_name:
        return "NEW", None

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
            return "NEW", None

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
            f"{existing.quantity}"
            f"{(' ' + existing.unit) if existing.unit else ''}"
        )

        requested_quantity_text = (
            f"{args.get('quantity', 1)}"
            f"{(' ' + str(args.get('unit'))) if args.get('unit') else ''}"
        )

        if exact_match:
            return (
                "DUPLICATE",
                (
                    f"'{existing.name}' is already on the "
                    f"active grocery list with quantity "
                    f"{existing_quantity_text} "
                    f"(id={existing.grocery_item_id})."
                ),
            )

        return (
            "CONFLICT",
            (
                f"'{existing.name}' is already on the "
                f"active grocery list as "
                f"{existing_quantity_text} "
                f"(id={existing.grocery_item_id}), "
                f"while the new request is "
                f"{requested_quantity_text} "
                f"{args.get('name')}."
            ),
        )

    finally:
        session.close()


def _check_inventory(
    args: dict,
) -> tuple[str, str | None]:
    requested_name = _normalize(
        args.get("name")
    )

    if not requested_name:
        return "NEW", None

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
            return "NEW", None

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
            f"'{existing.name}' already exists in "
            f"inventory with quantity "
            f"{existing.quantity}"
            f"{(' ' + existing.unit) if existing.unit else ''} "
            f"(id={existing.item_id})."
        )

        return status, details

    finally:
        session.close()


DUPLICATE_CHECKERS = {
    "add_grocery_item": _check_grocery,
    "add_inventory_item": _check_inventory,
}


def duplicate_check_node(
    state: AgentState,
) -> dict:
    """
    Runs after Specialist chooses a tool, but before authorization
    and execution.

    Only tools registered in DUPLICATE_CHECKERS are checked.
    All other tools continue normally.
    """

    call = state.get(
        "pending_tool_call"
    )

    if not call:
        return {
            "duplicate_status": "NEW",
            "duplicate_details": None,
            "awaiting_confirmation": False,
        }

    tool_name = call.get(
        "name",
        "",
    )

    checker = DUPLICATE_CHECKERS.get(
        tool_name
    )

    if checker is None:
        return {
            "duplicate_status": "NEW",
            "duplicate_details": None,
            "awaiting_confirmation": False,
        }

    status, details = checker(
        call.get("args", {})
    )

    return {
        "duplicate_status": status,
        "duplicate_details": details,
        "awaiting_confirmation": (
            status in {
                "DUPLICATE",
                "CONFLICT",
            }
        ),
    }


def route_after_duplicate(
    state: AgentState,
) -> str:
    status = state.get(
        "duplicate_status"
    )

    if status in {
        "DUPLICATE",
        "CONFLICT",
    }:
        return "request_confirmation"

    return "authorize"