"""Authorize step: minimum role required per (domain, tool) pair.

This is the RBAC gate between the Specialist agent *proposing* an action and
the Execute node actually writing to the database (diagram: "Authorize
check -> Verifies role permits this action"). It mirrors the role hierarchy
already used by app.auth.decorators.require_min_role, but applied to tool
calls rather than HTTP routes, since one chat message can trigger different
underlying actions depending on what the specialist decides to do.

Review/edit TOOL_PERMISSIONS to match your household's actual rules — the
values below are reasonable defaults, not a spec.
"""
from __future__ import annotations

from typing import Dict, Tuple

from app.models.enums import HouseholdRole

ROLE_RANK: Dict[HouseholdRole, int] = {
    HouseholdRole.GUEST: 0,
    HouseholdRole.CHILD: 1,
    HouseholdRole.ADULT: 2,
    HouseholdRole.ADMIN: 3,
}
TOOL_DOMAINS: Dict[str, str] = {
    # Grocery
    "add_grocery_item": "food",
    "list_grocery_items": "food",
    "get_grocery_item": "food",
    "update_grocery_item": "food",
    "delete_grocery_item": "food",
    "mark_purchased": "food",
    # Inventory
    "add_inventory_item": "food",
    "list_inventory": "food",
    "get_inventory_item": "food",
    "update_inventory_item": "food",
    "delete_inventory_item": "food",

    # Tasks
    "get_task": "tasks",
    "update_task": "tasks",
    "delete_task": "tasks",
    "create_task":"tasks",
    "list_tasks":"tasks",
    "complete_task":"tasks",
    "create_calendar_event": "tasks",
    "list_calendar_events": "tasks",
    "get_calendar_event": "tasks",
    "update_calendar_event": "tasks",
    "delete_calendar_event": "tasks",

    # Maintenance
    "add_appliance": "maintenance",
    "list_appliances": "maintenance",
    "get_appliance": "maintenance",
    "update_appliance": "maintenance",
    "delete_appliance": "maintenance",

    "report_issue":"maintenance",
    "list_issues":"maintenance",
    "get_issue": "maintenance",
    "update_issue": "maintenance",
    "delete_issue": "maintenance",

    "log_repair":"maintenance",
    "list_repairs": "maintenance",
    "get_repair": "maintenance",
    "update_repair": "maintenance",
    "delete_repair": "maintenance",

    # Finance
    "log_expense":"finance",
    "get_expense": "finance",
    "update_expense": "finance",
    "delete_expense": "finance",
    "list_expenses":"finance",

    "create_budget":"finance",
    "list_budgets": "finance",
    "get_budget": "finance",
    "update_budget": "finance",
    "delete_budget": "finance",

    "create_recurring_bill": "finance",
    "list_recurring_bills": "finance",
    "get_recurring_bill": "finance",
    "update_recurring_bill": "finance",
    "delete_recurring_bill": "finance",

    # Documents
    "create_document": "documents",
    "list_documents": "documents",
    "get_document": "documents",
    "update_document": "documents",
    "delete_document": "documents",
}
# (domain, tool_name) -> minimum role. Anything NOT listed here defaults to
# DEFAULT_MIN_ROLE (fail-closed: a new tool needs an explicit, reviewed entry
# before a lower-privileged role can use it).
TOOL_PERMISSIONS: Dict[Tuple[str, str], HouseholdRole] = {
    # Finance — money-affecting actions stay Adult+; reading is Adult+ too,
    # since balances/spending are treated as sensitive by default.
    # Expenses
    ("finance", "log_expense"): HouseholdRole.ADULT,
    ("finance", "list_expenses"): HouseholdRole.ADULT,
    ("finance", "get_expense"): HouseholdRole.ADULT,
    ("finance", "update_expense"): HouseholdRole.ADULT,
    ("finance", "delete_expense"): HouseholdRole.ADULT,
    # Budgets
    ("finance", "create_budget"): HouseholdRole.ADULT,
    ("finance", "list_budgets"): HouseholdRole.ADULT,
    ("finance", "get_budget"): HouseholdRole.ADULT,
    ("finance", "update_budget"): HouseholdRole.ADULT,
    ("finance", "delete_budget"): HouseholdRole.ADULT,
    # Recurring bills
    ("finance", "create_recurring_bill"): HouseholdRole.ADULT,
    ("finance", "list_recurring_bills"): HouseholdRole.ADULT,
    ("finance", "get_recurring_bill"): HouseholdRole.ADULT,
    ("finance", "update_recurring_bill"): HouseholdRole.ADULT,
    ("finance", "delete_recurring_bill"): HouseholdRole.ADULT,
    # Tasks — kids can log/claim/complete chores, not just Admins.
    ("tasks", "create_task"): HouseholdRole.ADULT,
    ("tasks", "complete_task"): HouseholdRole.ADULT,
    ("tasks", "list_tasks"): HouseholdRole.ADULT,
    ("tasks", "get_task"): HouseholdRole.ADULT,
    ("tasks", "update_task"): HouseholdRole.ADULT,
    ("tasks", "delete_task"): HouseholdRole.ADULT,
    # Calendar events
    ("tasks", "create_calendar_event"): HouseholdRole.ADULT,
    ("tasks", "list_calendar_events"): HouseholdRole.ADULT,
    ("tasks", "get_calendar_event"): HouseholdRole.ADULT,
    ("tasks", "update_calendar_event"): HouseholdRole.ADULT,
    ("tasks", "delete_calendar_event"): HouseholdRole.ADULT,
    # Food/inventory — low stakes; anyone active can touch the grocery list.
    ("food", "add_grocery_item"): HouseholdRole.CHILD,
    ("food", "list_grocery_items"): HouseholdRole.CHILD,
    ("food", "get_grocery_item"): HouseholdRole.CHILD,
    ("food", "update_grocery_item"): HouseholdRole.CHILD,
    ("food", "delete_grocery_item"): HouseholdRole.CHILD,
    ("food", "mark_purchased"): HouseholdRole.CHILD,
    ("food", "list_inventory"): HouseholdRole.CHILD,
    # Inventory
    ("food", "add_inventory_item"): HouseholdRole.CHILD,
    ("food", "list_inventory"): HouseholdRole.CHILD,
    ("food", "get_inventory_item"): HouseholdRole.CHILD,
    ("food", "update_inventory_item"): HouseholdRole.CHILD,
    ("food", "delete_inventory_item"): HouseholdRole.CHILD,
    # Appliances
    ("maintenance", "add_appliance"): HouseholdRole.ADULT,
    ("maintenance", "list_appliances"): HouseholdRole.CHILD,
    ("maintenance", "get_appliance"): HouseholdRole.CHILD,
    ("maintenance", "update_appliance"): HouseholdRole.ADULT,
    ("maintenance", "delete_appliance"): HouseholdRole.ADULT,
    # Maintenance issues
    ("maintenance", "report_issue"): HouseholdRole.CHILD,
    ("maintenance", "list_issues"): HouseholdRole.CHILD,
    ("maintenance", "get_issue"): HouseholdRole.CHILD,
    ("maintenance", "update_issue"): HouseholdRole.CHILD,
    ("maintenance", "delete_issue"): HouseholdRole.CHILD,
    # Repairs
    ("maintenance", "log_repair"): HouseholdRole.ADULT,
    ("maintenance", "list_repairs"): HouseholdRole.CHILD,
    ("maintenance", "get_repair"): HouseholdRole.CHILD,
    ("maintenance", "update_repair"): HouseholdRole.ADULT,
    ("maintenance", "delete_repair"): HouseholdRole.ADULT,
    # Documents
    ("documents", "create_document"): HouseholdRole.ADULT,
    ("documents", "list_documents"): HouseholdRole.ADULT,
    ("documents", "get_document"): HouseholdRole.ADULT,
    ("documents", "update_document"): HouseholdRole.ADULT,
    ("documents", "delete_document"): HouseholdRole.ADULT,

}

