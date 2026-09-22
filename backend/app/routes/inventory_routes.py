"""REST routes for Inventory, Grocery Lists, and Recurring Commodities."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole
from app.services.inventory import InventoryService

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


# -----------------------------------------------------------------------------
# Inventory Endpoints
# -----------------------------------------------------------------------------


@inventory_bp.route("", methods=["GET"])
@login_required
def get_inventory():
    """Retrieve full household inventory stock."""
    session = SessionLocal()
    try:
        items = InventoryService.get_all_inventory(session)
        return (
            jsonify(
                [
                    {
                        "item_id": i.item_id,
                        "name": i.name,
                        "quantity": float(i.quantity),
                        "unit": i.unit,
                        "low_stock_threshold": (
                            float(i.low_stock_threshold)
                            if i.low_stock_threshold
                            else None
                        ),
                    }
                    for i in items
                ]
            ),
            200,
        )
    finally:
        session.close()


@inventory_bp.route("/low-stock", methods=["GET"])
@login_required
def get_low_stock():
    """US-3.1: Return items that have breached low stock thresholds."""
    session = SessionLocal()
    try:
        items = InventoryService.get_low_stock_items(session)
        return (
            jsonify(
                [
                    {
                        "item_id": i.item_id,
                        "name": i.name,
                        "quantity": float(i.quantity),
                        "unit": i.unit,
                        "low_stock_threshold": (
                            float(i.low_stock_threshold)
                            if i.low_stock_threshold
                            else None
                        ),
                    }
                    for i in items
                ]
            ),
            200,
        )
    finally:
        session.close()


@inventory_bp.route("", methods=["POST"])
@login_required
def add_or_update_inventory():
    """Update stock quantities (Adult and Admin only)."""
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return (
            jsonify(
                {
                    "error": "Forbidden: Only Adult and Admin can update inventory stock levels"
                }
            ),
            403,
        )

    data = request.get_json() or {}
    name = data.get("name")
    quantity = data.get("quantity")

    if not name or quantity is None:
        return jsonify({"error": "name and quantity are required"}), 400

    session = SessionLocal()
    try:
        item = InventoryService.add_or_update_stock(
            session=session,
            name=name,
            quantity=float(quantity),
            unit=data.get("unit"),
            low_stock_threshold=(
                float(data["low_stock_threshold"])
                if data.get("low_stock_threshold") is not None
                else None
            ),
        )
        return (
            jsonify(
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                    "low_stock_threshold": item.low_stock_threshold,
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@inventory_bp.route("/<string:item_id>", methods=["PUT"])
@login_required
def update_inventory_item(item_id: str):
    """Update stock details (Adult and Admin only)."""
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can modify inventory stock"}), 403

    data = request.get_json() or {}
    session = SessionLocal()
    try:
        item = InventoryService.update_inventory_item(
            session=session,
            item_id=item_id,
            name=data.get("name"),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            low_stock_threshold=data.get("low_stock_threshold"),
        )
        return jsonify({
            "item_id": item.item_id,
            "name": item.name,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "low_stock_threshold": float(item.low_stock_threshold) if item.low_stock_threshold is not None else None,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@inventory_bp.route("/<string:item_id>", methods=["DELETE"])
@login_required
def delete_inventory_item(item_id: str):
    """Delete stock item (Adult and Admin only)."""
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can delete inventory items"}), 403

    session = SessionLocal()
    try:
        InventoryService.delete_inventory_item(session, item_id)
        return jsonify({"message": "Inventory item deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Grocery List Endpoints (US-3.4)
# -----------------------------------------------------------------------------


@inventory_bp.route("/groceries", methods=["GET"])
@login_required
def get_groceries():
    """Retrieve active shopping list. Supports ?include_purchased=true."""
    include_purchased = request.args.get("include_purchased", "false").lower() == "true"
    session = SessionLocal()
    try:
        groceries = InventoryService.get_grocery_list(
            session, include_purchased=include_purchased
        )
        return (
            jsonify(
                [
                    {
                        "grocery_item_id": g_item.grocery_item_id,
                        "name": g_item.name,
                        "quantity": float(g_item.quantity) if g_item.quantity else None,
                        "unit": g_item.unit,
                        "purchased": g_item.purchased,
                        "added_by": g_item.added_by,
                    }
                    for g_item in groceries
                ]
            ),
            200,
        )
    finally:
        session.close()


@inventory_bp.route("/groceries", methods=["POST"])
@login_required
def add_grocery():
    """Add item to shopping list (Children, Adults, and Admins permitted; Guests blocked)."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Item name is required"}), 400

    session = SessionLocal()
    try:
        item = InventoryService.add_grocery_item(
            session=session,
            name=name,
            added_by_id=g.current_user.user_id,
            quantity=(
                float(data["quantity"]) if data.get("quantity") is not None else 1.0
            ),
            unit=data.get("unit"),
        )
        return (
            jsonify(
                {
                    "grocery_item_id": item.grocery_item_id,
                    "name": item.name,
                    "quantity": float(item.quantity) if item.quantity else None,
                    "purchased": item.purchased,
                    "added_by_id": item.added_by,
                    "unit": item.unit,
                }
            ),
            201,
        )
    finally:
        session.close()


