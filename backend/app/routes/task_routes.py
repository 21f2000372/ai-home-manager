"""REST routes for Tasks and Calendar events."""
from __future__ import annotations

from datetime import datetime
from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole, Priority, TaskStatus
from app.services.tasks import CalendarService, TaskService

task_bp = Blueprint("tasks", __name__, url_prefix="/api")


def _parse_iso(value):
    """Parse an ISO datetime string, tolerating a trailing 'Z' (UTC).

    Python 3.9's datetime.fromisoformat does not accept the 'Z' suffix that
    JavaScript's toISOString() produces, so normalize it to '+00:00' first.
    Returns None for empty values.
    """
    if not value:
        return None
    if isinstance(value, str) and value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


@task_bp.route("/tasks", methods=["GET"])
@login_required
def get_tasks():
    """US-2.3: Retrieve household tasks. Supports ?assigned_to=me filter."""
    assigned_filter = request.args.get("assigned_to")
    status_filter = request.args.get("status")

    target_user_id = g.current_user.user_id if assigned_filter == "me" else assigned_filter
    parsed_status = TaskStatus(status_filter) if status_filter else None

    session = SessionLocal()
    try:
        tasks = TaskService.list_tasks(session, target_user_id, parsed_status)
        return jsonify([
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "assigned_to": t.assigned_to,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "priority": t.priority.value,
                "status": t.status.value,
            }
            for t in tasks
        ]), 200
    finally:
        session.close()


@task_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    """US-2.2: Create a task manually. Blocked for Guest roles."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    title = data.get("title")
    if not title:
        return jsonify({"error": "Title is required"}), 400

    due_at = _parse_iso(data.get("due_at"))
    priority = Priority(data.get("priority", Priority.NORMAL.value))

    session = SessionLocal()
    try:
        task = TaskService.create_task(
            session=session,
            title=title,
            created_by_id=g.current_user.user_id,
            description=data.get("description"),
            assigned_to_id=data.get("assigned_to"),
            due_at=due_at,
            priority=priority,
        )
        return jsonify({
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status.value,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@task_bp.route("/tasks/<string:task_id>/status", methods=["PATCH"])
@login_required
def update_task_status(task_id: str):
    """Update task lifecycle state.

    A Guest may respond ONLY to a task assigned to them, and only by
    accepting (InProgress) or rejecting (Cancelled) it. This backs the guest
    notification dashboard without granting broader write access.
    """
    data = request.get_json() or {}
    status_str = data.get("status")
    try:
        new_status = TaskStatus(status_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Valid status is required"}), 400

    session = SessionLocal()
    try:
        if g.current_role == HouseholdRole.GUEST:
            # Guests can only accept/reject their own assigned notifications.
            task = TaskService.get_task(session, task_id)
            if task is None:
                return jsonify({"error": "Task not found"}), 404
            if task.assigned_to != g.current_user.user_id:
                return jsonify({"error": "Guest accounts can only respond to their own tasks"}), 403
            if new_status not in (TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED):
                return jsonify({"error": "Guests may only accept or reject a task"}), 403

        task = TaskService.update_task_status(session, task_id, new_status)
        return jsonify({"task_id": task.task_id, "status": task.status.value}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


@task_bp.route("/tasks/<string:task_id>", methods=["PUT"])
@login_required
def update_task(task_id: str):
    """Update editable task details without changing its status."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    title = data.get("title")
    if not title or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    try:
        due_at = _parse_iso(data.get("due_at"))
        priority = Priority(data.get("priority", Priority.NORMAL.value))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid due_at and priority are required"}), 400

    session = SessionLocal()
    try:
        task = TaskService.update_task(
            session=session,
            task_id=task_id,
            title=title,
            description=data.get("description"),
            assigned_to_id=data.get("assigned_to"),
            due_at=due_at,
            priority=priority,
        )
        return jsonify({
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "assigned_to": task.assigned_to,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "priority": task.priority.value,
            "status": task.status.value,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@task_bp.route("/tasks/<string:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id: str):
    """Delete a task. Blocked for Guest accounts."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    session = SessionLocal()
    try:
        TaskService.delete_task(session, task_id)
        return jsonify({"message": "Task deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


@task_bp.route("/calendar", methods=["GET"])
@login_required
def get_calendar():
    """US-2.5: View shared calendar events."""
    session = SessionLocal()
    try:
        events = CalendarService.list_events(session)
        return jsonify([
            {
                "event_id": e.event_id,
                "title": e.title,
                "starts_at": e.starts_at.isoformat(),
                "ends_at": e.ends_at.isoformat(),
                "owner_id": e.owner_id,
            }
            for e in events
        ]), 200
    finally:
        session.close()


@task_bp.route("/calendar", methods=["POST"])
@login_required
def create_calendar_event():
    """US-2.6: Create event and return scheduling conflict warnings."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    title = data.get("title")
    starts_at_raw = data.get("starts_at")
    ends_at_raw = data.get("ends_at")

    if not all([title, starts_at_raw, ends_at_raw]):
        return jsonify({"error": "title, starts_at, and ends_at are required"}), 400

    starts_at = _parse_iso(starts_at_raw)
    ends_at = _parse_iso(ends_at_raw)

    session = SessionLocal()
    try:
        event, conflicts = CalendarService.create_event(
            session=session,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            owner_id=g.current_user.user_id,
        )
        return jsonify({
            "event": {
                "event_id": event.event_id,
                "title": event.title,
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat(),
            },
            "conflicts": [
                {
                    "event_id": c.event_id,
                    "title": c.title,
                    "starts_at": c.starts_at.isoformat(),
                    "ends_at": c.ends_at.isoformat(),
                }
                for c in conflicts
            ],
            "has_conflict": len(conflicts) > 0,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@task_bp.route("/calendar/<string:event_id>", methods=["PUT"])
@login_required
def update_calendar_event(event_id: str):
    """Edit an event with automatic conflict detection."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    data = request.get_json() or {}
    starts_at = _parse_iso(data.get("starts_at"))
    ends_at = _parse_iso(data.get("ends_at"))

    session = SessionLocal()
    try:
        event, conflicts = CalendarService.update_event(
            session=session,
            event_id=event_id,
            title=data.get("title"),
            starts_at=starts_at,
            ends_at=ends_at,
        )
        return jsonify({
            "event": {
                "event_id": event.event_id,
                "title": event.title,
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat(),
            },
            "conflicts": [
                {
                    "event_id": c.event_id,
                    "title": c.title,
                    "starts_at": c.starts_at.isoformat(),
                    "ends_at": c.ends_at.isoformat(),
                }
                for c in conflicts
            ],
            "has_conflict": len(conflicts) > 0,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()



@task_bp.route("/calendar/<string:event_id>", methods=["DELETE"])
@login_required
def delete_calendar_event(event_id: str):
    """Delete a calendar event. Blocked for Guest accounts."""
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "Guest accounts have read-only access"}), 403

    session = SessionLocal()
    try:
        CalendarService.delete_event(session, event_id)
        return jsonify({"message": "Calendar event deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()