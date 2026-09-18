"""Service layer for Inventory, Grocery shopping list, and Recurring Commodities."""
from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.enums import OccurrenceStatus
from app.models.inventory import CommodityRule, GroceryItem, InventoryItem, PurchaseOccurrence


class InventoryService:
    # -------------------------------------------------------------------------
    # Inventory Items & Low-Stock Alerts (US-3.1)
    # -------------------------------------------------------------------------

    @staticmethod
    def get_all_inventory(session: Session) -> List[InventoryItem]:
        """Fetch all stocked household inventory items."""
        return session.query(InventoryItem).order_by(InventoryItem.name.asc()).all()

    @staticmethod
    def get_low_stock_items(session: Session) -> List[InventoryItem]:
        """US-3.1: Retrieve items where stock level is less than or equal to threshold.
        
        >>> AGENT HOOK:
        >>> Used by the Inventory Agent for US-3.2 ('what are we out of?').
        >>> The agent calls this method via tool execution to summarize low stock.
        """
        return (
            session.query(InventoryItem)
            .filter(
                InventoryItem.low_stock_threshold.isnot(None),
                InventoryItem.quantity <= InventoryItem.low_stock_threshold,
            )
            .order_by(InventoryItem.name.asc())
            .all()
        )

    @staticmethod
    def add_or_update_stock(
        session: Session,
        name: str,
        quantity: float,
        unit: Optional[str] = None,
        low_stock_threshold: Optional[float] = None,
    ) -> InventoryItem:
        """Add a new inventory item or increment stock if it already exists."""
        item = (
            session.query(InventoryItem)
            .filter(InventoryItem.name.ilike(name.strip()))
            .first()
        )
        if item:
            item.quantity = float(item.quantity) + float(quantity)
            if unit:
                item.unit = unit
            if low_stock_threshold is not None:
                item.low_stock_threshold = low_stock_threshold
        else:
            item = InventoryItem(
                name=name.strip(),
                quantity=quantity,
                unit=unit,
                low_stock_threshold=low_stock_threshold,
            )
            session.add(item)

        session.commit()
        return item

    # -------------------------------------------------------------------------
    # Grocery List (US-3.4)
    # -------------------------------------------------------------------------

    @staticmethod
    def get_grocery_list(session: Session, include_purchased: bool = False) -> List[GroceryItem]:
        """Retrieve items currently on the household grocery list."""
        query = session.query(GroceryItem)
        if not include_purchased:
            query = query.filter(GroceryItem.purchased.is_(False))
        return query.order_by(GroceryItem.created_at.desc()).all()

    @staticmethod
    def add_grocery_item(
        session: Session,
        name: str,
        added_by_id: str,
        quantity: Optional[float] = 1.0,
        unit: Optional[str] = None,
    ) -> GroceryItem:
        """Add an item directly to the active grocery list.
        
        >>> AGENT HOOK:
        >>> The Orchestrator / Inventory Agent will call this when building
        >>> grocery lists from recipes or meal plans (US-3.3).
        """
        grocery_item = GroceryItem(
            name=name.strip(),
            quantity=quantity,
            unit=unit,
            purchased=False,
            added_by=added_by_id,
        )
        session.add(grocery_item)
        session.commit()
        return grocery_item

    @staticmethod
    def toggle_grocery_purchased(
        session: Session,
        grocery_item_id: str,
        purchased: bool = True,
    ) -> GroceryItem:
        """US-3.4: Mark an item on the shopping list as bought or unbought."""
        item = session.query(GroceryItem).filter(GroceryItem.grocery_item_id == grocery_item_id).first()
        if not item:
            raise ValueError("Grocery item not found")
        item.purchased = purchased
        session.commit()
        return item

    # -------------------------------------------------------------------------
    # Recurring Daily Commodities & Occurrences (US-3.5, US-3.6)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_commodity_rule(
        session: Session,
        name: str,
        schedule: str = "DAILY",
        quantity: float = 1.0,
        unit: Optional[str] = None,
        preferred_brand: Optional[str] = None,
        low_stock_threshold: Optional[float] = None,
    ) -> CommodityRule:
        """US-3.5: Define a recurring commodity rule (e.g., 1L milk daily)."""
        rule = CommodityRule(
            name=name.strip(),
            schedule=schedule.strip(),
            quantity=quantity,
            unit=unit,
            preferred_brand=preferred_brand,
            low_stock_threshold=low_stock_threshold,
            active=True,
        )
        session.add(rule)
        session.commit()
        return rule

    @classmethod
    def generate_daily_occurrence(
        cls,
        session: Session,
        rule_id: str,
        target_date: Optional[date] = None,
    ) -> PurchaseOccurrence:
        """Generate a purchase occurrence for a scheduled commodity date."""
        target = target_date or date.today()
        
        # Prevent duplicate occurrences for the same day
        existing = (
            session.query(PurchaseOccurrence)
            .filter(
                PurchaseOccurrence.rule_id == rule_id,
                PurchaseOccurrence.occurrence_date == target,
            )
            .first()
        )
        if existing:
            return existing

        rule = session.query(CommodityRule).filter(CommodityRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError("Commodity rule not found")

        # Find or link corresponding inventory item
        inv_item = session.query(InventoryItem).filter(InventoryItem.name.ilike(rule.name)).first()

        occurrence = PurchaseOccurrence(
            rule_id=rule.rule_id,
            occurrence_date=target,
            status=OccurrenceStatus.PENDING,
            item_id=inv_item.item_id if inv_item else None,
        )
        session.add(occurrence)
        session.commit()
        return occurrence

    @classmethod
    def mark_occurrence_purchased(
        cls,
        session: Session,
        occurrence_id: str,
        restock_inventory: bool = True,
    ) -> Tuple[PurchaseOccurrence, Optional[InventoryItem]]:
        """US-3.6: Mark a recurring occurrence bought and restock inventory accordingly.
        
        >>> AGENT HOOK / MULTI-DOMAIN HOOK:
        >>> When a receipt photo is parsed (US-4.1), the Expense Agent or
        >>> Inventory Agent can call this to mark commodities fulfilled
        >>> and link the expense cost simultaneously.
        """
        occurrence = (
            session.query(PurchaseOccurrence)
            .filter(PurchaseOccurrence.occurrence_id == occurrence_id)
            .first()
        )
        if not occurrence:
            raise ValueError("Purchase occurrence not found")

        occurrence.status = OccurrenceStatus.PURCHASED
        updated_item = None

        if restock_inventory:
            rule = occurrence.rule
            updated_item = cls.add_or_update_stock(
                session=session,
                name=rule.name,
                quantity=float(rule.quantity),
                unit=rule.unit,
                low_stock_threshold=float(rule.low_stock_threshold) if rule.low_stock_threshold else None,
            )
            occurrence.item_id = updated_item.item_id

        session.commit()
        return occurrence, updated_item