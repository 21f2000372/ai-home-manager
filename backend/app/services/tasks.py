"""Service layer for household tasks, recurring chores, and calendar events."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, case
from sqlalchemy.orm import Session

from app.models.enums import MembershipStatus, Priority, TaskStatus
from app.models.people import Membership, User
from app.models.tasks import CalendarEvent, Task

IST = timezone(timedelta(hours=5, minutes=30))


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetimes for comparison with the current SQLite storage.

    Although the model columns declare timezone=True, SQLite returns the
    persisted values as naive wall-clock datetimes in this app. Keep the
    wall-clock value and remove tzinfo so incoming aware values compare
    consistently with stored rows.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


class TaskService:
    DEFAULT_TASK_DURATION_MINUTES = 60

    @classmethod
    def check_task_conflicts(
        cls,
        session: Session,
        due_at: datetime,
        duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
        user_id: Optional[str] = None,
        exclude_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_end = _to_utc(due_at)
        task_start = task_end - timedelta(minutes=duration_minutes)

        # 1. Check for overlapping calendar meetings
        cal_query = session.query(CalendarEvent)
        if user_id:
            cal_query = cal_query.filter(
                (CalendarEvent.owner_id == user_id)
                | (CalendarEvent.attendees.any(User.user_id == user_id))
            )

        cal_conflicts = []
        for event in cal_query.all():
            event_start = _to_utc(event.starts_at)
            event_end = _to_utc(event.ends_at)
            if event_start and event_end and event_start < task_end and event_end > task_start:
                cal_conflicts.append(event)

        # 2. Check for overlapping open/in-progress tasks
        task_query = session.query(Task).filter(
            Task.due_at.isnot(None),
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )
        if user_id:
            task_query = task_query.filter(Task.assigned_to == user_id)
        if exclude_task_id:
            task_query = task_query.filter(Task.task_id != exclude_task_id)

        task_conflicts = []
        for other in task_query.all():
            other_end = _to_utc(other.due_at)
            if other_end is None:
                continue
            other_start = other_end - timedelta(minutes=cls.DEFAULT_TASK_DURATION_MINUTES)
            if other_start < task_end and other_end > task_start:
                task_conflicts.append(other)

        # Build calendar conflict payload with owner/member name
        formatted_cal_conflicts = []
        for e in cal_conflicts:
            owner = session.get(User, e.owner_id) if e.owner_id else None
            formatted_cal_conflicts.append({
                "event_id": e.event_id,
                "title": e.title,  # Meeting name
                "starts_at": e.starts_at.isoformat(),
                "ends_at": e.ends_at.isoformat(),
                
            })

        # Build task conflict payload with assignee name
        formatted_task_conflicts = []
        for task in task_conflicts:
            assignee = session.get(User, task.assigned_to) if task.assigned_to else None
            formatted_task_conflicts.append({
                "task_id": task.task_id,
                "title": task.title,  # Task name
                "due_at": task.due_at.isoformat(),
                "priority": task.priority.value,
                "assigned_to": task.assigned_to,
                "person_name": assignee.display_name if assignee else "Household Member",
            })

        has_conflict = len(formatted_cal_conflicts) > 0 or len(formatted_task_conflicts) > 0
        return {
            "has_conflict": has_conflict,
            "calendar_conflicts": formatted_cal_conflicts,
            "task_conflicts": formatted_task_conflicts,
        }

    @classmethod
    def create_task(
        cls,
        session: Session,
        title: str,
        created_by_id: str,
        description: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        priority: Priority = Priority.NORMAL,
        duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
        force: bool = False,
    ) -> Tuple[Optional[Task], Dict[str, Any]]:
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

        conflicts: Dict[str, Any] = {"has_conflict": False, "calendar_conflicts": [], "task_conflicts": []}
        if due_at:
            conflicts = cls.check_task_conflicts(
                session=session,
                due_at=due_at,
                duration_minutes=duration_minutes,
                user_id=assigned_to_id,
            )

        if conflicts["has_conflict"] and not force:
            return None, conflicts

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

        if assigned_to_id and assigned_to_id != created_by_id:
            from app.models.notifications import Notification
            session.add(
                Notification(
                    user_id=assigned_to_id,
                    title="New Task Assigned",
                    message=f"You have been assigned: '{task.title}'",
                )
            )

        session.commit()
        return task, conflicts

    @staticmethod
    def list_tasks(
        session: Session,
        assigned_to_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        """TIE BREAKER IMPLEMENTATION:
        1. Earliest deadline
        2. Priority rank (High > Normal > Low)
        3. Lifecycle stage (InProgress before Open)
        4. FIFO creation date
        """
        priority_rank = case(
            (Task.priority == Priority.HIGH, 1),
            (Task.priority == Priority.NORMAL, 2),
            (Task.priority == Priority.LOW, 3),
            else_=4,
        )

        status_rank = case(
            (Task.status == TaskStatus.IN_PROGRESS, 1),
            (Task.status == TaskStatus.OPEN, 2),
            (Task.status == TaskStatus.DONE, 3),
            (Task.status == TaskStatus.CANCELLED, 4),
            else_=5,
        )

        query = session.query(Task)
        if assigned_to_id:
            query = query.filter(Task.assigned_to == assigned_to_id)
        if status:
            query = query.filter(Task.status == status)

        return query.order_by(
            Task.due_at.asc().nullslast(),
            priority_rank.asc(),
            status_rank.asc(),
            Task.created_at.asc(),
        ).all()

    @staticmethod
    def update_task_status(session: Session, task_id: str, status: TaskStatus) -> Task:
        task = session.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        task.status = status
        session.commit()
        return task

    @staticmethod
    def list_user_tasks(
        session: Session,
        user_id: str,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        """Fetch tasks assigned specifically to a given user."""
        priority_rank = case(
            (Task.priority == Priority.HIGH, 1),
            (Task.priority == Priority.NORMAL, 2),
            (Task.priority == Priority.LOW, 3),
            else_=4,
        )
        status_rank = case(
            (Task.status == TaskStatus.IN_PROGRESS, 1),
            (Task.status == TaskStatus.OPEN, 2),
            (Task.status == TaskStatus.DONE, 3),
            (Task.status == TaskStatus.CANCELLED, 4),
            else_=5,
        )
        query = session.query(Task).filter(Task.assigned_to == user_id)
        if status:
            query = query.filter(Task.status == status)

        return query.order_by(
            Task.due_at.asc().nullslast(),
            priority_rank.asc(),
            status_rank.asc(),
            Task.created_at.asc(),
        ).all()

    @classmethod
    def update_task(
        cls,
        session: Session,
        task_id: str,
        title: str,
        description: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        priority: Priority = Priority.NORMAL,
        duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
    ) -> Tuple[Task, Dict[str, Any]]:
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

        conflicts: Dict[str, Any] = {"has_conflict": False, "calendar_conflicts": [], "task_conflicts": []}
        if due_at:
            conflicts = cls.check_task_conflicts(
                session=session,
                due_at=due_at,
                duration_minutes=duration_minutes,
                user_id=assigned_to_id or task.assigned_to,
                exclude_task_id=task.task_id,
            )
        old_assigned = task.assigned_to

        task.title = title.strip()
        task.description = description.strip() if description else None
        task.assigned_to = assigned_to_id
        task.due_at = due_at
        task.priority = priority

        if assigned_to_id and assigned_to_id != old_assigned:
            from app.models.notifications import Notification
            session.add(
                Notification(
                    user_id=assigned_to_id,
                    title="Task Reassigned to You",
                    message=f"You have been assigned the task: '{task.title}'",
                )
            )
        else:
            session.add(
                Notification(
                    user_id=old_assigned,
                    title="Task Updated",
                    message=f"The task '{task.title}' has been updated.",
                )
            )
        session.commit()
        return task, conflicts

    @staticmethod
    def delete_task(session: Session, task_id: str) -> None:
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
        attendee_ids: Optional[List[str]] = None,
        exclude_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        window_start = _to_utc(starts_at)
        window_end = _to_utc(ends_at)
        target_ids = list(set(attendee_ids or []))

        # 1. Calendar collisions
        cal_query = session.query(CalendarEvent).filter(
            CalendarEvent.starts_at < window_end,
            CalendarEvent.ends_at > window_start,
        )
        if exclude_event_id:
            cal_query = cal_query.filter(CalendarEvent.event_id != exclude_event_id)

        if target_ids:
            cal_query = cal_query.filter(
                (CalendarEvent.owner_id.in_(target_ids))
                | (CalendarEvent.attendees.any(User.user_id.in_(target_ids)))
            )

        cal_conflicts = cal_query.all()
        calendar_conflict_list = [
            {
                "event_id": e.event_id,
                "title": e.title,  # Meeting name
                "starts_at": e.starts_at.isoformat(),
                "ends_at": e.ends_at.isoformat(),
            }
            for e in cal_conflicts
        ]

        # 2. Task collisions
        task_query = session.query(Task).filter(
            Task.due_at.isnot(None),
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )
        if target_ids:
            task_query = task_query.filter(Task.assigned_to.in_(target_ids))

        task_conflict_list = []
        for task in task_query.all():
            task_end = _to_utc(task.due_at)
            if not task_end:
                continue
            task_start = task_end - timedelta(minutes=TaskService.DEFAULT_TASK_DURATION_MINUTES)
            if task_start < window_end and task_end > window_start:
                assignee = session.get(User, task.assigned_to) if task.assigned_to else None
                task_conflict_list.append({
                    "task_id": task.task_id,
                    "title": task.title,  # Task name
                    "due_at": task.due_at.isoformat(),
                    "priority": task.priority.value,
                    "person_name": assignee.display_name if assignee else "Household Member",
                })

        return {
            "has_conflict": len(calendar_conflict_list) > 0 or len(task_conflict_list) > 0,
            "calendar_conflicts": calendar_conflict_list,
            "task_conflicts": task_conflict_list,
        }

    @classmethod
    def create_meeting(
        cls,
        session: Session,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        organizer_id: str,
        attendee_ids: Optional[List[str]] = None,
        force: bool = False,
    ) -> Tuple[Optional[CalendarEvent], Dict[str, Any]]:
        if ends_at <= starts_at:
            raise ValueError("Event end time must occur after start time")

        attendee_ids = list(set((attendee_ids or []) + [organizer_id]))

        users = (
            session.query(User)
            .join(Membership)
            .filter(
                User.user_id.in_(attendee_ids),
                Membership.status == MembershipStatus.ACTIVE,
            )
            .all()
        )
        if len(users) != len(attendee_ids):
            raise ValueError("One or more selected attendees are not active household members")

        conflicts = cls.check_conflicts(
            session=session,
            starts_at=starts_at,
            ends_at=ends_at,
            attendee_ids=attendee_ids,
        )

        if conflicts["has_conflict"] and not force:
            return None, conflicts

        event = CalendarEvent(
            title=title.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            owner_id=organizer_id,
        )
        event.attendees = users
        session.add(event)

        utc_start = _to_utc(starts_at)
        ist_start = utc_start.astimezone(IST)
        formatted_ist_time = ist_start.strftime('%d %b %Y at %I:%M %p IST')

        from app.models.notifications import Notification
        for attendee in users:
            if attendee.user_id != organizer_id:
                session.add(
                    Notification(
                        user_id=attendee.user_id,
                        title="New Calendar Event",
                        message=f"You were added to '{event.title}' scheduled for {formatted_ist_time}",
                    )
                )
                
        session.commit()
        return event, conflicts

    @staticmethod
    def list_events(
        session: Session,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        query = session.query(CalendarEvent)
        if range_start:
            query = query.filter(CalendarEvent.ends_at >= range_start)
        if range_end:
            query = query.filter(CalendarEvent.starts_at <= range_end)
        return query.order_by(CalendarEvent.starts_at.asc()).all()

    @staticmethod
    def list_user_events(
        session: Session,
        user_id: str,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """Fetch events owned by or attended by a specific user."""
        query = session.query(CalendarEvent).filter(
            (CalendarEvent.owner_id == user_id)
            | (CalendarEvent.attendees.any(User.user_id == user_id))
        )
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
    ) -> Tuple[CalendarEvent, Dict[str, Any]]:
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

        attendee_ids = [u.user_id for u in event.attendees] if event.attendees else []
        if event.owner_id and event.owner_id not in attendee_ids:
            attendee_ids.append(event.owner_id)

        conflicts = cls.check_conflicts(
            session=session,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            attendee_ids=attendee_ids,
            exclude_event_id=event.event_id,
        )
        session.commit()
        return event, conflicts

    @staticmethod
    def delete_event(session: Session, event_id: str) -> None:
        event = session.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        if not event:
            raise ValueError("Calendar event not found")
        session.delete(event)
        session.commit()