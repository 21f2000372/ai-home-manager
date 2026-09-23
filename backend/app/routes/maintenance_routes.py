"""REST routes for Home & Maintenance: appliances, warranties, issues, and repairs."""
from __future__ import annotations

from datetime import date
from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required, require_role
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole, IssueStatus, Priority
from app.services.maintenance import MaintenanceService

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/api/maintenance")


# -----------------------------------------------------------------------------
# Appliances Endpoints (US-5.1)
# -----------------------------------------------------------------------------

@maintenance_bp.route("/appliances", methods=["GET", "OPTIONS"])
@login_required
def get_appliances():
    """List all tracked appliances."""
    if request.method == "OPTIONS":
        return ("", 200)

    session = SessionLocal()
    try:
        appliances = MaintenanceService.list_appliances(session)
        return jsonify([
            {
                "appliance_id": a.appliance_id,
                "name": a.name,
                "brand": a.brand,
                "model": a.model,
                "purchased_at": a.purchased_at.isoformat() if a.purchased_at else None,
                "warranty_ends_at": a.warranty_ends_at.isoformat() if a.warranty_ends_at else None,
            }
            for a in appliances
        ]), 200
    finally:
        session.close()


@maintenance_bp.route("/appliances/warranties/expiring", methods=["GET", "OPTIONS"])
@login_required
def get_expiring_warranties():
    """US-5.1: Proactively check appliances with expiring warranties."""
    if request.method == "OPTIONS":
        return ("", 200)

    days = request.args.get("days", default=30, type=int)
    session = SessionLocal()
    try:
        expiring = MaintenanceService.get_expiring_warranties(session, days_ahead=days)
        return jsonify(expiring), 200
    finally:
        session.close()


