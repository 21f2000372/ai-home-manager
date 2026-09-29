"""Tasks & Schedule domain models (US-2.x).

Tasks can be created manually or via chat (both converge on the same row).
Recurrence rules drive recurring chores; calendar events power the shared
calendar and overlap/conflict checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import Priority, TaskStatus
from app.models.people import User

event_attendees = Table(
    "event_attendees",
    Base.metadata,
    Column("event_id", String(36), ForeignKey("calendar_events.event_id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
)


class RecurrenceRule(Base):
    """A schedule expression used to generate recurring tasks (US-2.4)."""

    __tablename__ = "recurrence_rules"

    rule_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    # e.g. "FREQ=WEEKLY;BYDAY=FR" or a simple app-defined expression.
    expression: Mapped[str] = mapped_column(String(255), nullable=False)
    next_occurrence: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="recurrence_rule")


class Task(Base):
    """A household task, optionally assigned to a member and/or recurring."""

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Assignee is a household member (user). Nullable = unassigned.
    assigned_to: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=10), nullable=False, default=Priority.NORMAL
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=15), nullable=False, default=TaskStatus.OPEN
    )

    recurrence_rule_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("recurrence_rules.rule_id", ondelete="SET NULL"), nullable=True
    )

    assignee: Mapped[Optional["User"]] = relationship(
        "User", 
        foreign_keys=[assigned_to],
        lazy="selectin"  
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recurrence_rule: Mapped[Optional["RecurrenceRule"]] = relationship(back_populates="tasks")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Task {self.title!r} {self.status.value}>"


class CalendarEvent(Base):
    """A shared calendar event; overlap is checked on create (US-2.5/2.6)."""

    __tablename__ = "calendar_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optional owner and optional link back to a task.
    owner_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.task_id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    attendees: Mapped[list["User"]] = relationship(
        "User", secondary=event_attendees, backref="calendar_events"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<CalendarEvent {self.title!r} {self.starts_at}>"
