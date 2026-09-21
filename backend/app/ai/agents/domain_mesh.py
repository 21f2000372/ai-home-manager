from __future__ import annotations

from dataclasses import dataclass, field


DomainName = str


@dataclass(frozen=True)
class DomainAgentSpec:
    """Contract for one isolated domain agent in the household mesh."""

    name: DomainName
    purpose: str
    owned_tools: tuple[str, ...] = ()
    public_proxy_tools: tuple[str, ...] = ()
    prompt_rules: tuple[str, ...] = ()
    shared_services: tuple[str, ...] = ("core_database_mcp",)
    can_delegate_to: tuple[DomainName, ...] = ()
    extraction_targets: tuple[str, ...] = ()

    @property
    def exposed_tools(self) -> tuple[str, ...]:
        return self.owned_tools + self.public_proxy_tools


DOMAIN_AGENT_SPECS: dict[DomainName, DomainAgentSpec] = {
    "finance": DomainAgentSpec(
        name="finance",
        purpose="Expenses, budgets, recurring bills, payments, and bill-derived money records.",
        owned_tools=(
            "log_expense",
            "list_expenses",
            "get_expense",
            "update_expense",
            "delete_expense",
            "create_budget",
            "list_budgets",
            "get_budget",
            "update_budget",
            "delete_budget",
            "create_recurring_bill",
            "list_recurring_bills",
            "get_recurring_bill",
            "update_recurring_bill",
            "delete_recurring_bill",
        ),
        public_proxy_tools=(
            "get_document",
            "extract_bill_information",
            "link_document_to_record",
        ),
        prompt_rules=(
            "Use finance tools for actual spending, budgets, and recurring obligations.",
            "When a bill or receipt document is involved, read/extract document facts before logging money.",
            "Do not update document metadata except through the document domain or public document proxy tools.",
        ),
        can_delegate_to=("documents",),
        extraction_targets=("bill", "receipt"),
    ),
    "tasks": DomainAgentSpec(
        name="tasks",
        purpose="To-dos, chores, reminders, and calendar-like household activities.",
        owned_tools=(
            "create_task",
            "list_tasks",
            "search_tasks",
            "get_task",
            "update_task",
            "update_task_by_search",
            "delete_task",
            "complete_task",
            "create_calendar_event",
            "list_calendar_events",
            "get_calendar_event",
            "update_calendar_event",
            "delete_calendar_event",
        ),
        prompt_rules=(
            "Use task tools for reminders, chores, and scheduling.",
            "When the user identifies a task by title or description instead of id, search first or use update_task_by_search.",
            "If task search returns multiple plausible matches, ask for clarification instead of updating.",
            "Resolve relative dates to ISO datetimes before calling task tools.",
        ),
    ),
    "food": DomainAgentSpec(
        name="food",
        purpose="Groceries and household inventory.",
        owned_tools=(
            "add_grocery_item",
            "list_grocery_items",
            "get_grocery_item",
            "update_grocery_item",
            "delete_grocery_item",
            "mark_purchased",
            "add_inventory_item",
            "list_inventory",
            "get_inventory_item",
            "update_inventory_item",
            "delete_inventory_item",
        ),
        prompt_rules=(
            "Keep grocery-list actions separate from stocked household inventory actions.",
            "Never create duplicates when the user is modifying an existing item.",
        ),
    ),
    "maintenance": DomainAgentSpec(
        name="maintenance",
        purpose="Appliances, household issues, repairs, and maintenance history.",
        owned_tools=(
            "add_appliance",
            "list_appliances",
            "get_appliance",
            "update_appliance",
            "delete_appliance",
            "report_issue",
            "list_issues",
            "get_issue",
            "update_issue",
            "delete_issue",
            "log_repair",
            "list_repairs",
            "get_repair",
            "update_repair",
            "delete_repair",
        ),
        public_proxy_tools=(
            "get_document",
            "link_document_to_record",
        ),
        prompt_rules=(
            "Use appliance tools for durable household assets.",
            "Use issue tools for reported problems, and repair tools for completed or planned repairs.",
            "Warranty or invoice documents may be linked through public document proxy tools.",
        ),
        can_delegate_to=("documents",),
    ),
    "documents": DomainAgentSpec(
        name="documents",
        purpose="Document metadata, bill/receipt records, warranties, and document extraction.",
        owned_tools=(
            "create_document",
            "list_documents",
            "get_document",
            "update_document",
            "delete_document",
            "extract_bill_information",
            "link_document_to_record",
            "list_document_links",
        ),
        public_proxy_tools=(
            "log_expense",
            "create_recurring_bill",
        ),
        prompt_rules=(
            "Document tools manage metadata and extracted facts, not binary upload storage.",
            "For bills, extract payee, amount, due date, invoice number, and account/reference when present.",
            "If the user wants a bill saved as money owed or paid, use the finance public proxy tools after extraction.",
        ),
        can_delegate_to=("finance", "maintenance"),
        extraction_targets=("bill", "receipt", "warranty"),
    ),
    "general": DomainAgentSpec(
        name="general",
        purpose="Questions, discussion, and ambiguous requests that do not need household state changes.",
    ),
}


def get_domain_spec(domain: str | None) -> DomainAgentSpec:
    return DOMAIN_AGENT_SPECS.get(domain or "general", DOMAIN_AGENT_SPECS["general"])


def domain_names() -> tuple[str, ...]:
    return tuple(DOMAIN_AGENT_SPECS)


def allowed_tool_names_for_domain(domain: str | None) -> set[str]:
    return set(get_domain_spec(domain).exposed_tools)


def build_mesh_summary(domain: str | None) -> str:
    spec = get_domain_spec(domain)
    lines = [
        f"Domain agent: {spec.name}",
        f"Purpose: {spec.purpose}",
        "Shared MCP services: " + ", ".join(spec.shared_services),
        "Owned tools: " + (", ".join(spec.owned_tools) or "none"),
        "Public proxy tools: " + (", ".join(spec.public_proxy_tools) or "none"),
    ]
    if spec.can_delegate_to:
        lines.append("Allowed delegation targets: " + ", ".join(spec.can_delegate_to))
    if spec.extraction_targets:
        lines.append("Extraction targets: " + ", ".join(spec.extraction_targets))
    if spec.prompt_rules:
        lines.append("Domain rules:")
        lines.extend(f"- {rule}" for rule in spec.prompt_rules)
    return "\n".join(lines)
