"""Food & inventory domain tools: grocery list and stocked items."""
from __future__ import annotations

from langchain_core.tools import tool

from app.db.base import SessionLocal
from app.models.inventory import GroceryItem, InventoryItem


# ============================================================
# Grocery CRUD
# ============================================================

@tool
def add_grocery_item(
    name: str,
    quantity: float = 1,
    unit: str = "",
) -> str:
    """Add an item to the active grocery list."""
    session = SessionLocal()
    try:
        item = GroceryItem(
            name=name,
            quantity=quantity,
            unit=unit or None,
            purchased=False,
        )

        session.add(item)
        session.commit()
        session.refresh(item)

        return (
            f"Added {quantity}"
            f"{(' ' + unit) if unit else ''} {name} "
            f"to the grocery list. "
            f"Grocery item id: {item.grocery_item_id}"
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


@tool
def list_grocery_items(
    purchased: bool | None = None,
) -> str:
    """List grocery items, optionally filtering by purchased status."""
    session = SessionLocal()
    try:
        query = session.query(GroceryItem)

        if purchased is not None:
            query = query.filter(GroceryItem.purchased == purchased)

        rows = query.order_by(GroceryItem.created_at.desc()).all()

        if not rows:
            return "No grocery items found."

        result = []

        for item in rows:
            quantity = (
                f"{item.quantity}"
                f"{(' ' + item.unit) if item.unit else ''}"
            )

            status = "purchased" if item.purchased else "pending"

            result.append(
                f"- {item.name}: {quantity} "
                f"({status}, id={item.grocery_item_id})"
            )

        return "\n".join(result)

    finally:
        session.close()


@tool
def get_grocery_item(
    grocery_item_id: str,
) -> str:
    """Get one grocery item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(GroceryItem, grocery_item_id)

        if not item:
            return f"No grocery item found with id {grocery_item_id}."

        quantity = (
            f"{item.quantity}"
            f"{(' ' + item.unit) if item.unit else ''}"
        )

        status = "purchased" if item.purchased else "pending"

        return (
            f"Grocery item: {item.name}; "
            f"quantity: {quantity}; "
            f"status: {status}; "
            f"id: {item.grocery_item_id}"
        )

    finally:
        session.close()


@tool
def update_grocery_item(
    grocery_item_id: str,
    name: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    purchased: bool | None = None,
) -> str:
    """Update an existing grocery item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(GroceryItem, grocery_item_id)

        if not item:
            return f"No grocery item found with id {grocery_item_id}."

        changed = []

        if name is not None:
            item.name = name
            changed.append(f"name='{name}'")

        if quantity is not None:
            item.quantity = quantity
            changed.append(f"quantity={quantity}")

        if unit is not None:
            item.unit = unit or None
            changed.append(
                f"unit='{unit}'" if unit else "unit cleared"
            )

        if purchased is not None:
            item.purchased = purchased
            changed.append(
                "purchased"
                if purchased
                else "marked as not purchased"
            )

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated grocery item '{item.name}' "
            f"({item.grocery_item_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


@tool
def delete_grocery_item(
    grocery_item_id: str,
) -> str:
    """Delete a grocery item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(GroceryItem, grocery_item_id)

        if not item:
            return f"No grocery item found with id {grocery_item_id}."

        name = item.name

        session.delete(item)
        session.commit()

        return (
            f"Deleted grocery item '{name}' "
            f"(id={grocery_item_id})."
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


@tool
def mark_purchased(
    grocery_item_id: str,
) -> str:
    """Mark a grocery list item as purchased by its id."""
    session = SessionLocal()
    try:
        item = session.get(GroceryItem, grocery_item_id)

        if not item:
            return f"No grocery item found with id {grocery_item_id}."

        item.purchased = True
        session.commit()

        return f"Marked '{item.name}' as purchased."

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


# ============================================================
# Inventory CRUD
# ============================================================

@tool
def add_inventory_item(
    name: str,
    quantity: float = 1,
    unit: str = "",
    low_stock_threshold: float | None = None,
) -> str:
    """Add an item to household inventory."""
    session = SessionLocal()
    try:
        item = InventoryItem(
            name=name,
            quantity=quantity,
            unit=unit or None,
            low_stock_threshold=low_stock_threshold,
        )

        session.add(item)
        session.commit()
        session.refresh(item)

        return (
            f"Added {quantity}"
            f"{(' ' + unit) if unit else ''} {name} "
            f"to inventory. "
            f"Inventory item id: {item.item_id}"
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


@tool
def list_inventory(
    low_stock_only: bool = False,
) -> str:
    """List stocked inventory items, optionally only those at/below their low-stock threshold."""
    session = SessionLocal()
    try:
        query = session.query(InventoryItem)

        if low_stock_only:
            query = query.filter(
                InventoryItem.low_stock_threshold.isnot(None),
                InventoryItem.quantity <= InventoryItem.low_stock_threshold,
            )

        rows = query.order_by(InventoryItem.created_at.desc()).all()

        if not rows:
            return "No inventory items found."

        result = []

        for item in rows:
            quantity = (
                f"{item.quantity}"
                f"{(' ' + item.unit) if item.unit else ''}"
            )

            threshold = ""
            if item.low_stock_threshold is not None:
                threshold = (
                    f", low-stock threshold={item.low_stock_threshold}"
                )

            result.append(
                f"- {item.name}: {quantity}"
                f"{threshold} "
                f"(id={item.item_id})"
            )

        return "\n".join(result)

    finally:
        session.close()


@tool
def get_inventory_item(
    item_id: str,
) -> str:
    """Get one inventory item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(InventoryItem, item_id)

        if not item:
            return f"No inventory item found with id {item_id}."

        quantity = (
            f"{item.quantity}"
            f"{(' ' + item.unit) if item.unit else ''}"
        )

        threshold = (
            f"{item.low_stock_threshold}"
            if item.low_stock_threshold is not None
            else "not set"
        )

        return (
            f"Inventory item: {item.name}; "
            f"quantity: {quantity}; "
            f"low-stock threshold: {threshold}; "
            f"id: {item.item_id}"
        )

    finally:
        session.close()


@tool
def update_inventory_item(
    item_id: str,
    name: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    low_stock_threshold: float | None = None,
) -> str:
    """Update an existing inventory item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(InventoryItem, item_id)

        if not item:
            return f"No inventory item found with id {item_id}."

        changed = []

        if name is not None:
            item.name = name
            changed.append(f"name='{name}'")

        if quantity is not None:
            item.quantity = quantity
            changed.append(f"quantity={quantity}")

        if unit is not None:
            item.unit = unit or None
            changed.append(
                f"unit='{unit}'" if unit else "unit cleared"
            )

        if low_stock_threshold is not None:
            item.low_stock_threshold = low_stock_threshold
            changed.append(
                f"low_stock_threshold={low_stock_threshold}"
            )

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated inventory item '{item.name}' "
            f"({item.item_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


@tool
def delete_inventory_item(
    item_id: str,
) -> str:
    """Delete an inventory item by its stable database id."""
    session = SessionLocal()
    try:
        item = session.get(InventoryItem, item_id)

        if not item:
            return f"No inventory item found with id {item_id}."

        name = item.name

        session.delete(item)
        session.commit()

        return (
            f"Deleted inventory item '{name}' "
            f"(id={item_id})."
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


# ============================================================
# Tool registry
# ============================================================

TOOLS = [
    # Grocery
    add_grocery_item,
    list_grocery_items,
    get_grocery_item,
    update_grocery_item,
    delete_grocery_item,
    mark_purchased,

    # Inventory
    add_inventory_item,
    list_inventory,
    get_inventory_item,
    update_inventory_item,
    delete_inventory_item,
]

TOOLS_BY_NAME = {
    tool_fn.name: tool_fn
    for tool_fn in TOOLS
}