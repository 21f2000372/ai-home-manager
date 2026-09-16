"""People & Permissions domain models (US-1.x).

Single household. A ``User`` is a global identity with login credentials.
A ``Membership`` links a user to the household with a role and status. Roles
drive the RBAC that the Authorize step enforces before any agent/LLM call.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import HouseholdRole, InviteStatus, MembershipStatus


class User(Base):
    """A person who can authenticate. Identity is global, not role-scoped."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)

    # --- Auth (JWT is issued against these) ---
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Profile ---
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # date_of_birth is preferred over a static age so "Child" status can be
    # derived correctly over time. age is kept as an optional convenience.
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    relationship_label: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    membership: Mapped[Optional["Membership"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User {self.display_name} ({self.email})>"


class Membership(Base):
    """Links a user to the household with a role and lifecycle status.

    In a single-household model there is one membership per user. The role
    (Admin/Adult/Child/Guest) is the authorization source.
    """

    __tablename__ = "memberships"

    membership_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    role: Mapped[HouseholdRole] = mapped_column(
        Enum(HouseholdRole, native_enum=False, length=20), nullable=False
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=20),
        nullable=False,
        default=MembershipStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="membership")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Membership {self.role.value}/{self.status.value} user={self.user_id}>"


class Invite(Base):
    """An invite code (hashed at rest) used to join the household (US-1.2)."""

    __tablename__ = "invites"

    invite_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    code_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    status: Mapped[InviteStatus] = mapped_column(
        Enum(InviteStatus, native_enum=False, length=20),
        nullable=False,
        default=InviteStatus.ACTIVE,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Invite {self.status.value}>"
