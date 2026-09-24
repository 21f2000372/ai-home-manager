"""REST routes for Finance, Expense Tracking, and Monthly Budgets."""
from __future__ import annotations

from datetime import date, datetime
from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required, require_role
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole
from app.services.finance import FinanceService

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")


# -----------------------------------------------------------------------------
# RBAC Enforcement Guard (US-4.4, US-1.6, US-1.7)
# -----------------------------------------------------------------------------
# app/routes/finance_routes.py

@finance_bp.before_request
def enforce_finance_privacy():
    """Allow CORS preflight OPTIONS requests, then enforce JWT and role checks."""
    # 1. Skip preflight CORS checks so the browser receives 200 OK
    if request.method == "OPTIONS":
        return

    # 2. Run authentication manually for other methods (GET, POST, PUT, DELETE)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or malformed Authorization header"}), 401

    token = auth_header.split(" ", 1)[1].strip()
    try:
        from app.auth.jwt import decode_access_token
        from app.models.people import User
        from app.models.enums import MembershipStatus
        payload = decode_access_token(token)
    except Exception:
        return jsonify({"error": "Invalid or expired token"}), 401

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == payload.get("sub")).first()
        if not user or not user.membership:
            return jsonify({"error": "User account or membership not found"}), 401
        if user.membership.status != MembershipStatus.ACTIVE:
            return jsonify({"error": "User membership is pending or suspended"}), 403

        g.current_user = user
        g.current_role = user.membership.role

        # 3. RBAC check: Block Child and Guest from finance domain
        if g.current_role not in [HouseholdRole.ADMIN, HouseholdRole.ADULT]:
            return jsonify({"error": "Forbidden: Financial records are restricted to Adult and Admin members"}), 403
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Expense Endpoints (CRUD)
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
                "amount_minor": exp.amount_minor,
                "currency": exp.currency,
                "category": exp.category,
                "description": exp.description,
                "occurred_at": exp.occurred_at.isoformat(),
                "recorded_by": exp.recorded_by,
                "document_id": exp.document_id,
            }
            for exp in expenses
        ]), 200
    finally:
        session.close()


@finance_bp.route("/expenses/<string:expense_id>", methods=["GET"])
def get_single_expense(expense_id: str):
    """Retrieve a single expense by ID."""
    session = SessionLocal()
    try:
        expense = FinanceService.get_expense(session, expense_id)
        if not expense:
            return jsonify({"error": "Expense not found"}), 404
        return jsonify({
            "expense_id": expense.expense_id,
            "amount_minor": expense.amount_minor,
            "currency": expense.currency,
            "category": expense.category,
            "description": expense.description,
            "occurred_at": expense.occurred_at.isoformat(),
            "recorded_by": expense.recorded_by,
            "document_id": expense.document_id,
        }), 200
    finally:
        session.close()


