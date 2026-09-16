"""Shared enums used across domain models.

Stored as plain strings in SQLite via SQLAlchemy's ``Enum`` type. Using
``str, Enum`` mixins keeps values human-readable in the database and JSON.
"""

from __future__ import annotations

from enum import Enum


class HouseholdRole(str, Enum):
    """A member's role within the single household."""

    ADMIN = "Admin"
    ADULT = "Adult"
    CHILD = "Child"
    GUEST = "Guest"


class MembershipStatus(str, Enum):
    """Lifecycle of a member's participation."""

    PENDING = "Pending"
    ACTIVE = "Active"
    REJECTED = "Rejected"
    SUSPENDED = "Suspended"
    REMOVED = "Removed"


class InviteStatus(str, Enum):
    """Lifecycle of an invite code."""

    ACTIVE = "Active"
    USED = "Used"
    EXPIRED = "Expired"
    REVOKED = "Revoked"


class TaskStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "InProgress"
    DONE = "Done"
    CANCELLED = "Cancelled"


class Priority(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"


class OccurrenceStatus(str, Enum):
    """Status of a generated recurring purchase occurrence."""

    PENDING = "Pending"
    PURCHASED = "Purchased"
    SKIPPED = "Skipped"


class BudgetPeriod(str, Enum):
    MONTHLY = "Monthly"
    WEEKLY = "Weekly"
    CUSTOM = "Custom"


class IssueStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "InProgress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class DocumentType(str, Enum):
    RECEIPT = "Receipt"
    BILL = "Bill"
    WARRANTY = "Warranty"
    OTHER = "Other"
