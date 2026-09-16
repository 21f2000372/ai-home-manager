"""Seed the database with one household of members and sample domain data.

Run:  python -m scripts.seed        (creates schema if needed, then seeds)
      python -m scripts.seed --reset (drops and recreates first)

Single-household model: four members demonstrate every role
(Admin / Adult / Child / Guest) so the RBAC layer has data to authorize
against. A little data is added to each of the six domains so the agents and
RAG layer have something to query during development.

Default password for every seeded user: "password123"  (development only).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from app.auth.passwords import hash_password
from app.db.base import SessionLocal
from app.db.init_db import create_all, drop_all
from app.models import (
    Appliance,
    Budget,
    BudgetPeriod,
    CalendarEvent,
    CommodityRule,
    Conversation,
    Document,
    DocumentLink,
    DocumentType,
    Expense,
    GroceryItem,
    HouseholdRole,
    InventoryItem,
    IssueStatus,
    MaintenanceIssue,
    Membership,
    MembershipStatus,
    Priority,
    PurchaseOccurrence,
    RecurringBill,
    Task,
    TaskStatus,
    User,
)

DEFAULT_PASSWORD = "password123"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_user(email: str, name: str, dob: date, role: HouseholdRole) -> User:
    user = User(
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        display_name=name,
        date_of_birth=dob,
    )
    user.membership = Membership(role=role, status=MembershipStatus.ACTIVE)
    return user


def seed() -> None:
    session = SessionLocal()
    try:
        # --- People & Permissions: one household, four roles ---
        admin = _make_user("admin@home.test", "Ravi (Admin)", date(1985, 4, 12), HouseholdRole.ADMIN)
        adult = _make_user("adult@home.test", "Meera (Adult)", date(1988, 9, 3), HouseholdRole.ADULT)
        child = _make_user("child@home.test", "Aarav (Child)", date(2014, 1, 20), HouseholdRole.CHILD)
        guest = _make_user("guest@home.test", "Sam (Guest)", date(1979, 6, 30), HouseholdRole.GUEST)
        session.add_all([admin, adult, child, guest])
        session.flush()  # assign user_ids

        # --- Tasks & Schedule ---
        session.add_all(
            [
                Task(
                    title="Take out the trash",
                    description="Kitchen and bathroom bins",
                    assigned_to=child.user_id,
                    created_by=admin.user_id,
                    due_at=_now() + timedelta(days=2),
                    priority=Priority.NORMAL,
                    status=TaskStatus.OPEN,
                ),
                Task(
                    title="Pay electricity bill",
                    assigned_to=adult.user_id,
                    created_by=admin.user_id,
                    due_at=_now() + timedelta(days=5),
                    priority=Priority.HIGH,
                    status=TaskStatus.OPEN,
                ),
            ]
        )
        start = _now() + timedelta(days=3)
        session.add(
            CalendarEvent(
                title="Saturday family dinner",
                starts_at=start,
                ends_at=start + timedelta(hours=2),
                owner_id=adult.user_id,
            )
        )

        # --- Food & Inventory ---
        milk = InventoryItem(name="Milk", quantity=1, unit="litre", low_stock_threshold=2)
        eggs = InventoryItem(name="Eggs", quantity=4, unit="pcs", low_stock_threshold=6)
        session.add_all([milk, eggs])
        session.flush()

        session.add_all(
            [
                GroceryItem(name="Bread", quantity=2, unit="loaf", added_by=adult.user_id),
                GroceryItem(
                    name="Tomatoes", quantity=1, unit="kg", purchased=True, added_by=child.user_id
                ),
            ]
        )
        milk_rule = CommodityRule(
            name="Milk", quantity=1, unit="litre", schedule="DAILY", low_stock_threshold=2
        )
        session.add(milk_rule)
        session.flush()
        session.add(
            PurchaseOccurrence(
                rule_id=milk_rule.rule_id, occurrence_date=date.today(), item_id=milk.item_id
            )
        )

        # --- Finance & Budgeting (amounts in minor units / cents) ---
        session.add_all(
            [
                Budget(category="Groceries", limit_minor=40000, period=BudgetPeriod.MONTHLY),
                Expense(
                    amount_minor=1250,
                    category="Groceries",
                    description="Tomatoes and bread",
                    recorded_by=adult.user_id,
                ),
                RecurringBill(
                    payee="City Electric",
                    expected_amount_minor=8000,
                    category="Utilities",
                    due_at=_now() + timedelta(days=6),
                    recurrence="MONTHLY",
                ),
            ]
        )

        # --- Home & Maintenance ---
        dishwasher = Appliance(
            name="Dishwasher",
            brand="Bosch",
            purchased_at=date(2023, 5, 1),
            warranty_ends_at=date.today() + timedelta(days=40),
        )
        session.add(dishwasher)
        session.flush()
        session.add(
            MaintenanceIssue(
                description="AC is making a rattling noise",
                status=IssueStatus.OPEN,
                priority=Priority.HIGH,
                reported_by=adult.user_id,
            )
        )

        # --- Documents + Conversation ---
        receipt = Document(
            document_type=DocumentType.RECEIPT,
            storage_key="receipts/seed-grocery-receipt.jpg",
            original_filename="grocery-receipt.jpg",
            mime_type="image/jpeg",
            uploaded_by=adult.user_id,
        )
        session.add(receipt)
        session.flush()
        session.add(
            DocumentLink(
                document_id=receipt.document_id,
                linked_domain="finance",
                linked_record_id=receipt.document_id,  # placeholder link target
            )
        )
        session.add(
            Conversation(session_id="seed-session-1", user_id=adult.user_id)
        )

        session.commit()
        print("Seed complete.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the AI Home Manager database.")
    parser.add_argument(
        "--reset", action="store_true", help="Drop all tables before creating and seeding."
    )
    args = parser.parse_args()

    if args.reset:
        drop_all()
        print("Dropped existing tables.")

    create_all()
    print("Schema ready.")
    seed()


if __name__ == "__main__":
    main()
