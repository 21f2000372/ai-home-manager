"""Finance domain tools."""
from __future__ import annotations

from datetime import date, datetime

from langchain_core.tools import tool

from app.ai.agents.request_context import (
    AgentRequestContextError,
    get_agent_request_identity,
)
from app.db.base import SessionLocal
from app.models.enums import BudgetPeriod
from app.models.finance import Budget, Expense, RecurringBill
from typing import Optional

def _parse_datetime(value: str, field_name: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid {field_name}. Use an ISO datetime."
        )


def _authenticated_user_id() -> str:
    """Return the server-verified user id for this agent invocation."""
    identity = get_agent_request_identity()
    return identity.user_id


# ============================================================
# EXPENSE CRUD
# ============================================================

@tool
def log_expense(
    amount_minor: int,
    currency: str,
    category: str,
    description: str = "",
    occurred_at: str = "",
    document_id: str = "",
) -> str:
    """Record a household expense. Money uses integer minor units."""
    session = SessionLocal()

    try:
        try:
            parsed_occurred = (
                _parse_datetime(occurred_at, "occurred_at")
                if occurred_at
                else datetime.now().astimezone()
            )
        except ValueError as exc:
            return str(exc)

        try:
            recorded_by = _authenticated_user_id()
        except AgentRequestContextError as exc:
            return str(exc)

        expense = Expense(
            amount_minor=amount_minor,
            currency=currency.upper(),
            category=category,
            description=description or None,
            occurred_at=parsed_occurred,
            recorded_by=recorded_by,
            document_id=document_id or None,
        )

        session.add(expense)
        session.commit()
        session.refresh(expense)

        return (
            f"Logged {amount_minor / 100:.2f} "
            f"{currency.upper()} under '{category}' "
            f"(id={expense.expense_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to log expense: {exc}"

    finally:
        session.close()


@tool
def list_expenses(
    category: str = "",
    scope: str = "mine",
) -> str:
    """List recent expenses.

    scope='mine' filters by the authenticated user's recorded_by value.
    scope='household' returns household-wide expenses. Use household scope
    only when the user explicitly asks for all/household expenses.
    """
    session = SessionLocal()

    try:
        query = session.query(Expense)

        normalized_scope = (
            scope or "mine"
        ).strip().casefold()

        if normalized_scope in {
            "mine",
            "my",
            "self",
        }:
            try:
                current_user_id = (
                    _authenticated_user_id()
                )
            except AgentRequestContextError as exc:
                return str(exc)

            query = query.filter(
                Expense.recorded_by
                == current_user_id
            )
            heading = "Here are your recent expenses:"

        elif normalized_scope in {
            "household",
            "all",
        }:
            heading = (
                "Here are the household's recent expenses:"
            )

        else:
            return (
                "Invalid scope. Use 'mine' or 'household'."
            )

        if category:
            query = query.filter(
                Expense.category == category
            )

        rows = (
            query
            .order_by(
                Expense.occurred_at.desc()
            )
            .limit(20)
            .all()
        )

        if not rows:
            return (
                "No household expenses found."
                if normalized_scope
                in {"household", "all"}
                else "No expenses found for you."
            )

        lines = [
            f"- {e.occurred_at.date()}: "
            f"{e.amount_minor / 100:.2f} {e.currency} "
            f"({e.category}) "
            f"(id={e.expense_id})"
            for e in rows
        ]

        return "\n".join(
            [heading] + lines
        )

    finally:
        session.close()


@tool
def get_expense(expense_id: str) -> str:
    """Get one expense by id."""
    session = SessionLocal()

    try:
        expense = session.get(Expense, expense_id)

        if not expense:
            return f"No expense found with id {expense_id}."

        return (
            f"Expense: {expense.amount_minor / 100:.2f} "
            f"{expense.currency}; "
            f"category: {expense.category}; "
            f"description: {expense.description or 'none'}; "
            f"occurred_at: {expense.occurred_at.isoformat()}; "
            f"id: {expense.expense_id}"
        )

    finally:
        session.close()


@tool
def update_expense(
    expense_id: str,
    amount_minor: Optional[int] = None ,
    currency: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    occurred_at: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    """Update an existing expense."""
    session = SessionLocal()

    try:
        expense = session.get(Expense, expense_id)

        if not expense:
            return f"No expense found with id {expense_id}."

        changed = []

        if amount_minor is not None:
            expense.amount_minor = amount_minor
            changed.append(f"amount_minor={amount_minor}")

        if currency is not None:
            expense.currency = currency.upper()
            changed.append(f"currency={currency.upper()}")

        if category is not None:
            expense.category = category
            changed.append(f"category='{category}'")

        if description is not None:
            expense.description = description or None
            changed.append("description updated")

        if occurred_at is not None:
            try:
                expense.occurred_at = _parse_datetime(
                    occurred_at,
                    "occurred_at",
                )
            except ValueError as exc:
                return str(exc)

            changed.append(f"occurred_at={occurred_at}")

        if document_id is not None:
            expense.document_id = document_id or None
            changed.append("document_id updated")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated expense ({expense.expense_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update expense: {exc}"

    finally:
        session.close()


@tool
def delete_expense(expense_id: str) -> str:
    """Delete an expense."""
    session = SessionLocal()

    try:
        expense = session.get(Expense, expense_id)

        if not expense:
            return f"No expense found with id {expense_id}."

        session.delete(expense)
        session.commit()

        return f"Deleted expense (id={expense_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete expense: {exc}"

    finally:
        session.close()


# ============================================================
# BUDGET CRUD
# ============================================================

@tool
def create_budget(
    category: str,
    limit_minor: int,
    currency: str,
    period: str = "Monthly",
    period_start: str = "",
    period_end: str = "",
) -> str:
    """Create a spending budget."""
    session = SessionLocal()

    try:
        try:
            parsed_period = BudgetPeriod(period)
        except ValueError:
            return (
                f"Invalid period '{period}'. "
                "Use Monthly, Weekly, or Custom."
            )

        start = (
            date.fromisoformat(period_start)
            if period_start
            else None
        )

        end = (
            date.fromisoformat(period_end)
            if period_end
            else None
        )

        budget = Budget(
            category=category,
            limit_minor=limit_minor,
            currency=currency.upper(),
            period=parsed_period,
            period_start=start,
            period_end=end,
        )

        session.add(budget)
        session.commit()
        session.refresh(budget)

        return (
            f"Budget created for {category}: "
            f"{limit_minor / 100:.2f} {currency.upper()}/"
            f"{parsed_period.value} "
            f"(id={budget.budget_id})."
        )

    except ValueError:
        return "Invalid budget date. Use YYYY-MM-DD."

    except Exception as exc:
        session.rollback()
        return f"Failed to create budget: {exc}"

    finally:
        session.close()


@tool
def list_budgets() -> str:
    """List budgets."""
    session = SessionLocal()

    try:
        rows = (
            session.query(Budget)
            .order_by(Budget.created_at.desc())
            .all()
        )

        if not rows:
            return "No budgets found."

        return "\n".join(
            f"- {b.category}: "
            f"{b.limit_minor / 100:.2f} {b.currency}/"
            f"{b.period.value} "
            f"(id={b.budget_id})"
            for b in rows
        )

    finally:
        session.close()


@tool
def get_budget(budget_id: str) -> str:
    """Get one budget by id."""
    session = SessionLocal()

    try:
        budget = session.get(Budget, budget_id)

        if not budget:
            return f"No budget found with id {budget_id}."

        return (
            f"Budget: {budget.category}; "
            f"limit: {budget.limit_minor / 100:.2f} "
            f"{budget.currency}; "
            f"period: {budget.period.value}; "
            f"id: {budget.budget_id}"
        )

    finally:
        session.close()


@tool
def update_budget(
    budget_id: str,
    category: Optional[str] = None,
    limit_minor: Optional[int] = None,
    currency: Optional[str] = None,
    period: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> str:
    """Update an existing budget."""
    session = SessionLocal()

    try:
        budget = session.get(Budget, budget_id)

        if not budget:
            return f"No budget found with id {budget_id}."

        changed = []

        if category is not None:
            budget.category = category
            changed.append(f"category='{category}'")

        if limit_minor is not None:
            budget.limit_minor = limit_minor
            changed.append(f"limit_minor={limit_minor}")

        if currency is not None:
            budget.currency = currency.upper()
            changed.append(f"currency={currency.upper()}")

        if period is not None:
            try:
                budget.period = BudgetPeriod(period)
            except ValueError:
                return (
                    f"Invalid period '{period}'. "
                    "Use Monthly, Weekly, or Custom."
                )

            changed.append(f"period={period}")

        if period_start is not None:
            try:
                budget.period_start = (
                    date.fromisoformat(period_start)
                    if period_start
                    else None
                )
            except ValueError:
                return "Invalid period_start. Use YYYY-MM-DD."

            changed.append(f"period_start={period_start}")

        if period_end is not None:
            try:
                budget.period_end = (
                    date.fromisoformat(period_end)
                    if period_end
                    else None
                )
            except ValueError:
                return "Invalid period_end. Use YYYY-MM-DD."

            changed.append(f"period_end={period_end}")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated budget ({budget.budget_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update budget: {exc}"

    finally:
        session.close()


@tool
def delete_budget(budget_id: str) -> str:
    """Delete a budget."""
    session = SessionLocal()

    try:
        budget = session.get(Budget, budget_id)

        if not budget:
            return f"No budget found with id {budget_id}."

        session.delete(budget)
        session.commit()

        return f"Deleted budget (id={budget_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete budget: {exc}"

    finally:
        session.close()


# ============================================================
# RECURRING BILL CRUD
# ============================================================

@tool
def create_recurring_bill(
    payee: str,
    due_at: str,
    expected_amount_minor: Optional[int] = None,
    currency: str = "USD",
    category: str = "",
    recurrence: str = "MONTHLY",
) -> str:
    """Create a recurring bill."""
    session = SessionLocal()

    try:
        try:
            parsed_due = datetime.fromisoformat(due_at)
        except ValueError:
            return "Invalid due_at. Use an ISO datetime."

        bill = RecurringBill(
            payee=payee,
            expected_amount_minor=expected_amount_minor,
            currency=currency.upper(),
            category=category or None,
            due_at=parsed_due,
            recurrence=recurrence,
        )

        session.add(bill)
        session.commit()
        session.refresh(bill)

        return (
            f"Created recurring bill for '{payee}' "
            f"(id={bill.bill_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to create recurring bill: {exc}"

    finally:
        session.close()


@tool
def list_recurring_bills() -> str:
    """List recurring bills."""
    session = SessionLocal()

    try:
        rows = (
            session.query(RecurringBill)
            .order_by(RecurringBill.due_at.asc())
            .all()
        )

        if not rows:
            return "No recurring bills found."

        return "\n".join(
            f"- {b.payee}: "
            f"due={b.due_at.isoformat()}, "
            f"recurrence={b.recurrence} "
            f"(id={b.bill_id})"
            for b in rows
        )

    finally:
        session.close()


@tool
def get_recurring_bill(bill_id: str) -> str:
    """Get one recurring bill."""
    session = SessionLocal()

    try:
        bill = session.get(RecurringBill, bill_id)

        if not bill:
            return f"No recurring bill found with id {bill_id}."

        return (
            f"Recurring bill: {bill.payee}; "
            f"due_at: {bill.due_at.isoformat()}; "
            f"recurrence: {bill.recurrence}; "
            f"category: {bill.category or 'none'}; "
            f"id: {bill.bill_id}"
        )

    finally:
        session.close()


@tool
def update_recurring_bill(
    bill_id: str,
    payee: Optional[str] = None,
    due_at: Optional[str] = None,
    expected_amount_minor: Optional[int] = None,
    currency: Optional[str] = None,
    category: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> str:
    """Update a recurring bill."""
    session = SessionLocal()

    try:
        bill = session.get(RecurringBill, bill_id)

        if not bill:
            return f"No recurring bill found with id {bill_id}."

        changed = []

        if payee is not None:
            bill.payee = payee
            changed.append(f"payee='{payee}'")

        if due_at is not None:
            try:
                bill.due_at = datetime.fromisoformat(due_at)
            except ValueError:
                return "Invalid due_at. Use an ISO datetime."

            changed.append(f"due_at={due_at}")

        if expected_amount_minor is not None:
            bill.expected_amount_minor = expected_amount_minor
            changed.append(
                f"expected_amount_minor={expected_amount_minor}"
            )

        if currency is not None:
            bill.currency = currency.upper()
            changed.append(f"currency={currency.upper()}")

        if category is not None:
            bill.category = category or None
            changed.append("category updated")

        if recurrence is not None:
            bill.recurrence = recurrence
            changed.append(f"recurrence={recurrence}")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated recurring bill ({bill.bill_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update recurring bill: {exc}"

    finally:
        session.close()


@tool
def delete_recurring_bill(bill_id: str) -> str:
    """Delete a recurring bill."""
    session = SessionLocal()

    try:
        bill = session.get(RecurringBill, bill_id)

        if not bill:
            return f"No recurring bill found with id {bill_id}."

        session.delete(bill)
        session.commit()

        return f"Deleted recurring bill (id={bill_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete recurring bill: {exc}"

    finally:
        session.close()


TOOLS = [
    log_expense,
    list_expenses,
    get_expense,
    update_expense,
    delete_expense,

    create_budget,
    list_budgets,
    get_budget,
    update_budget,
    delete_budget,

    create_recurring_bill,
    list_recurring_bills,
    get_recurring_bill,
    update_recurring_bill,
    delete_recurring_bill,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}