"""Food & Inventory domain models (US-3.x).

Inventory items carry a low-stock threshold. Grocery items are the active
shopping list. Commodity rules define recurring purchases (milk, bread) that
generate dated purchase occurrences the household can mark purchased/skipped.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import OccurrenceStatus


class InventoryItem(Base):
    """A stocked household item with an optional low-stock threshold."""

    __tablename__ = "inventory_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    low_stock_threshold: Mapped[Optional[float]] = mapped_column(Numeric(12, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<InventoryItem {self.name} qty={self.quantity}>"


class GroceryItem(Base):
    """A one-off or recipe-derived item on the active grocery list."""

    __tablename__ = "grocery_items"

    grocery_item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(12, 3), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    purchased: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<GroceryItem {self.name} purchased={self.purchased}>"


class CommodityRule(Base):
    """A recurring commodity (e.g. milk daily) that generates occurrences."""

    __tablename__ = "commodity_rules"

    rule_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    preferred_brand: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Simple schedule string, e.g. "DAILY" or "FREQ=WEEKLY;BYDAY=MO".
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    low_stock_threshold: Mapped[Optional[float]] = mapped_column(Numeric(12, 3), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    occurrences: Mapped[list["PurchaseOccurrence"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class PurchaseOccurrence(Base):
    """A dated occurrence generated from a commodity rule.

    Unique on ``(rule_id, occurrence_date)`` so the scheduler is idempotent
    and cannot create duplicate occurrences for the same day.
    """

    __tablename__ = "purchase_occurrences"
    __table_args__ = (
        UniqueConstraint("rule_id", "occurrence_date", name="uq_occurrence_rule_date"),
    )

    occurrence_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("commodity_rules.rule_id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurrence_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(OccurrenceStatus, native_enum=False, length=12),
        nullable=False,
        default=OccurrenceStatus.PENDING,
    )
    # Optional link to the inventory item this purchase restocks.
    item_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("inventory_items.item_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rule: Mapped["CommodityRule"] = relationship(back_populates="occurrences")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<PurchaseOccurrence {self.occurrence_date} {self.status.value}>"
