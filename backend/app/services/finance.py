"""Service layer for household expenses, category budgets, and recurring bills."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.enums import BudgetPeriod
from app.models.finance import Budget, Expense, RecurringBill


class FinanceService:
    # -------------------------------------------------------------------------
    # Expenses (US-4.1, US-4.4)
    # -------------------------------------------------------------------------

    @staticmethod
    def log_expense(
        session: Session,
        amount_minor: int,
        category: str,
        recorded_by_id: str,
        description: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        currency: str = "USD",
        document_id: Optional[str] = None,
    ) -> Expense:
        """Create a household expense record."""
        if amount_minor <= 0:
            raise ValueError("Expense amount must be greater than zero")

        expense = Expense(
            amount_minor=amount_minor,
            currency=currency.upper(),
            category=category.strip(),
            recorded_by=recorded_by_id,
            description=description.strip() if description else None,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            document_id=document_id,
        )
        session.add(expense)
        session.commit()
        return expense

    @staticmethod
    def list_expenses(
        session: Session,
        category: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[Expense]:
        """Fetch logged expenses with optional category and date filtering."""
        query = session.query(Expense)
        if category:
            query = query.filter(Expense.category.ilike(category.strip()))
        if month:
            query = query.filter(extract("month", Expense.occurred_at) == month)
        if year:
            query = query.filter(extract("year", Expense.occurred_at) == year)
        return query.order_by(Expense.occurred_at.desc()).all()

    @staticmethod
    def get_expense(session: Session, expense_id: str) -> Optional[Expense]:
        """Fetch a single expense by ID."""
        return session.query(Expense).filter(Expense.expense_id == expense_id).first()

    @staticmethod
    def update_expense(
        session: Session,
        expense_id: str,
        amount_minor: Optional[int] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        currency: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Expense:
        """Update fields on an existing expense."""
        expense = session.query(Expense).filter(Expense.expense_id == expense_id).first()
        if not expense:
            raise ValueError("Expense not found")
        if amount_minor is not None:
            if amount_minor <= 0:
                raise ValueError("Amount must be greater than zero")
            expense.amount_minor = amount_minor
        if category is not None:
            expense.category = category.strip()
        if description is not None:
            expense.description = description.strip() if description else None
        if occurred_at is not None:
            expense.occurred_at = occurred_at
        if currency is not None:
            expense.currency = currency.upper()
        if document_id is not None:
            expense.document_id = document_id
        session.commit()
        return expense

    @staticmethod
    def delete_expense(session: Session, expense_id: str) -> None:
        """Delete an expense record."""
        expense = session.query(Expense).filter(Expense.expense_id == expense_id).first()
        if not expense:
            raise ValueError("Expense not found")
        session.delete(expense)
        session.commit()

    # -------------------------------------------------------------------------
    # Budgets & Spending Balance Check (US-4.2)
    # -------------------------------------------------------------------------

    @staticmethod
    def set_budget(
        session: Session,
        category: str,
        limit_minor: int,
        month: int,
        year: int,
        currency: str = "USD",
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
    ) -> Budget:
        """Set or update a monthly category budget limit (Admin only)."""
        if limit_minor < 0:
            raise ValueError("Budget limit cannot be negative")

        _, last_day = calendar.monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)

        budget = (
            session.query(Budget)
            .filter(
                Budget.category.ilike(category.strip()),
                Budget.period_start == period_start,
                Budget.period_end == period_end,
            )
            .first()
        )
        if budget:
            budget.limit_minor = limit_minor
            budget.currency = currency.upper()
            budget.period = period
        else:
            budget = Budget(
                category=category.strip(),
                limit_minor=limit_minor,
                currency=currency.upper(),
                period=period,
                period_start=period_start,
                period_end=period_end,
            )
            session.add(budget)

        session.commit()
        return budget

    @staticmethod
    def list_budgets(session: Session) -> List[Budget]:
        """List all category budgets."""
        return session.query(Budget).order_by(Budget.created_at.desc()).all()

    @staticmethod
    def get_budget(session: Session, budget_id: str) -> Optional[Budget]:
        """Fetch a single budget by ID."""
        return session.query(Budget).filter(Budget.budget_id == budget_id).first()

    @classmethod
    def get_budget_status(
        cls,
        session: Session,
        category: str,
        month: int,
        year: int,
    ) -> Dict[str, Any]:
        """Calculate spent vs. limit to determine remaining balance (US-4.2)."""
        _, last_day = calendar.monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)

        budget = (
            session.query(Budget)
            .filter(
                Budget.category.ilike(category.strip()),
                Budget.period_start == period_start,
                Budget.period_end == period_end,
            )
            .first()
        )

        spent_minor = (
            session.query(func.coalesce(func.sum(Expense.amount_minor), 0))
            .filter(
                Expense.category.ilike(category.strip()),
                extract("month", Expense.occurred_at) == month,
                extract("year", Expense.occurred_at) == year,
            )
            .scalar()
        )

        limit_minor = budget.limit_minor if budget else 0
        remaining_minor = limit_minor - spent_minor

        return {
            "category": category,
            "month": month,
            "year": year,
            "limit_minor": limit_minor,
            "spent_minor": spent_minor,
            "remaining_minor": remaining_minor,
            "has_budget": budget is not None,
            "is_exceeded": remaining_minor < 0,
        }

    @staticmethod
    def delete_budget(session: Session, budget_id: str) -> None:
        """Delete a category budget limit."""
        budget = session.query(Budget).filter(Budget.budget_id == budget_id).first()
        if not budget:
            raise ValueError("Budget not found")
        session.delete(budget)
        session.commit()

    # -------------------------------------------------------------------------
    # Recurring Bills (US-4.3)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_recurring_bill(
        session: Session,
        payee: str,
        expected_amount_minor: int,
        due_at: datetime,
        category: Optional[str] = None,
        recurrence: str = "MONTHLY",
        currency: str = "USD",
    ) -> RecurringBill:
        """Register a recurring bill (Admin only)."""
        if expected_amount_minor < 0:
            raise ValueError("Bill amount cannot be negative")

        bill = RecurringBill(
            payee=payee.strip(),
            expected_amount_minor=expected_amount_minor,
            currency=currency.upper(),
            due_at=due_at,
            category=category.strip() if category else None,
            recurrence=recurrence,
        )
        session.add(bill)
        session.commit()
        return bill

    @staticmethod
    def list_recurring_bills(session: Session) -> List[RecurringBill]:
        """List all active recurring bills."""
        return session.query(RecurringBill).order_by(RecurringBill.due_at.asc()).all()

    @staticmethod
    def get_recurring_bill(session: Session, bill_id: str) -> Optional[RecurringBill]:
        """Retrieve a recurring bill by ID."""
        return session.query(RecurringBill).filter(RecurringBill.bill_id == bill_id).first()

    @staticmethod
    def update_recurring_bill(
        session: Session,
        bill_id: str,
        payee: Optional[str] = None,
        expected_amount_minor: Optional[int] = None,
        due_at: Optional[datetime] = None,
        category: Optional[str] = None,
        recurrence: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> RecurringBill:
        """Update recurring bill details."""
        bill = session.query(RecurringBill).filter(RecurringBill.bill_id == bill_id).first()
        if not bill:
            raise ValueError("Recurring bill not found")
        if payee is not None:
            bill.payee = payee.strip()
        if expected_amount_minor is not None:
            if expected_amount_minor < 0:
                raise ValueError("Amount cannot be negative")
            bill.expected_amount_minor = expected_amount_minor
        if due_at is not None:
            bill.due_at = due_at
        if category is not None:
            bill.category = category.strip() if category else None
        if recurrence is not None:
            bill.recurrence = recurrence.strip()
        if currency is not None:
            bill.currency = currency.upper()
        session.commit()
        return bill

    @staticmethod
    def get_upcoming_bills(
        session: Session,
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """US-4.3: Find active bills due within the upcoming window."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        bills = (
            session.query(RecurringBill)
            .filter(
                RecurringBill.due_at >= now,
                RecurringBill.due_at <= cutoff,
            )
            .order_by(RecurringBill.due_at.asc())
            .all()
        )

        upcoming = []
        for bill in bills:
            diff_days = (bill.due_at.date() - now.date()).days
            upcoming.append({
                "bill_id": bill.bill_id,
                "payee": bill.payee,
                "expected_amount_minor": bill.expected_amount_minor,
                "due_at": bill.due_at.isoformat(),
                "days_remaining": diff_days,
                "category": bill.category,
            })

        return upcoming

    @staticmethod
    def delete_recurring_bill(session: Session, bill_id: str) -> None:
        """Delete a recurring bill."""
        bill = session.query(RecurringBill).filter(RecurringBill.bill_id == bill_id).first()
        if not bill:
            raise ValueError("Recurring bill not found")
        session.delete(bill)
        session.commit()