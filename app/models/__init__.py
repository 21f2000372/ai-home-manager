"""SQLAlchemy models for the six household domains.

Importing this package registers every model on the shared ``Base.metadata``
so ``Base.metadata.create_all()`` builds the full schema in one call.

Design: single household, role-based access (Admin / Adult / Child / Guest).
There is intentionally no ``tenant_id`` anywhere; the proposal scopes the
system to one household whose members have different roles.
"""

from app.models.enums import (
    BudgetPeriod,
    DocumentType,
    HouseholdRole,
    InviteStatus,
    IssueStatus,
    MembershipStatus,
    OccurrenceStatus,
    Priority,
    TaskStatus,
)
from app.models.people import Invite, Membership, User
from app.models.tasks import CalendarEvent, RecurrenceRule, Task
from app.models.inventory import (
    CommodityRule,
    GroceryItem,
    InventoryItem,
    PurchaseOccurrence,
)
from app.models.finance import Budget, Expense, RecurringBill
from app.models.maintenance import Appliance, MaintenanceIssue, Repair
from app.models.documents import (
    AgentInteraction,
    Conversation,
    Document,
    DocumentLink,
)

__all__ = [
    # enums
    "HouseholdRole",
    "MembershipStatus",
    "InviteStatus",
    "TaskStatus",
    "Priority",
    "OccurrenceStatus",
    "BudgetPeriod",
    "IssueStatus",
    "DocumentType",
    # people
    "User",
    "Membership",
    "Invite",
    # tasks
    "Task",
    "RecurrenceRule",
    "CalendarEvent",
    # inventory
    "InventoryItem",
    "GroceryItem",
    "CommodityRule",
    "PurchaseOccurrence",
    # finance
    "Expense",
    "Budget",
    "RecurringBill",
    # maintenance
    "Appliance",
    "MaintenanceIssue",
    "Repair",
    # documents / conversation
    "Document",
    "DocumentLink",
    "Conversation",
    "AgentInteraction",
]
