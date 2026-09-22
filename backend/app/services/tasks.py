"""Service layer for household tasks, recurring chores, and calendar events."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.enums import MembershipStatus, Priority, TaskStatus
from app.models.people import Membership, User
from app.models.tasks import CalendarEvent, Task


class TaskService:
    @staticmethod
    def create_task(
        session: Session,
        title: str,
        created_by_id: str,
        description: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        priority: Priority = Priority.NORMAL,
    ) -> Task:
        """Create a household task record (US-2.2)."""
        if assigned_to_id:
            assignee = (
                session.query(User)
                .join(Membership)
                .filter(
                    User.user_id == assigned_to_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
                .first()
            )
            if not assignee:
                raise ValueError("Assigned member was not found in the active household")

        task = Task(
            title=title.strip(),
            description=description.strip() if description else None,
            assigned_to=assigned_to_id,
            created_by=created_by_id,
            due_at=due_at,
            priority=priority,
            status=TaskStatus.OPEN,
        )
        session.add(task)
        session.commit()
        return task

    @staticmethod
    def list_tasks(
        session: Session,
        assigned_to_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        """Query tasks with optional filtering by assignee or status (US-2.3)."""
        query = session.query(Task)
        if assigned_to_id:
            query = query.filter(Task.assigned_to == assigned_to_id)
        if status:
            query = query.filter(Task.status == status)
        return query.order_by(Task.due_at.asc().nullslast()).all()

    @staticmethod
    def update_task_status(
        session: Session,
        task_id: str,
        status: TaskStatus,
    ) -> Task:
        """Update workflow status of an existing task."""
        task = session.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        task.status = status
        session.commit()
        return task

    @staticmethod
    def update_task(
        session: Session,
        task_id: str,
        title: str,
        description: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        priority: Priority = Priority.NORMAL,
    ) -> Task:
        """Update editable task fields while preserving its lifecycle status."""
        task = session.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise ValueError("Task not found")

        if assigned_to_id:
            assignee = (
                session.query(User)
                .join(Membership)
                .filter(
                    User.user_id == assigned_to_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
                .first()
            )
            if not assignee:
                raise ValueError("Assigned member was not found in the active household")

        task.title = title.strip()
        task.description = description.strip() if description else None
        task.assigned_to = assigned_to_id
        task.due_at = due_at
        task.priority = priority
        session.commit()
        return task

    
    @staticmethod
    def delete_task(session: Session, task_id: str) -> None:
        """Delete a task record."""
        task = session.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        session.delete(task)
        session.commit()


class CalendarService:
    @staticmethod
    def check_conflicts(
        session: Session,
        starts_at: datetime,
        ends_at: datetime,
        exclude_event_id: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """Detect overlapping calendar entries across the household (US-2.6)."""
        query = session.query(CalendarEvent).filter(
            and_(
                CalendarEvent.starts_at < ends_at,
                CalendarEvent.ends_at > starts_at,
            )
        )
        if exclude_event_id:
            query = query.filter(CalendarEvent.event_id != exclude_event_id)
        return query.all()

    @classmethod
    def create_event(
        cls,
        session: Session,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        owner_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Tuple[CalendarEvent, List[CalendarEvent]]:
        """Add calendar event and return any detected overlapping events."""
        if ends_at <= starts_at:
            raise ValueError("Event end time must occur after start time")

        conflicts = cls.check_conflicts(session, starts_at, ends_at)

        event = CalendarEvent(
            title=title.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            owner_id=owner_id,
            task_id=task_id,
        )
        session.add(event)
        session.commit()
        return event, conflicts

    @staticmethod
    def list_events(
        session: Session,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """Retrieve shared household calendar events (US-2.5)."""
        query = session.query(CalendarEvent)
        if range_start:
            query = query.filter(CalendarEvent.ends_at >= range_start)
        if range_end:
            query = query.filter(CalendarEvent.starts_at <= range_end)
        return query.order_by(CalendarEvent.starts_at.asc()).all()

    @classmethod
    def update_event(
        cls,
        session: Session,
        event_id: str,
        title: Optional[str] = None,
        starts_at: Optional[datetime] = None,
        ends_at: Optional[datetime] = None,
    ) -> Tuple[CalendarEvent, List[CalendarEvent]]:
        """Update an event and check for time-overlap conflicts against other events."""
        event = session.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        if not event:
            raise ValueError("Calendar event not found")
        if title is not None:
            event.title = title.strip()
        if starts_at is not None:
            event.starts_at = starts_at
        if ends_at is not None:
            event.ends_at = ends_at
        if event.ends_at <= event.starts_at:
            raise ValueError("Event end time must occur after start time")
        conflicts = cls.check_conflicts(session, event.starts_at, event.ends_at, exclude_event_id=event.event_id)
        session.commit()
        return event, conflicts

    @staticmethod
    def delete_event(session: Session, event_id: str) -> None:
        """Delete a shared calendar event."""
        event = session.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        if not event:
            raise ValueError("Calendar event not found")
        session.delete(event)
        session.commit()

    