@inventory_bp.route("/groceries/<string:grocery_item_id>/purchase", methods=["PATCH"])
@login_required
def toggle_grocery(grocery_item_id: str):
    """US-3.4: Toggle item purchased state."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    purchased = data.get("purchased", True)

    session = SessionLocal()
    try:
        item = InventoryService.toggle_grocery_purchased(
            session, grocery_item_id, purchased
        )
        return (
            jsonify(
                {
                    "grocery_item_id": item.grocery_item_id,
                    "purchased": item.purchased,
                    "unit": item.unit,
                    "added_by": item.added_by,
                    "name": item.name,
                    "quantity": item.quantity,
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()

@inventory_bp.route("/groceries/<string:grocery_item_id>", methods=["PUT"])
@login_required
def update_grocery_item(grocery_item_id: str):
    """Update a grocery item (Children, Adults, and Admins allowed; Guests blocked)."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    session = SessionLocal()
    try:
        item = InventoryService.update_grocery_item(
            session=session,
            grocery_item_id=grocery_item_id,
            name=data.get("name"),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
        )
        return jsonify({
            "grocery_item_id": item.grocery_item_id,
            "name": item.name,
            "quantity": float(item.quantity) if item.quantity is not None else None,
            "unit": item.unit,
            "purchased": item.purchased,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@inventory_bp.route("/groceries/<string:grocery_item_id>", methods=["DELETE"])
@login_required
def delete_grocery(grocery_item_id: str):
    """Delete grocery item from list (Children, Adults, and Admins allowed; Guests blocked)."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    session = SessionLocal()
    try:
        InventoryService.delete_grocery_item(session, grocery_item_id)
        return jsonify({"message": "Grocery item removed successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Recurring Daily Commodities (US-3.5, US-3.6)
# -----------------------------------------------------------------------------


@inventory_bp.route("/commodities", methods=["POST"])
@login_required
def create_commodity():
    """US-3.5: Define a recurring daily purchase rule and generate today's occurrence."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Commodity name is required"}), 400

    session = SessionLocal()
    try:
        # 1. Create the recurring commodity rule
        rule = InventoryService.create_commodity_rule(
            session=session,
            name=name,
            schedule=data.get("schedule", "DAILY"),
            quantity=float(data.get("quantity", 1.0)),
            unit=data.get("unit"),
            preferred_brand=data.get("preferred_brand"),
            low_stock_threshold=(
                float(data["low_stock_threshold"])
                if data.get("low_stock_threshold") is not None
                else None
            ),
        )

        # 2. Immediately generate and persist today's purchase occurrence
        occurrence = InventoryService.generate_daily_occurrence(
            session=session,
            rule_id=rule.rule_id,
        )

        return (
            jsonify(
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "schedule": rule.schedule,
                    "quantity": float(rule.quantity),
                    "unit": rule.unit,
                    "preferred_brand": rule.preferred_brand,
                    "low_stock_threshold": (
                        float(rule.low_stock_threshold)
                        if rule.low_stock_threshold is not None
                        else None
                    ),
                    "today_occurrence": {
                        "occurrence_id": occurrence.occurrence_id,
                        "occurrence_date": occurrence.occurrence_date.isoformat(),
                        "status": occurrence.status.value,
                    },
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@inventory_bp.route(
    "/commodities/<string:occurrence_id>/mark-purchased", methods=["POST"]
)
@login_required
def purchase_occurrence(occurrence_id: str):
    """US-3.6: Mark a daily commodity fulfilled and update inventory stock."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    session = SessionLocal()
    try:
        occurrence, item = InventoryService.mark_occurrence_purchased(
            session=session,
            occurrence_id=occurrence_id,
            restock_inventory=True,
        )
        return (
            jsonify(
                {
                    "occurrence_id": occurrence.occurrence_id,
                    "status": occurrence.status.value,
                    "inventory_restocked": item.name if item else None,
                    "new_inventory_quantity": float(item.quantity) if item else None,
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()

@inventory_bp.route("/commodities/<string:rule_id>", methods=["PUT"])
@login_required
def update_commodity_rule(rule_id: str):
    """Update recurring commodity rule (Adult and Admin only)."""
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can modify commodity rules"}), 403

    data = request.get_json() or {}
    session = SessionLocal()
    try:
        rule = InventoryService.update_commodity_rule(
            session=session,
            rule_id=rule_id,
            name=data.get("name"),
            schedule=data.get("schedule"),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            preferred_brand=data.get("preferred_brand"),
            low_stock_threshold=data.get("low_stock_threshold"),
            active=data.get("active"),
        )
        return jsonify({
            "rule_id": rule.rule_id,
            "name": rule.name,
            "schedule": rule.schedule,
            "quantity": float(rule.quantity),
            "unit": rule.unit,
            "preferred_brand": rule.preferred_brand,
            "low_stock_threshold": float(rule.low_stock_threshold) if rule.low_stock_threshold is not None else None,
            "active": rule.active,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@inventory_bp.route("/commodities/<string:rule_id>", methods=["DELETE"])
@login_required
def delete_commodity(rule_id: str):
    """Delete a recurring commodity rule (Adult and Admin only)."""
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can delete commodity rules"}), 403

    session = SessionLocal()
    try:
        InventoryService.delete_commodity_rule(session, rule_id)
        return jsonify({"message": "Commodity rule deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()