DEFAULT_MIN_ROLE = HouseholdRole.ADULT

# Read-only document retrieval is authorized from the actual document's
# resolved min_role at retrieval time, not from the model-declared action
# domain. This prevents a generic ``documents -> Adult`` gate from blocking a
# Child from reading Food/Maintenance/Tasks documents while still keeping
# Finance Adult+. Guest may search/read only content whose resolved min_role is
# Guest, but original-file download is never allowed for Guest.
DOCUMENT_READ_TOOLS = {
    "search_documents",
    "get_document",
}
DOCUMENT_DOWNLOAD_TOOLS = {
    "get_original_document",
}

# Minimum role required to *retrieve* an embedded interaction from a given
# domain, keyed by domain rather than by whoever happened to be logged in
# when it was said. Kept separate from TOOL_PERMISSIONS because retrieval
# sensitivity is about the DATA's domain, not any one specific tool call —
# e.g. a finance conversation should be visible to any Adult, not just the
# Admin who happened to trigger it.
DOMAIN_MIN_ROLE: Dict[str, HouseholdRole] = {
    "finance": HouseholdRole.ADULT,
    "tasks": HouseholdRole.CHILD,
    "food": HouseholdRole.CHILD,
    "maintenance": HouseholdRole.CHILD,
    "documents": HouseholdRole.ADULT,
    "general": HouseholdRole.GUEST,
}

