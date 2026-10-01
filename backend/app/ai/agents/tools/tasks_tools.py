"""Tasks and calendar domain tools."""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime

from langchain_core.tools import tool

from app.db.base import SessionLocal
from app.models.enums import MembershipStatus, Priority, TaskStatus
from app.models.people import Membership, User
from app.models.tasks import CalendarEvent, Task
from app.services.tasks import TaskService
from typing import Optional

_agent_user_id: ContextVar[str] = ContextVar("agent_user_id", default="")


def set_agent_user_id(user_id: str):
    """Bind the current authenticated user for agent-created task data."""
    return _agent_user_id.set(user_id)


def reset_agent_user_id(token):
    """Restore the previous agent user context after a request."""
    _agent_user_id.reset(token)


def _parse_datetime(value: str, field_name: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid {field_name} '{value}'. "
            "Use an ISO datetime such as 2026-09-19T08:00:00."
        )


def _resolve_task_id(session, task_ref: str) -> Optional[str]:
    """Resolve a full task_id OR a compact reference (id prefix) to a task_id.

    The list output shows a short 'ref' (first 8 chars of the id) for
    readability; this lets follow-up actions accept either the full id or
    that short ref. Returns None if nothing matches, or raises if ambiguous.
    """
    task_ref = (task_ref or "").strip()
    if not task_ref:
        return None
    # Exact full-id match first.
    exact = session.query(Task).filter(Task.task_id == task_ref).first()
    if exact:
        return exact.task_id
    # Otherwise treat it as an id prefix (the compact ref).
    matches = session.query(Task).filter(Task.task_id.like(f"{task_ref}%")).all()
    if len(matches) == 1:
        return matches[0].task_id
    if len(matches) > 1:
        raise ValueError(f"Reference '{task_ref}' matches multiple tasks; use the full id.")
    return None


def _member_names(session, user_ids) -> dict:
    """Map a set of user_ids to display names for readable task output."""
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    rows = session.query(User).filter(User.user_id.in_(ids)).all()
    return {u.user_id: u.display_name for u in rows}


def _friendly_datetime(value) -> str:
    """Render a datetime as a short, human-readable string (e.g. 'Oct 4, 9:30 AM')."""
    if value is None:
        return ""
    try:
        has_time = value.hour or value.minute
        if has_time:
            return value.strftime("%b %-d, %-I:%M %p")
        return value.strftime("%b %-d")
    except (ValueError, AttributeError):
        # Windows strftime does not support %-d / %-I; fall back gracefully.
        try:
            if value.hour or value.minute:
                return value.strftime("%b %d, %I:%M %p").replace(" 0", " ")
            return value.strftime("%b %d").replace(" 0", " ")
        except Exception:
            return str(value)


def _resolve_assignee(session, assignee: str) -> Optional[str]:
    """Resolve a task assignee (a name or user_id) to a household user_id.

    Returns None when no assignee is given. Accepts either an existing
    user_id or a member's display name (case-insensitive, and tolerant of
    extra text like a role suffix, e.g. "Meera" matches "Meera (Adult)").
    Raises ValueError with a clear message when the name matches no active
    member or is ambiguous.
    """
    assignee = (assignee or "").strip()
    if not assignee:
        return None

    # 1. Exact user_id match against an active member.
    exact = (
        session.query(User)
        .join(Membership, Membership.user_id == User.user_id)
        .filter(
            User.user_id == assignee,
            Membership.status == MembershipStatus.ACTIVE,
        )
        .first()
    )
    if exact:
        return exact.user_id

    # 2. Match by display name among active members (forgiving).
    needle = assignee.lower()
    active_members = (
        session.query(User)
        .join(Membership, Membership.user_id == User.user_id)
        .filter(Membership.status == MembershipStatus.ACTIVE)
        .all()
    )

    matches = [
        user
        for user in active_members
        if user.display_name and needle in user.display_name.lower()
    ]

    if len(matches) == 1:
        return matches[0].user_id

    if len(matches) > 1:
        names = ", ".join(user.display_name for user in matches)
        raise ValueError(
            f"'{assignee}' matches more than one household member "
            f"({names}). Please be more specific."
        )

    raise ValueError(
        f"No active household member matches '{assignee}'."
    )


# ============================================================
# TASK CRUD
# ============================================================

