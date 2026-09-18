"""REST routes for Finance, Expense Tracking, and Monthly Budgets."""
from __future__ import annotations

from datetime import date
from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required, require_role
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole
from app.services.finance import FinanceService

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")


# -----------------------------------------------------------------------------
# RBAC Enforcement Guard (US-4.4, US-1.6, US-1.7)
# -----------------------------------------------------------------------------
@finance_bp.before_request
@login_required
def enforce_finance_privacy():
    """Block Child and Guest roles before reaching any financial data."""
    if g.current_role not in [HouseholdRole.ADMIN, HouseholdRole.ADULT]:
        return jsonify({"error": "Forbidden: Financial records are restricted to Adult and Admin members"}), 403


# -----------------------------------------------------------------------------
# Expense Endpoints
# -----------------------------------------------------------------------------

@finance_bp.route("/expenses", methods=["GET"])
def get_expenses():
    """Retrieve logged expenses with optional filtering."""
    category = request.args.get("category")
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    session = SessionLocal()
    try:
        expenses = FinanceService.list_expenses(session, category=category, month=month, year=year)
        return jsonify([
            {
                "expense_id": exp.expense_id,
                "amount_cents": exp.amount_cents,
                "category": exp.category,
                "description": exp.description,
                "payment_date": exp.payment_date.isoformat(),
                "paid_by": exp.paid_by,
            }
            for exp in expenses
        ]), 200
    finally:
        session.close()


@finance_bp.route("/expenses", methods=["POST"])
def log_expense():
    """Log an expense entry manually."""
    data = request.get_json() or {}
    amount_cents = data.get("amount_cents")
    category = data.get("category")

    if amount_cents is None or not category:
        return jsonify({"error": "amount_cents and category are required"}), 400

    payment_date = date.fromisoformat(data["payment_date"]) if data.get("payment_date") else None

    session = SessionLocal()
    try:
        expense = FinanceService.log_expense(
            session=session,
            amount_cents=int(amount_cents),
            category=category,
            paid_by_id=g.current_user.user_id,
            description=data.get("description"),
            payment_date=payment_date,
        )
        return jsonify({
            "expense_id": expense.expense_id,
            "amount_cents": expense.amount_cents,
            "category": expense.category,
            "payment_date": expense.payment_date.isoformat(),
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Budget Endpoints (US-4.2)
# -----------------------------------------------------------------------------

@finance_bp.route("/budgets", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def set_budget():
    """Set or update a monthly category budget (Admin only)."""
    data = request.get_json() or {}
    category = data.get("category")
    month = data.get("month")
    year = data.get("year")
    limit_cents = data.get("limit_cents")

    if not all([category, month, year, limit_cents is not None]):
        return jsonify({"error": "category, month, year, and limit_cents are required"}), 400

    session = SessionLocal()
    try:
        budget = FinanceService.set_budget(
            session=session,
            category=category,
            month=int(month),
            year=int(year),
            limit_cents=int(limit_cents),
        )
        return jsonify({
            "budget_id": budget.budget_id,
            "category": budget.category,
            "limit_cents": budget.limit_cents,
            "month": budget.month,
            "year": budget.year,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/budgets/status", methods=["GET"])
def check_budget_status():
    """US-4.2: Query remaining balance for a category and month."""
    category = request.args.get("category")
    today = date.today()
    month = request.args.get("month", default=today.month, type=int)
    year = request.args.get("year", default=today.year, type=int)

    if not category:
        return jsonify({"error": "category query parameter is required"}), 400

    session = SessionLocal()
    try:
        status = FinanceService.get_budget_status(session, category=category, month=month, year=year)
        return jsonify(status), 200
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Recurring Bills Endpoints (US-4.3)
# -----------------------------------------------------------------------------

@finance_bp.route("/bills", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def create_bill():
    """Register a new recurring bill (Admin only)."""
    data = request.get_json() or {}
    name = data.get("name")
    amount_cents = data.get("amount_cents")
    due_day = data.get("due_day_of_month")

    if not all([name, amount_cents is not None, due_day is not None]):
        return jsonify({"error": "name, amount_cents, and due_day_of_month are required"}), 400

    session = SessionLocal()
    try:
        bill = FinanceService.create_recurring_bill(
            session=session,
            name=name,
            amount_cents=int(amount_cents),
            due_day_of_month=int(due_day),
            category=data.get("category"),
        )
        return jsonify({
            "bill_id": bill.bill_id,
            "name": bill.name,
            "amount_cents": bill.amount_cents,
            "due_day_of_month": bill.due_day_of_month,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/bills/upcoming", methods=["GET"])
def upcoming_bills():
    """US-4.3: View bills due within the next N days (default 7)."""
    days = request.args.get("days", default=7, type=int)
    session = SessionLocal()
    try:
        bills = FinanceService.get_upcoming_bills(session, days_ahead=days)
        return jsonify(bills), 200
    finally:
        session.close()