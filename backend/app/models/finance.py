"""Finance & Budgeting domain models (US-4.x).

Simple 3-table MVP model (expenses, budgets, recurring_bills) that matches the
relational schema doc and the user stories: log expenses (optionally from a
receipt document), check budget status, and get bill reminders.

Money is stored as integer minor units (cents) plus an ISO currency code to
avoid binary floating-point rounding errors on amounts.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import BudgetPeriod


class Expense(Base):
    """A recorded expense. May be linked to a source document (receipt)."""

    __tablename__ = "expenses"

    expense_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    recorded_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    # Optional link to the receipt/bill document this expense came from.
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.document_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Expense {self.category} {self.amount_minor}{self.currency}>"


class Budget(Base):
    """A per-category spending plan for a period (US-4.2)."""

    __tablename__ = "budgets"

    budget_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    period: Mapped[BudgetPeriod] = mapped_column(
        Enum(BudgetPeriod, native_enum=False, length=10),
        nullable=False,
        default=BudgetPeriod.MONTHLY,
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Budget {self.category} {self.limit_minor}{self.currency}/{self.period.value}>"


class RecurringBill(Base):
    """A recurring bill/obligation used for due-date reminders (US-4.3)."""

    __tablename__ = "recurring_bills"

    bill_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    payee: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_amount_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Simple recurrence string, e.g. "MONTHLY".
    recurrence: Mapped[str] = mapped_column(String(60), nullable=False, default="MONTHLY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<RecurringBill {self.payee} due={self.due_at}>"