@maintenance_bp.route("/appliances", methods=["POST", "OPTIONS"])
@login_required
def create_appliance():
    """Add a new appliance (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can add appliances"}), 403

    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Appliance name is required"}), 400

    purchased_at = date.fromisoformat(data["purchased_at"]) if data.get("purchased_at") else None
    warranty_ends_at = date.fromisoformat(data["warranty_ends_at"]) if data.get("warranty_ends_at") else None

    session = SessionLocal()
    try:
        appliance = MaintenanceService.add_appliance(
            session=session,
            name=name,
            brand=data.get("brand"),
            model=data.get("model"),
            purchased_at=purchased_at,
            warranty_ends_at=warranty_ends_at,
        )
        return jsonify({
            "appliance_id": appliance.appliance_id,
            "name": appliance.name,
            "brand": appliance.brand,
            "model": appliance.model,
            "warranty_ends_at": appliance.warranty_ends_at.isoformat() if appliance.warranty_ends_at else None,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@maintenance_bp.route("/appliances/<string:appliance_id>", methods=["PUT", "OPTIONS"])
@login_required
def update_appliance(appliance_id: str):
    """Update appliance details (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can update appliances"}), 403

    data = request.get_json() or {}
    purchased_at = date.fromisoformat(data["purchased_at"]) if data.get("purchased_at") else None
    warranty_ends_at = date.fromisoformat(data["warranty_ends_at"]) if data.get("warranty_ends_at") else None

    session = SessionLocal()
    try:
        appliance = MaintenanceService.update_appliance(
            session=session,
            appliance_id=appliance_id,
            name=data.get("name"),
            brand=data.get("brand"),
            model=data.get("model"),
            purchased_at=purchased_at,
            warranty_ends_at=warranty_ends_at,
        )
        return jsonify({
            "appliance_id": appliance.appliance_id,
            "name": appliance.name,
            "brand": appliance.brand,
            "model": appliance.model,
            "warranty_ends_at": appliance.warranty_ends_at.isoformat() if appliance.warranty_ends_at else None,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@maintenance_bp.route("/appliances/<string:appliance_id>", methods=["DELETE", "OPTIONS"])
@login_required
def delete_appliance(appliance_id: str):
    """Delete an appliance (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can delete appliances"}), 403

    session = SessionLocal()
    try:
        MaintenanceService.delete_appliance(session, appliance_id)
        return jsonify({"message": "Appliance deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Maintenance Issues Endpoints (US-5.2)
# -----------------------------------------------------------------------------

@maintenance_bp.route("/issues", methods=["GET", "OPTIONS"])
@login_required
def get_issues():
    """List maintenance issues."""
    if request.method == "OPTIONS":
        return ("", 200)

    status_str = request.args.get("status")
    appliance_id = request.args.get("appliance_id")
    status = IssueStatus(status_str) if status_str else None

    session = SessionLocal()
    try:
        issues = MaintenanceService.list_issues(session, status=status, appliance_id=appliance_id)
        return jsonify([
            {
                "issue_id": i.issue_id,
                "description": i.description,
                "status": i.status.value,
                "priority": i.priority.value,
                "reported_by": i.reported_by,
                "accountable_to": i.accountable_to,
                "appliance_id": i.appliance_id,
                "created_at": i.created_at.isoformat(),
            }
            for i in issues
        ]), 200
    finally:
        session.close()


@maintenance_bp.route("/issues", methods=["POST", "OPTIONS"])
@login_required
def report_issue():
    """Report a maintenance problem (Children, Adults, and Admins allowed; Guests blocked)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    description = data.get("description")
    if not description:
        return jsonify({"error": "Issue description is required"}), 400

    priority = Priority(data.get("priority", Priority.NORMAL.value))

    session = SessionLocal()
    try:
        issue = MaintenanceService.report_issue(
            session=session,
            description=description,
            reported_by_id=g.current_user.user_id,
            priority=priority,
            appliance_id=data.get("appliance_id"),
            accountable_to_id=data.get("accountable_to"),
        )
        return jsonify({
            "issue_id": issue.issue_id,
            "description": issue.description,
            "status": issue.status.value,
            "priority": issue.priority.value,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@maintenance_bp.route("/issues/<string:issue_id>", methods=["PUT", "OPTIONS"])
@login_required
def update_issue(issue_id: str):
    """Update issue status or priority (Children, Adults, and Admins allowed)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    status = IssueStatus(data["status"]) if data.get("status") else None
    priority = Priority(data["priority"]) if data.get("priority") else None

    session = SessionLocal()
    try:
        issue = MaintenanceService.update_issue(
            session=session,
            issue_id=issue_id,
            description=data.get("description"),
            status=status,
            priority=priority,
            accountable_to_id=data.get("accountable_to"),
        )
        return jsonify({
            "issue_id": issue.issue_id,
            "description": issue.description,
            "status": issue.status.value,
            "priority": issue.priority.value,
            "accountable_to": issue.accountable_to,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@maintenance_bp.route("/issues/<string:issue_id>", methods=["DELETE", "OPTIONS"])
@login_required
def delete_issue(issue_id: str):
    """Delete a maintenance issue (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can delete issues"}), 403

    session = SessionLocal()
    try:
        MaintenanceService.delete_issue(session, issue_id)
        return jsonify({"message": "Issue deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Repairs Endpoints (US-5.3)
# -----------------------------------------------------------------------------

@maintenance_bp.route("/repairs", methods=["GET", "OPTIONS"])
@login_required
def get_repairs():
    """List repair history (Adult and Admin only due to cost visibility)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can view repair logs"}), 403

    appliance_id = request.args.get("appliance_id")
    session = SessionLocal()
    try:
        repairs = MaintenanceService.list_repairs(session, appliance_id=appliance_id)
        return jsonify([
            {
                "repair_id": r.repair_id,
                "serviced_at": r.serviced_at.isoformat(),
                "provider": r.provider,
                "cost_minor": r.cost_minor,
                "currency": r.currency,
                "notes": r.notes,
                "appliance_id": r.appliance_id,
                "logged_by": r.logged_by,
            }
            for r in repairs
        ]), 200
    finally:
        session.close()


@maintenance_bp.route("/repairs", methods=["POST", "OPTIONS"])
@login_required
def log_repair():
    """Log a repair (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can log repairs"}), 403

    data = request.get_json() or {}
    serviced_at_raw = data.get("serviced_at")
    if not serviced_at_raw:
        return jsonify({"error": "serviced_at date is required"}), 400

    serviced_at = date.fromisoformat(serviced_at_raw)
    cost_minor = int(data["cost_minor"]) if data.get("cost_minor") is not None else None

    session = SessionLocal()
    try:
        repair = MaintenanceService.log_repair(
            session=session,
            logged_by_id=g.current_user.user_id,
            serviced_at=serviced_at,
            appliance_id=data.get("appliance_id"),
            provider=data.get("provider"),
            cost_minor=cost_minor,
            currency=data.get("currency", "USD"),
            notes=data.get("notes"),
        )
        return jsonify({
            "repair_id": repair.repair_id,
            "serviced_at": repair.serviced_at.isoformat(),
            "provider": repair.provider,
            "cost_minor": repair.cost_minor,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@maintenance_bp.route("/repairs/<string:repair_id>", methods=["DELETE", "OPTIONS"])
@login_required
def delete_repair(repair_id: str):
    """Delete a repair record (Adult and Admin only)."""
    if request.method == "OPTIONS":
        return ("", 200)
    if g.current_role in [HouseholdRole.GUEST, HouseholdRole.CHILD]:
        return jsonify({"error": "Forbidden: Only Adult and Admin can delete repairs"}), 403

    session = SessionLocal()
    try:
        MaintenanceService.delete_repair(session, repair_id)
        return jsonify({"message": "Repair record deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()