@tool
def create_task(
    title: str,
    description: str = "",
    due_at: str = "",
    assigned_to: str = "",
    priority: str = "Normal",
) -> str:
    """Create a household task, optionally with a reminder."""
    session = SessionLocal()

    try:
        try:
            task_priority = Priority(priority)
        except ValueError:
            return (
                f"Invalid priority '{priority}'. "
                "Use Low, Normal, or High."
            )

        try:
            parsed_due_at = _parse_datetime(due_at, "due_at")
        except ValueError as exc:
            return str(exc)

        assigned_to_id = _resolve_assignee(session, assigned_to)
        task = TaskService.create_task(
            session=session,
            title=title,
            description=description or None,
            created_by_id=_agent_user_id.get() or "",
            assigned_to_id=assigned_to_id,
            due_at=parsed_due_at,
            priority=task_priority,
        )

        result = f"Created task '{title}' (id={task.task_id})."

        if parsed_due_at:
            result += f" Due: {parsed_due_at.isoformat()}."

        if assigned_to:
            result += f" Assigned to: {assigned_to_id}."

        return result

    except Exception as exc:
        session.rollback()
        return f"Failed to create task: {exc}"

    finally:
        session.close()


@tool
def list_tasks(status: str = "") -> str:
    """List tasks, optionally filtered by status."""
    session = SessionLocal()

    try:
        query = session.query(Task)

        if status:
            try:
                task_status = TaskStatus(status)
            except ValueError:
                return (
                    f"Invalid status '{status}'. "
                    "Use Open, InProgress, Done, or Cancelled."
                )

            query = query.filter(Task.status == task_status)

        rows = (
            query
            .order_by(Task.created_at.desc())
            .limit(20)
            .all()
        )

        if not rows:
            return "No tasks found."

        # Resolve assignee ids -> names in one query for readable output.
        names = _member_names(session, [t.assigned_to for t in rows])

        # Group tasks by status for a structured, scannable list.
        groups: dict[str, list[str]] = {}
        for task in rows:
            parts = [f"• {task.title}"]
            if task.due_at:
                parts.append(f"due {_friendly_datetime(task.due_at)}")
            if task.assigned_to:
                parts.append(f"assigned to {names.get(task.assigned_to, 'a household member')}")
            # Compact reference (short id) so the user/agent can act on it later.
            line = " — ".join([parts[0]] + parts[1:]) if len(parts) > 1 else parts[0]
            line += f"  (ref {task.task_id[:8]})"
            groups.setdefault(task.status.value, []).append(line)

        # Present statuses in a sensible order.
        order = [TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value,
                 TaskStatus.DONE.value, TaskStatus.CANCELLED.value]
        labels = {
            TaskStatus.OPEN.value: "Open",
            TaskStatus.IN_PROGRESS.value: "In progress",
            TaskStatus.DONE.value: "Done",
            TaskStatus.CANCELLED.value: "Cancelled",
        }

        sections = ["Here are the household tasks:"]
        for status_value in order:
            if groups.get(status_value):
                sections.append(f"\n{labels[status_value]}")
                sections.extend(groups[status_value])

        return "\n".join(sections)

    finally:
        session.close()


@tool
def get_task(task_id: str) -> str:
    """Get one task by its id or compact reference."""
    session = SessionLocal()

    try:
        resolved_id = _resolve_task_id(session, task_id)
        task = session.get(Task, resolved_id) if resolved_id else None

        if not task:
            return f"No task found with id {task_id}."

        result = (
            f"Task: {task.title}; "
            f"status: {task.status.value}; "
            f"priority: {task.priority.value}; "
            f"id: {task.task_id}"
        )

        if task.description:
            result += f"; description: {task.description}"

        if task.due_at:
            result += f"; due_at: {task.due_at.isoformat()}"


        if task.assigned_to:
            result += f"; assigned_to: {task.assigned_to}"

        return result

    finally:
        session.close()


