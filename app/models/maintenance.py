"""Home & Maintenance domain models (US-5.x).

Appliances carry warranty end dates for reminders. Maintenance issues track
reported problems. Repairs record service history against an appliance.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import IssueStatus, Priority


class Appliance(Base):
    """A household appliance with optional warranty tracking (US-5.2)."""

    __tablename__ = "appliances"

    appliance_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    purchased_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_ends_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    repairs: Mapped[list["Repair"]] = relationship(
        back_populates="appliance", cascade="all, delete-orphan"
    )
    issues: Mapped[list["MaintenanceIssue"]] = relationship(back_populates="appliance")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Appliance {self.name}>"


class MaintenanceIssue(Base):
    """A reported maintenance issue (US-5.3)."""

    __tablename__ = "maintenance_issues"

    issue_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, native_enum=False, length=12), nullable=False, default=IssueStatus.OPEN
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=10), nullable=False, default=Priority.NORMAL
    )
    reported_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    accountable_to: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    appliance_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("appliances.appliance_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    appliance: Mapped[Optional["Appliance"]] = relationship(back_populates="issues")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<MaintenanceIssue {self.status.value}>"


class Repair(Base):
    """A service/repair history record (US-5.1)."""

    __tablename__ = "repairs"

    repair_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    appliance_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("appliances.appliance_id", ondelete="SET NULL"), nullable=True, index=True
    )
    serviced_at: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    cost_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    appliance: Mapped[Optional["Appliance"]] = relationship(back_populates="repairs")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Repair {self.provider} {self.serviced_at}>"
