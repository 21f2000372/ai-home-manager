"""Service layer for household expenses, category budgets, and recurring bills."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.finance import Budget, Expense, RecurringBill


class FinanceService:
    # -------------------------------------------------------------------------
    # Expenses (US-4.1, US-4.4)
    # -------------------------------------------------------------------------

    @staticmethod
    def log_expense(
        session: Session,
        amount_cents: int,
        category: str,
        paid_by_id: str,
        description: Optional[str] = None,
        payment_date: Optional[date] = None,
    ) -> Expense:
        """Log an out-of-pocket or household expense.
        
        >>> AGENT HOOK:
        >>> US-4.1: The Expense Agent / Document OCR pipeline calls this method
        >>> after parsing uploaded receipts and links the generated document_id.
        """
        if amount_cents <= 0:
            raise ValueError("Expense amount must be greater than zero")

        expense = Expense(
            amount_cents=amount_cents,
            category=category.strip(),
            paid_by=paid_by_id,
            description=description.strip() if description else None,
            payment_date=payment_date or date.today(),
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
            query = query.filter(extract("month", Expense.payment_date) == month)
        if year:
            query = query.filter(extract("year", Expense.payment_date) == year)
        return query.order_by(Expense.payment_date.desc()).all()

    # -------------------------------------------------------------------------
    # Budgets & Spending Balance Check (US-4.2)
    # -------------------------------------------------------------------------

    @staticmethod
    def set_budget(
        session: Session,
        category: str,
        month: int,
        year: int,
        limit_cents: int,
    ) -> Budget:
        """Define or update a monthly category budget limit (Admin only)."""
        if limit_cents < 0:
            raise ValueError("Budget limit cannot be negative")

        budget = (
            session.query(Budget)
            .filter(
                Budget.category.ilike(category.strip()),
                Budget.month == month,
                Budget.year == year,
            )
            .first()
        )
        if budget:
            budget.limit_cents = limit_cents
        else:
            budget = Budget(
                category=category.strip(),
                month=month,
                year=year,
                limit_cents=limit_cents,
            )
            session.add(budget)

        session.commit()
        return budget

    @classmethod
    def get_budget_status(
        cls,
        session: Session,
        category: str,
        month: int,
        year: int,
    ) -> Dict[str, Any]:
        """Calculate spent vs. limit to determine remaining balance (US-4.2).
        
        >>> AGENT HOOK:
        >>> US-4.2: The Expense Agent calls this directly when responding to:
        >>> "How much is left in the groceries budget this month?"
        >>> US-6.2: The Orchestrator calls this for cross-domain feasibility questions.
        """
        budget = (
            session.query(Budget)
            .filter(
                Budget.category.ilike(category.strip()),
                Budget.month == month,
                Budget.year == year,
            )
            .first()
        )

        spent_cents = (
            session.query(func.coalesce(func.sum(Expense.amount_cents), 0))
            .filter(
                Expense.category.ilike(category.strip()),
                extract("month", Expense.payment_date) == month,
                extract("year", Expense.payment_date) == year,
            )
            .scalar()
        )

        limit_cents = budget.limit_cents if budget else 0
        remaining_cents = limit_cents - spent_cents

        return {
            "category": category,
            "month": month,
            "year": year,
            "limit_cents": limit_cents,
            "spent_cents": spent_cents,
            "remaining_cents": remaining_cents,
            "has_budget": budget is not None,
            "is_exceeded": remaining_cents < 0,
        }

    # -------------------------------------------------------------------------
    # Recurring Bills (US-4.3)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_recurring_bill(
        session: Session,
        name: str,
        amount_cents: int,
        due_day_of_month: int,
        category: Optional[str] = None,
    ) -> RecurringBill:
        """Register a monthly recurring bill (e.g., Rent, Utilities, Wi-Fi)."""
        if not (1 <= due_day_of_month <= 31):
            raise ValueError("due_day_of_month must be between 1 and 31")

        bill = RecurringBill(
            name=name.strip(),
            amount_cents=amount_cents,
            due_day_of_month=due_day_of_month,
            category=category.strip() if category else None,
            active=True,
        )
        session.add(bill)
        session.commit()
        return bill

    @staticmethod
    def get_upcoming_bills(
        session: Session,
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """US-4.3: Find active bills due within the upcoming window.
        
        >>> AGENT HOOK:
        >>> US-4.3: The Expense Agent queries this to issue proactive bill
        >>> alerts before late penalties accrue.
        """
        today = date.today()
        current_day = today.day
        bills = session.query(RecurringBill).filter(RecurringBill.active.is_(True)).all()

        upcoming = []
        for bill in bills:
            # Days until the bill is due this month
            diff = bill.due_day_of_month - current_day
            if 0 <= diff <= days_ahead:
                upcoming.append({
                    "bill_id": bill.bill_id,
                    "name": bill.name,
                    "amount_cents": bill.amount_cents,
                    "due_day_of_month": bill.due_day_of_month,
                    "days_remaining": diff,
                    "category": bill.category,
                })

        return sorted(upcoming, key=lambda x: x["days_remaining"])