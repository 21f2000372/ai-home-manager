from __future__ import annotations

from app.ai.agents.tools import document_tools
from app.ai.agents.tools import finance_tools
from app.ai.agents.tools import food_tools
from app.ai.agents.tools import maintenance_tools
from app.ai.agents.tools import tasks_tools


TOOLSETS = {
    "finance": finance_tools.TOOLS,
    "tasks": tasks_tools.TOOLS,
    "food": food_tools.TOOLS,
    "maintenance": maintenance_tools.TOOLS,
    "documents": document_tools.TOOLS,
    "general": [],
}


ALL_TOOLS_BY_NAME = {
    **finance_tools.TOOLS_BY_NAME,
    **tasks_tools.TOOLS_BY_NAME,
    **food_tools.TOOLS_BY_NAME,
    **maintenance_tools.TOOLS_BY_NAME,
    **document_tools.TOOLS_BY_NAME,
}

_ACTION_TOOL_HINTS = {
    "add grocery": [
        "add_grocery_item",
    ],

    "grocery item": [
        "add_grocery_item",
        "update_grocery_item",
        "delete_grocery_item",
        "mark_purchased",
        "get_grocery_item",
    ],

    "grocery list": [
        "add_grocery_item",
        "list_grocery_items",
        "update_grocery_item",
        "delete_grocery_item",
        "mark_purchased",
    ],

    "inventory": [
        "add_inventory_item",
        "update_inventory_item",
        "delete_inventory_item",
        "get_inventory_item",
        "list_inventory",
    ],

    "expense": [
        "log_expense",
        "get_expense",
        "update_expense",
        "delete_expense",
        "list_expenses",
    ],

    "budget": [
        "create_budget",
        "get_budget",
        "update_budget",
        "delete_budget",
        "list_budgets",
    ],

    "recurring bill": [
        "create_recurring_bill",
        "get_recurring_bill",
        "update_recurring_bill",
        "delete_recurring_bill",
        "list_recurring_bills",
    ],

    "task": [
        "create_task",
        "get_task",
        "update_task",
        "delete_task",
        "complete_task",
        "list_tasks",
    ],

    "calendar": [
        "create_calendar_event",
        "get_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "list_calendar_events",
    ],

    "appliance": [
        "add_appliance",
        "get_appliance",
        "update_appliance",
        "delete_appliance",
        "list_appliances",
    ],

    "issue": [
        "report_issue",
        "get_issue",
        "update_issue",
        "delete_issue",
        "list_issues",
    ],

    "repair": [
        "log_repair",
        "get_repair",
        "update_repair",
        "delete_repair",
        "list_repairs",
    ],

    "document": [
        "create_document",
        "get_document",
        "update_document",
        "delete_document",
        "list_documents",
    ],
}


def get_tools_for_action(
    domain: str,
    intent: str = "",
    description: str = "",
):
    """
    Expose only tools likely to be relevant to the current action.

    Falls back to the whole domain toolset if no safe match is found.
    """

    haystack = (
        f"{intent} {description}"
    ).casefold()

    domain_tools = TOOLSETS.get(
        domain,
        [],
    )

    domain_tool_names = {
        tool.name
        for tool in domain_tools
    }

    selected_names: list[str] = []

    for phrase, names in _ACTION_TOOL_HINTS.items():

        if phrase not in haystack:
            continue

        for name in names:

            if name in domain_tool_names:
                selected_names.append(
                    name
                )

    # Don't accidentally remove necessary tools if our heuristic
    # doesn't recognize the planner's wording.
    if not selected_names:
        return domain_tools

    result = []
    seen = set()

    for name in selected_names:

        if name in seen:
            continue

        seen.add(name)

        tool = ALL_TOOLS_BY_NAME.get(
            name
        )

        if tool is not None:
            result.append(tool)

    return result