@finance_bp.route("/expenses", methods=["POST", "OPTIONS"])
def log_expense():
    """Log an expense entry manually."""
    # Handle preflight OPTIONS check
    if request.method == "OPTIONS":
        return ("", 200)

    data = request.get_json() or {}
    amount_minor = data.get("amount_minor")
    category = data.get("category")

    if amount_minor is None or not category:
        return jsonify({"error": "amount_minor and category are required"}), 400

    occurred_at = (
        datetime.fromisoformat(data["occurred_at"])
        if data.get("occurred_at")
        else None
    )

    session = SessionLocal()
    try:
        expense = FinanceService.log_expense(
            session=session,
            amount_minor=int(amount_minor),
            category=category,
            recorded_by_id=g.current_user.user_id,
            description=data.get("description"),
            occurred_at=occurred_at,
            currency=data.get("currency", "USD"),
            document_id=data.get("document_id"),
        )
        return jsonify({
            "expense_id": expense.expense_id,
            "amount_minor": expense.amount_minor,
            "category": expense.category,
            "occurred_at": expense.occurred_at.isoformat(),
            "currency": expense.currency,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/expenses/<string:expense_id>", methods=["PUT"])
def update_expense(expense_id: str):
    """Edit an existing expense."""
    data = request.get_json() or {}
    occurred_at = (
        datetime.fromisoformat(data["occurred_at"])
        if data.get("occurred_at")
        else None
    )

    session = SessionLocal()
    try:
        expense = FinanceService.update_expense(
            session=session,
            expense_id=expense_id,
            amount_minor=int(data["amount_minor"]) if data.get("amount_minor") is not None else None,
            category=data.get("category"),
            description=data.get("description"),
            occurred_at=occurred_at,
            currency=data.get("currency"),
            document_id=data.get("document_id"),
        )
        return jsonify({
            "expense_id": expense.expense_id,
            "amount_minor": expense.amount_minor,
            "category": expense.category,
            "occurred_at": expense.occurred_at.isoformat(),
            "currency": expense.currency,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/expenses/<string:expense_id>", methods=["DELETE"])
def delete_expense(expense_id: str):
    """Delete an expense."""
    session = SessionLocal()
    try:
        FinanceService.delete_expense(session, expense_id)
        return jsonify({"message": "Expense deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Budget Endpoints (CRUD + US-4.2)
# -----------------------------------------------------------------------------

@finance_bp.route("/budgets", methods=["GET"])
def get_budgets():
    """List all category budgets."""
    session = SessionLocal()
    try:
        budgets = FinanceService.list_budgets(session)
        return jsonify([
            {
                "budget_id": b.budget_id,
                "category": b.category,
                "limit_minor": b.limit_minor,
                "currency": b.currency,
                "period": b.period.value,
                "period_start": b.period_start.isoformat() if b.period_start else None,
                "period_end": b.period_end.isoformat() if b.period_end else None,
            }
            for b in budgets
        ]), 200
    finally:
        session.close()


@finance_bp.route("/budgets", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def set_budget():
    """Set or update a monthly category budget (Admin only)."""
    data = request.get_json() or {}
    category = data.get("category")
    month = data.get("month")
    year = data.get("year")
    limit_minor = data.get("limit_minor")

    if not all([category, month, year, limit_minor is not None]):
        return jsonify({"error": "category, month, year, and limit_minor are required"}), 400

    session = SessionLocal()
    try:
        budget = FinanceService.set_budget(
            session=session,
            category=category,
            limit_minor=int(limit_minor),
            month=int(month),
            year=int(year),
            currency=data.get("currency", "USD"),
        )
        return jsonify({
            "budget_id": budget.budget_id,
            "category": budget.category,
            "limit_minor": budget.limit_minor,
            "period_start": budget.period_start.isoformat() if budget.period_start else None,
            "period_end": budget.period_end.isoformat() if budget.period_end else None,
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


@finance_bp.route("/budgets/<string:budget_id>", methods=["DELETE"])
@require_role(HouseholdRole.ADMIN)
def delete_budget(budget_id: str):
    """Delete a budget limit (Admin only)."""
    session = SessionLocal()
    try:
        FinanceService.delete_budget(session, budget_id)
        return jsonify({"message": "Budget deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Recurring Bills Endpoints (CRUD + US-4.3)
# -----------------------------------------------------------------------------

@finance_bp.route("/bills", methods=["GET"])
def get_bills():
    """List all registered recurring bills."""
    session = SessionLocal()
    try:
        bills = FinanceService.list_recurring_bills(session)
        return jsonify([
            {
                "bill_id": b.bill_id,
                "payee": b.payee,
                "expected_amount_minor": b.expected_amount_minor,
                "currency": b.currency,
                "category": b.category,
                "due_at": b.due_at.isoformat(),
                "recurrence": b.recurrence,
            }
            for b in bills
        ]), 200
    finally:
        session.close()


@finance_bp.route("/bills/<string:bill_id>", methods=["GET"])
def get_single_bill(bill_id: str):
    """Retrieve a single bill by ID."""
    session = SessionLocal()
    try:
        bill = FinanceService.get_recurring_bill(session, bill_id)
        if not bill:
            return jsonify({"error": "Recurring bill not found"}), 404
        return jsonify({
            "bill_id": bill.bill_id,
            "payee": bill.payee,
            "expected_amount_minor": bill.expected_amount_minor,
            "currency": bill.currency,
            "category": bill.category,
            "due_at": bill.due_at.isoformat(),
            "recurrence": bill.recurrence,
        }), 200
    finally:
        session.close()


@finance_bp.route("/bills", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def create_bill():
    """Register a new recurring bill (Admin only)."""
    data = request.get_json() or {}
    payee = data.get("payee")
    expected_amount_minor = data.get("expected_amount_minor")
    due_at_raw = data.get("due_at")

    if not all([payee, expected_amount_minor is not None, due_at_raw]):
        return jsonify({"error": "payee, expected_amount_minor, and due_at are required"}), 400

    try:
        due_at = datetime.fromisoformat(due_at_raw)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid ISO format for due_at"}), 400

    session = SessionLocal()
    try:
        bill = FinanceService.create_recurring_bill(
            session=session,
            payee=payee,
            expected_amount_minor=int(expected_amount_minor),
            due_at=due_at,
            category=data.get("category"),
            recurrence=data.get("recurrence", "MONTHLY"),
            currency=data.get("currency", "USD"),
        )
        return jsonify({
            "bill_id": bill.bill_id,
            "payee": bill.payee,
            "expected_amount_minor": bill.expected_amount_minor,
            "due_at": bill.due_at.isoformat(),
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/bills/<string:bill_id>", methods=["PUT"])
@require_role(HouseholdRole.ADMIN)
def update_bill(bill_id: str):
    """Edit a recurring bill (Admin only)."""
    data = request.get_json() or {}
    due_at = datetime.fromisoformat(data["due_at"]) if data.get("due_at") else None

    session = SessionLocal()
    try:
        bill = FinanceService.update_recurring_bill(
            session=session,
            bill_id=bill_id,
            payee=data.get("payee"),
            expected_amount_minor=int(data["expected_amount_minor"]) if data.get("expected_amount_minor") is not None else None,
            due_at=due_at,
            category=data.get("category"),
            recurrence=data.get("recurrence"),
            currency=data.get("currency"),
        )
        return jsonify({
            "bill_id": bill.bill_id,
            "payee": bill.payee,
            "expected_amount_minor": bill.expected_amount_minor,
            "due_at": bill.due_at.isoformat(),
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@finance_bp.route("/bills/<string:bill_id>", methods=["DELETE"])
@require_role(HouseholdRole.ADMIN)
def delete_bill(bill_id: str):
    """Delete a recurring bill (Admin only)."""
    session = SessionLocal()
    try:
        FinanceService.delete_recurring_bill(session, bill_id)
        return jsonify({"message": "Recurring bill deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
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