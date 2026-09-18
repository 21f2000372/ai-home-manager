"""Maintenance domain tools."""
from __future__ import annotations

from datetime import date

from langchain_core.tools import tool
from typing import Optional
from app.db.base import SessionLocal
from app.models.enums import IssueStatus, Priority
from app.models.maintenance import (
    Appliance,
    MaintenanceIssue,
    Repair,
)


# ============================================================
# APPLIANCE CRUD
# ============================================================

@tool
def add_appliance(
    name: str,
    brand: str = "",
    model: str = "",
    purchased_at: str = "",
    warranty_ends_at: str = "",
) -> str:
    """Add a household appliance."""
    session = SessionLocal()

    try:
        parsed_purchased = None
        parsed_warranty = None

        if purchased_at:
            try:
                parsed_purchased = date.fromisoformat(purchased_at)
            except ValueError:
                return "Invalid purchased_at. Use YYYY-MM-DD."

        if warranty_ends_at:
            try:
                parsed_warranty = date.fromisoformat(warranty_ends_at)
            except ValueError:
                return "Invalid warranty_ends_at. Use YYYY-MM-DD."

        appliance = Appliance(
            name=name,
            brand=brand or None,
            model=model or None,
            purchased_at=parsed_purchased,
            warranty_ends_at=parsed_warranty,
        )

        session.add(appliance)
        session.commit()
        session.refresh(appliance)

        return (
            f"Added appliance '{name}' "
            f"(id={appliance.appliance_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to add appliance: {exc}"

    finally:
        session.close()


@tool
def list_appliances() -> str:
    """List household appliances."""
    session = SessionLocal()

    try:
        rows = (
            session.query(Appliance)
            .order_by(Appliance.created_at.desc())
            .all()
        )

        if not rows:
            return "No appliances found."

        return "\n".join(
            f"- {a.name}"
            f"{f' ({a.brand})' if a.brand else ''} "
            f"(id={a.appliance_id})"
            for a in rows
        )

    finally:
        session.close()


@tool
def get_appliance(appliance_id: str) -> str:
    """Get one appliance by id."""
    session = SessionLocal()

    try:
        appliance = session.get(Appliance, appliance_id)

        if not appliance:
            return f"No appliance found with id {appliance_id}."

        return (
            f"Appliance: {appliance.name}; "
            f"brand: {appliance.brand or 'not set'}; "
            f"model: {appliance.model or 'not set'}; "
            f"warranty: "
            f"{appliance.warranty_ends_at or 'not set'}; "
            f"id: {appliance.appliance_id}"
        )

    finally:
        session.close()


@tool
def update_appliance(
    appliance_id: str,
    name: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    purchased_at: Optional[str] = None,
    warranty_ends_at: Optional[str] = None,
) -> str:
    """Update an existing appliance."""
    session = SessionLocal()

    try:
        appliance = session.get(Appliance, appliance_id)

        if not appliance:
            return f"No appliance found with id {appliance_id}."

        changed = []

        if name is not None:
            appliance.name = name
            changed.append(f"name='{name}'")

        if brand is not None:
            appliance.brand = brand or None
            changed.append("brand updated")

        if model is not None:
            appliance.model = model or None
            changed.append("model updated")

        if purchased_at is not None:
            try:
                appliance.purchased_at = (
                    date.fromisoformat(purchased_at)
                    if purchased_at
                    else None
                )
            except ValueError:
                return "Invalid purchased_at. Use YYYY-MM-DD."

            changed.append(f"purchased_at={purchased_at}")

        if warranty_ends_at is not None:
            try:
                appliance.warranty_ends_at = (
                    date.fromisoformat(warranty_ends_at)
                    if warranty_ends_at
                    else None
                )
            except ValueError:
                return "Invalid warranty_ends_at. Use YYYY-MM-DD."

            changed.append(
                f"warranty_ends_at={warranty_ends_at}"
            )

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated appliance '{appliance.name}' "
            f"({appliance.appliance_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update appliance: {exc}"

    finally:
        session.close()


@tool
def delete_appliance(appliance_id: str) -> str:
    """Delete an appliance by id."""
    session = SessionLocal()

    try:
        appliance = session.get(Appliance, appliance_id)

        if not appliance:
            return f"No appliance found with id {appliance_id}."

        name = appliance.name

        session.delete(appliance)
        session.commit()

        return f"Deleted appliance '{name}' (id={appliance_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete appliance: {exc}"

    finally:
        session.close()


# ============================================================
# MAINTENANCE ISSUE CRUD
# ============================================================

@tool
def report_issue(
    description: str,
    appliance_id: str = "",
    priority: str = "Normal",
) -> str:
    """Report a maintenance issue."""
    session = SessionLocal()

    try:
        try:
            parsed_priority = Priority(priority)
        except ValueError:
            return "Invalid priority. Use Low, Normal, or High."

        issue = MaintenanceIssue(
            description=description,
            appliance_id=appliance_id or None,
            priority=parsed_priority,
        )

        session.add(issue)
        session.commit()
        session.refresh(issue)

        return (
            f"Logged issue '{description}' "
            f"(id={issue.issue_id})."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to report issue: {exc}"

    finally:
        session.close()


@tool
def list_issues(status: str = "") -> str:
    """List maintenance issues."""
    session = SessionLocal()

    try:
        query = session.query(MaintenanceIssue)

        if status:
            try:
                parsed_status = IssueStatus(status)
            except ValueError:
                return (
                    f"Invalid status '{status}'. "
                    "Use Open, InProgress, Resolved, or Closed."
                )

            query = query.filter(
                MaintenanceIssue.status == parsed_status
            )

        rows = (
            query
            .order_by(MaintenanceIssue.created_at.desc())
            .limit(20)
            .all()
        )

        if not rows:
            return "No maintenance issues found."

        return "\n".join(
            f"- [{i.status.value}] {i.description} "
            f"(priority={i.priority.value}, id={i.issue_id})"
            for i in rows
        )

    finally:
        session.close()


@tool
def get_issue(issue_id: str) -> str:
    """Get one maintenance issue by id."""
    session = SessionLocal()

    try:
        issue = session.get(MaintenanceIssue, issue_id)

        if not issue:
            return f"No maintenance issue found with id {issue_id}."

        return (
            f"Maintenance issue: {issue.description}; "
            f"status: {issue.status.value}; "
            f"priority: {issue.priority.value}; "
            f"appliance_id: {issue.appliance_id or 'none'}; "
            f"id: {issue.issue_id}"
        )

    finally:
        session.close()


@tool
def update_issue(
    issue_id: str,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    appliance_id: Optional[str] = None,
) -> str:
    """Update an existing maintenance issue."""
    session = SessionLocal()

    try:
        issue = session.get(MaintenanceIssue, issue_id)

        if not issue:
            return f"No maintenance issue found with id {issue_id}."

        changed = []

        if description is not None:
            issue.description = description
            changed.append("description updated")

        if status is not None:
            try:
                issue.status = IssueStatus(status)
            except ValueError:
                return (
                    f"Invalid status '{status}'. "
                    "Use Open, InProgress, Resolved, or Closed."
                )

            changed.append(f"status={status}")

        if priority is not None:
            try:
                issue.priority = Priority(priority)
            except ValueError:
                return "Invalid priority. Use Low, Normal, or High."

            changed.append(f"priority={priority}")

        if appliance_id is not None:
            issue.appliance_id = appliance_id or None
            changed.append("appliance_id updated")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated maintenance issue ({issue.issue_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update issue: {exc}"

    finally:
        session.close()


@tool
def delete_issue(issue_id: str) -> str:
    """Delete a maintenance issue."""
    session = SessionLocal()

    try:
        issue = session.get(MaintenanceIssue, issue_id)

        if not issue:
            return f"No maintenance issue found with id {issue_id}."

        session.delete(issue)
        session.commit()

        return f"Deleted maintenance issue (id={issue_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete issue: {exc}"

    finally:
        session.close()


# ============================================================
# REPAIR CRUD
# ============================================================

@tool
def log_repair(
    appliance_id: str = "",
    serviced_at: str = "",
    provider: str = "",
    cost_minor: int = 0,
    currency: str = "USD",
    notes: str = "",
) -> str:
    """Record a repair."""
    session = SessionLocal()

    try:
        try:
            parsed_date = (
                date.fromisoformat(serviced_at)
                if serviced_at
                else date.today()
            )
        except ValueError:
            return "Invalid serviced_at. Use YYYY-MM-DD."

        repair = Repair(
            appliance_id=appliance_id or None,
            serviced_at=parsed_date,
            provider=provider or None,
            cost_minor=cost_minor or None,
            currency=currency,
            notes=notes or None,
        )

        session.add(repair)
        session.commit()
        session.refresh(repair)

        return (
            f"Logged repair (id={repair.repair_id}) "
            f"for {parsed_date}."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to log repair: {exc}"

    finally:
        session.close()


@tool
def list_repairs() -> str:
    """List repair history."""
    session = SessionLocal()

    try:
        rows = (
            session.query(Repair)
            .order_by(Repair.serviced_at.desc())
            .limit(20)
            .all()
        )

        if not rows:
            return "No repairs found."

        return "\n".join(
            f"- {r.serviced_at}: "
            f"{r.provider or 'Unknown provider'} "
            f"(cost={r.cost_minor / 100:.2f} {r.currency}"
            f"{', ' + r.notes if r.notes else ''}, "
            f"id={r.repair_id})"
            for r in rows
        )

    finally:
        session.close()


@tool
def get_repair(repair_id: str) -> str:
    """Get one repair by id."""
    session = SessionLocal()

    try:
        repair = session.get(Repair, repair_id)

        if not repair:
            return f"No repair found with id {repair_id}."

        cost = (
            f"{repair.cost_minor / 100:.2f} {repair.currency}"
            if repair.cost_minor is not None
            else "not recorded"
        )

        return (
            f"Repair: id={repair.repair_id}; "
            f"appliance_id={repair.appliance_id or 'none'}; "
            f"serviced_at={repair.serviced_at}; "
            f"provider={repair.provider or 'not recorded'}; "
            f"cost={cost}; "
            f"notes={repair.notes or 'none'}"
        )

    finally:
        session.close()


@tool
def update_repair(
    repair_id: str,
    appliance_id: Optional[str] = None,
    serviced_at: Optional[str] = None,
    provider: Optional[str] = None,
    cost_minor: Optional[int] = None,
    currency: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Update an existing repair."""
    session = SessionLocal()

    try:
        repair = session.get(Repair, repair_id)

        if not repair:
            return f"No repair found with id {repair_id}."

        changed = []

        if appliance_id is not None:
            repair.appliance_id = appliance_id or None
            changed.append("appliance_id updated")

        if serviced_at is not None:
            try:
                repair.serviced_at = date.fromisoformat(serviced_at)
            except ValueError:
                return "Invalid serviced_at. Use YYYY-MM-DD."

            changed.append(f"serviced_at={serviced_at}")

        if provider is not None:
            repair.provider = provider or None
            changed.append("provider updated")

        if cost_minor is not None:
            repair.cost_minor = cost_minor
            changed.append(f"cost_minor={cost_minor}")

        if currency is not None:
            repair.currency = currency
            changed.append(f"currency={currency}")

        if notes is not None:
            repair.notes = notes or None
            changed.append("notes updated")

        if not changed:
            return "No changes were provided."

        session.commit()

        return (
            f"Updated repair ({repair.repair_id}): "
            + ", ".join(changed)
            + "."
        )

    except Exception as exc:
        session.rollback()
        return f"Failed to update repair: {exc}"

    finally:
        session.close()


@tool
def delete_repair(repair_id: str) -> str:
    """Delete a repair by id."""
    session = SessionLocal()

    try:
        repair = session.get(Repair, repair_id)

        if not repair:
            return f"No repair found with id {repair_id}."

        session.delete(repair)
        session.commit()

        return f"Deleted repair (id={repair_id})."

    except Exception as exc:
        session.rollback()
        return f"Failed to delete repair: {exc}"

    finally:
        session.close()


TOOLS = [
    add_appliance,
    list_appliances,
    get_appliance,
    update_appliance,
    delete_appliance,

    report_issue,
    list_issues,
    get_issue,
    update_issue,
    delete_issue,

    log_repair,
    list_repairs,
    get_repair,
    update_repair,
    delete_repair,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}