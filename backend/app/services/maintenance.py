"""Service layer for Home & Maintenance: appliances, warranties, issues, and repairs."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.enums import IssueStatus, Priority
from app.models.maintenance import Appliance, MaintenanceIssue, Repair


class MaintenanceService:
    # -------------------------------------------------------------------------
    # Appliances & Warranties (US-5.1)
    # -------------------------------------------------------------------------

    @staticmethod
    def add_appliance(
        session: Session,
        name: str,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        purchased_at: Optional[date] = None,
        warranty_ends_at: Optional[date] = None,
    ) -> Appliance:
        """Register a new household appliance with optional warranty tracking."""
        appliance = Appliance(
            name=name.strip(),
            brand=brand.strip() if brand else None,
            model=model.strip() if model else None,
            purchased_at=purchased_at,
            warranty_ends_at=warranty_ends_at,
        )
        session.add(appliance)
        session.commit()
        return appliance

    @staticmethod
    def list_appliances(session: Session) -> List[Appliance]:
        """Fetch all tracked appliances."""
        return session.query(Appliance).order_by(Appliance.name.asc()).all()

    @staticmethod
    def get_appliance(session: Session, appliance_id: str) -> Optional[Appliance]:
        """Fetch a single appliance by ID."""
        return session.query(Appliance).filter(Appliance.appliance_id == appliance_id).first()

    @staticmethod
    def update_appliance(
        session: Session,
        appliance_id: str,
        name: Optional[str] = None,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        purchased_at: Optional[date] = None,
        warranty_ends_at: Optional[date] = None,
    ) -> Appliance:
        """Update appliance details and warranty."""
        appliance = session.query(Appliance).filter(Appliance.appliance_id == appliance_id).first()
        if not appliance:
            raise ValueError("Appliance not found")
        if name is not None:
            appliance.name = name.strip()
        if brand is not None:
            appliance.brand = brand.strip() if brand else None
        if model is not None:
            appliance.model = model.strip() if model else None
        if purchased_at is not None:
            appliance.purchased_at = purchased_at
        if warranty_ends_at is not None:
            appliance.warranty_ends_at = warranty_ends_at
        session.commit()
        return appliance

    @staticmethod
    def delete_appliance(session: Session, appliance_id: str) -> None:
        """Delete an appliance and its service records."""
        appliance = session.query(Appliance).filter(Appliance.appliance_id == appliance_id).first()
        if not appliance:
            raise ValueError("Appliance not found")
        session.delete(appliance)
        session.commit()

    @staticmethod
    def get_expiring_warranties(
        session: Session, days_ahead: int = 30
    ) -> List[Dict[str, Any]]:
        """US-5.1: Retrieve appliances whose warranties expire within the given window."""
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        appliances = (
            session.query(Appliance)
            .filter(
                Appliance.warranty_ends_at.isnot(None),
                Appliance.warranty_ends_at >= today,
                Appliance.warranty_ends_at <= cutoff,
            )
            .order_by(Appliance.warranty_ends_at.asc())
            .all()
        )

        return [
            {
                "appliance_id": a.appliance_id,
                "name": a.name,
                "brand": a.brand,
                "model": a.model,
                "warranty_ends_at": a.warranty_ends_at.isoformat(),
                "days_remaining": (a.warranty_ends_at - today).days,
            }
            for a in appliances
        ]

    # -------------------------------------------------------------------------
    # Maintenance Issues (US-5.2)
    # -------------------------------------------------------------------------

    @staticmethod
    def report_issue(
        session: Session,
        description: str,
        reported_by_id: str,
        priority: Priority = Priority.NORMAL,
        appliance_id: Optional[str] = None,
        accountable_to_id: Optional[str] = None,
    ) -> MaintenanceIssue:
        """Report a maintenance problem."""
        if appliance_id:
            appliance = session.query(Appliance).filter(Appliance.appliance_id == appliance_id).first()
            if not appliance:
                raise ValueError("Associated appliance not found")

        issue = MaintenanceIssue(
            description=description.strip(),
            reported_by=reported_by_id,
            priority=priority,
            status=IssueStatus.OPEN,
            appliance_id=appliance_id,
            accountable_to=accountable_to_id,
        )
        session.add(issue)
        session.commit()
        return issue

    @staticmethod
    def list_issues(
        session: Session,
        status: Optional[IssueStatus] = None,
        appliance_id: Optional[str] = None,
    ) -> List[MaintenanceIssue]:
        """Fetch logged issues with optional status or appliance filters."""
        query = session.query(MaintenanceIssue)
        if status:
            query = query.filter(MaintenanceIssue.status == status)
        if appliance_id:
            query = query.filter(MaintenanceIssue.appliance_id == appliance_id)
        return query.order_by(MaintenanceIssue.created_at.desc()).all()

    @staticmethod
    def get_issue(session: Session, issue_id: str) -> Optional[MaintenanceIssue]:
        """Fetch a single issue by ID."""
        return session.query(MaintenanceIssue).filter(MaintenanceIssue.issue_id == issue_id).first()

    @staticmethod
    def update_issue(
        session: Session,
        issue_id: str,
        description: Optional[str] = None,
        status: Optional[IssueStatus] = None,
        priority: Optional[Priority] = None,
        accountable_to_id: Optional[str] = None,
    ) -> MaintenanceIssue:
        """Update issue state or reassign accountability."""
        issue = session.query(MaintenanceIssue).filter(MaintenanceIssue.issue_id == issue_id).first()
        if not issue:
            raise ValueError("Issue not found")
        if description is not None:
            issue.description = description.strip()
        if status is not None:
            issue.status = status
        if priority is not None:
            issue.priority = priority
        if accountable_to_id is not None:
            issue.accountable_to = accountable_to_id
        session.commit()
        return issue

    @staticmethod
    def delete_issue(session: Session, issue_id: str) -> None:
        """Delete a maintenance issue."""
        issue = session.query(MaintenanceIssue).filter(MaintenanceIssue.issue_id == issue_id).first()
        if not issue:
            raise ValueError("Issue not found")
        session.delete(issue)
        session.commit()

    # -------------------------------------------------------------------------
    # Repairs & Service History (US-5.3)
    # -------------------------------------------------------------------------

    @staticmethod
    def log_repair(
        session: Session,
        logged_by_id: str,
        serviced_at: date,
        appliance_id: Optional[str] = None,
        provider: Optional[str] = None,
        cost_minor: Optional[int] = None,
        currency: str = "USD",
        notes: Optional[str] = None,
    ) -> Repair:
        """Log a service or maintenance repair record."""
        if cost_minor is not None and cost_minor < 0:
            raise ValueError("Cost cannot be negative")

        if appliance_id:
            appliance = session.query(Appliance).filter(Appliance.appliance_id == appliance_id).first()
            if not appliance:
                raise ValueError("Associated appliance not found")

        repair = Repair(
            logged_by=logged_by_id,
            serviced_at=serviced_at,
            appliance_id=appliance_id,
            provider=provider.strip() if provider else None,
            cost_minor=cost_minor,
            currency=currency.upper(),
            notes=notes.strip() if notes else None,
        )
        session.add(repair)
        session.commit()
        return repair

    @staticmethod
    def list_repairs(
        session: Session, appliance_id: Optional[str] = None
    ) -> List[Repair]:
        """Retrieve service repair history."""
        query = session.query(Repair)
        if appliance_id:
            query = query.filter(Repair.appliance_id == appliance_id)
        return query.order_by(Repair.serviced_at.desc()).all()

    @staticmethod
    def get_repair(session: Session, repair_id: str) -> Optional[Repair]:
        """Fetch a single repair record by ID."""
        return session.query(Repair).filter(Repair.repair_id == repair_id).first()

    @staticmethod
    def update_repair(
        session: Session,
        repair_id: str,
        serviced_at: Optional[date] = None,
        provider: Optional[str] = None,
        cost_minor: Optional[int] = None,
        currency: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Repair:
        """Update an existing repair record."""
        repair = session.query(Repair).filter(Repair.repair_id == repair_id).first()
        if not repair:
            raise ValueError("Repair record not found")
        if serviced_at is not None:
            repair.serviced_at = serviced_at
        if provider is not None:
            repair.provider = provider.strip() if provider else None
        if cost_minor is not None:
            if cost_minor < 0:
                raise ValueError("Cost cannot be negative")
            repair.cost_minor = cost_minor
        if currency is not None:
            repair.currency = currency.upper()
        if notes is not None:
            repair.notes = notes.strip() if notes else None
        session.commit()
        return repair

    @staticmethod
    def delete_repair(session: Session, repair_id: str) -> None:
        """Delete a repair record."""
        repair = session.query(Repair).filter(Repair.repair_id == repair_id).first()
        if not repair:
            raise ValueError("Repair record not found")
        session.delete(repair)
        session.commit()