def is_authorized(
    role_value: str,
    domain: str,
    tool_name: str,
) -> bool:
    """Return True if the user's role may execute this tool in this domain.

    Read-only document retrieval is a special case: the model-proposed action
    domain is not trusted as the document authorization boundary. The
    retrieval layer resolves the actual document and enforces its min_role.
    """

    # 1. Validate the user's role before any special-case authorization.
    try:
        role = HouseholdRole(role_value)
    except (TypeError, ValueError):
        return False

    # 2. Read-only document access is authorized against the actual document
    # inside app.rag.document_retrieval. Allow the call to reach that gate.
    if tool_name in DOCUMENT_READ_TOOLS:
        return True

    # Guest can never receive an original-document download link. Child, Adult
    # and Admin may reach the retrieval layer, which still enforces the actual
    # document's min_role before generating a signed URL.
    if tool_name in DOCUMENT_DOWNLOAD_TOOLS:
        return role != HouseholdRole.GUEST

    # 3. Verify that every other tool belongs to the routed domain.
    tool_domain = TOOL_DOMAINS.get(tool_name)

    if tool_domain is None:
        # Unknown tools fail closed.
        return False

    if tool_domain != domain:
        # Tool/domain mismatch fails closed.
        return False

    # 4. Check the minimum role for this domain/tool pair.
    min_role = TOOL_PERMISSIONS.get(
        (domain, tool_name),
        DEFAULT_MIN_ROLE,
    )

    return ROLE_RANK[role] >= ROLE_RANK[min_role]


def domain_min_role(domain: str) -> HouseholdRole:
    """Minimum role that should be able to retrieve embedded content from this domain."""
    return DOMAIN_MIN_ROLE.get(domain, DEFAULT_MIN_ROLE)

SUPPORTED_DOCUMENT_UPLOAD_DOMAINS = {
    "finance",
    "food",
    "maintenance",
    "tasks",
}


def can_upload_document(
    role_value: str,
    document_domain: str,
) -> bool:
    """
    Return True when this household role may submit a document classified
    into ``document_domain``.

    This is an intake authorization boundary, not an execution permission.
    It reuses the domain visibility hierarchy already used by retrieval:

        finance      -> Adult+
        food         -> Child+
        maintenance  -> Child+
        tasks        -> Child+

    Unknown, ambiguous, irrelevant, and unsupported classifications fail
    closed. Passing this gate never grants permission to mutate data.
    """

    normalized_domain = str(document_domain or "").strip().lower()

    if normalized_domain not in SUPPORTED_DOCUMENT_UPLOAD_DOMAINS:
        return False

    try:
        role = HouseholdRole(role_value)
    except (TypeError, ValueError):
        return False

    min_role = domain_min_role(normalized_domain)

    return ROLE_RANK[role] >= ROLE_RANK[min_role]


def can_review_unclassified_document(
    role_value: str,
) -> bool:
    """Allow ambiguous intake only for roles authorized in every domain.

    A low-confidence classifier cannot safely choose a domain-specific RBAC
    rule. The upload may continue to explicit human review only when the
    caller could upload a document in *all* supported document domains. This
    currently limits the path to Adult/Admin without hard-coding role names.

    This permission does not approve permanent storage or any derived action.
    Irrelevant and unsupported classifications are rejected before this policy
    is consulted.
    """

    return all(
        can_upload_document(
            role_value,
            domain,
        )
        for domain in sorted(
            SUPPORTED_DOCUMENT_UPLOAD_DOMAINS
        )
    )