@tool
def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_at: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """Update an existing task by its id or compact reference."""
    session = SessionLocal()

    try:
        resolved_id = _resolve_task_id(session, task_id)
        task = session.get(Task, resolved_id) if resolved_id else None

        if not task:
            return f"No task found with id {task_id}."

        changed = []

        if title is not None:
            task.title = title
            changed.append(f"title='{title}'")

        if description is not None:
            task.description = description or None
            changed.append("description updated")

        if due_at is not None:
            try:
                task.due_at = _parse_datetime(due_at, "due_at")
            except ValueError as exc:
                return str(exc)

            changed.append(f"due_at={due_at}")

        

        if assigned_to is not None:
            task.assigned_to = assigned_to or None
            changed.append("assigned_to updated")

        if priority is not None:
            try:
                task.priority = Priority(priority)
            except ValueError:
                return (
                    f"Invalid priority '{priority}'. "
                    "Use Low, Normal, or High."
                )

            changed.append(f"priority={priority}")

        if status is not None:
            try:
                task.status = TaskStatus(status)
            except ValueError:
                return (
                    f"Invalid status '{status}'. "
                    "Use Open, InProgress, Done, or Cancelled."
                )

            changed.append(f"status={status}")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated task '{task.title}' ({task.task_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update task: {exc}"

    finally:
        session.close()


@tool
def delete_task(task_id: str) -> str:
    """Delete an existing task by its id or compact reference."""
    session = SessionLocal()

    try:
        resolved_id = _resolve_task_id(session, task_id)
        task = session.get(Task, resolved_id) if resolved_id else None

        if not task:
            return f"No task found with id {task_id}."

        title = task.title

        session.delete(task)
        session.commit()

        return f"Deleted task '{title}' (id={task_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete task: {exc}"

    finally:
        session.close()


@tool
def complete_task(task_id: str) -> str:
    """Mark a task as Done."""
    session = SessionLocal()

    try:
        task = session.get(Task, task_id)

        if not task:
            return f"No task found with id {task_id}."

        task.status = TaskStatus.DONE
        session.commit()

        return f"Marked '{task.title}' as done."

    finally:
        session.close()


# ============================================================
# CALENDAR EVENT CRUD
# ============================================================

@tool
def create_calendar_event(
    title: str,
    starts_at: str,
    ends_at: str,
    owner_id: str = "",
    task_id: str = "",
) -> str:
    """Create a calendar event."""
    session = SessionLocal()

    try:
        try:
            parsed_start = datetime.fromisoformat(starts_at)
            parsed_end = datetime.fromisoformat(ends_at)
        except ValueError:
            return (
                "Invalid calendar datetime. "
                "Use ISO datetime strings."
            )

        if parsed_end <= parsed_start:
            return "ends_at must be later than starts_at."

        event = CalendarEvent(
            title=title,
            starts_at=parsed_start,
            ends_at=parsed_end,
            owner_id=owner_id or None,
            task_id=task_id or None,
        )

        session.add(event)
        session.commit()
        session.refresh(event)

        return (
            f"Created calendar event '{title}' "
            f"(id={event.event_id}) "
            f"from {parsed_start.isoformat()} "
            f"to {parsed_end.isoformat()}."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to create calendar event: {exc}"

    finally:
        session.close()


@tool
def list_calendar_events() -> str:
    """List recent calendar events."""
    session = SessionLocal()

    try:
        rows = (
            session.query(CalendarEvent)
            .order_by(CalendarEvent.starts_at.asc())
            .limit(20)
            .all()
        )

        if not rows:
            return "No calendar events found."

        return "\n".join(
            f"- {event.title}: "
            f"{event.starts_at.isoformat()} to "
            f"{event.ends_at.isoformat()} "
            f"(id={event.event_id})"
            for event in rows
        )

    finally:
        session.close()


@tool
def get_calendar_event(event_id: str) -> str:
    """Get one calendar event by stable event id."""
    session = SessionLocal()

    try:
        event = session.get(CalendarEvent, event_id)

        if not event:
            return f"No calendar event found with id {event_id}."

        return (
            f"Calendar event: {event.title}; "
            f"starts_at: {event.starts_at.isoformat()}; "
            f"ends_at: {event.ends_at.isoformat()}; "
            f"id: {event.event_id}"
        )

    finally:
        session.close()


@tool
def update_calendar_event(
    event_id: str,
    title: Optional[str] = None,
    starts_at: Optional[str] = None,
    ends_at: Optional[str] = None,
    owner_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> str:
    """Update an existing calendar event."""
    session = SessionLocal()

    try:
        event = session.get(CalendarEvent, event_id)

        if not event:
            return f"No calendar event found with id {event_id}."

        changed = []

        if title is not None:
            event.title = title
            changed.append(f"title='{title}'")

        if starts_at is not None:
            try:
                event.starts_at = datetime.fromisoformat(starts_at)
            except ValueError:
                return "Invalid starts_at. Use an ISO datetime."

            changed.append(f"starts_at={starts_at}")

        if ends_at is not None:
            try:
                event.ends_at = datetime.fromisoformat(ends_at)
            except ValueError:
                return "Invalid ends_at. Use an ISO datetime."

            changed.append(f"ends_at={ends_at}")

        if event.ends_at <= event.starts_at:
            return "ends_at must be later than starts_at."

        if owner_id is not None:
            event.owner_id = owner_id or None
            changed.append("owner_id updated")

        if task_id is not None:
            event.task_id = task_id or None
            changed.append("task_id updated")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated calendar event '{event.title}' "
            f"({event.event_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update calendar event: {exc}"

    finally:
        session.close()


@tool
def delete_calendar_event(event_id: str) -> str:
    """Delete an existing calendar event."""
    session = SessionLocal()

    try:
        event = session.get(CalendarEvent, event_id)

        if not event:
            return f"No calendar event found with id {event_id}."

        title = event.title

        session.delete(event)
        session.commit()

        return f"Deleted calendar event '{title}' (id={event_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete calendar event: {exc}"

    finally:
        session.close()


TOOLS = [
    create_task,
    list_tasks,
    get_task,
    update_task,
    delete_task,
    complete_task,
    create_calendar_event,
    list_calendar_events,
    get_calendar_event,
    update_calendar_event,
    delete_calendar_event,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}