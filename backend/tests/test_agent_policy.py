from app.ai.agents.permissions import TOOL_DOMAINS, TOOL_PERMISSIONS, is_authorized
from app.ai.agents.domain_mesh import allowed_tool_names_for_domain, get_domain_spec
from app.ai.agents.entity_resolution import find_entity_matches, is_ambiguous_match
from app.ai.agents.planner import PlannedActionModel, detect_single_action
from app.ai.agents.prompt_builder import PromptContext, ToolPromptBuilder
from app.ai.agents.tool_catalog import ToolCatalogRepository
from app.ai.agents.tools import ALL_TOOLS_BY_NAME
from app.models.enums import HouseholdRole


def test_planner_domain_and_permissions_cover_registered_tools():
    assert "documents" in PlannedActionModel.model_fields["domain"].description
    assert all(name in TOOL_DOMAINS for name in ALL_TOOLS_BY_NAME)
    assert all((TOOL_DOMAINS[name], name) in TOOL_PERMISSIONS for name in ALL_TOOLS_BY_NAME)


def test_permission_aliases_fail_closed():
    assert is_authorized("Adult", "maintenance", "log_repair")
    assert is_authorized("Adult", "finance", "create_budget")
    assert is_authorized("Adult", "finance", "extract_bill_information")
    assert is_authorized("Adult", "documents", "log_expense")
    assert not is_authorized("Adult", "maintenance", "log repair")
    assert not is_authorized("Adult", "finance", "create_budgets")
    assert not is_authorized("Adult", "tasks", "log_expense")


def test_prompt_builder_is_compact_and_bounded():
    prompt = ToolPromptBuilder().build(PromptContext(
        role="Adult",
        tenant_id="tenant-123",
        action={"domain": "finance", "intent": "log expense", "description": "Record ₹500."},
        candidates=[{"name": "log_expense", "purpose": "Record an expense."}],
        entity_context=["category: groceries"],
        result="Expense logged successfully",
    ))
    assert "Available domains:" not in prompt
    assert "log_expense" in prompt
    assert "tenant-123" in prompt
    assert len(prompt) < 3000


def test_tool_catalog_filters_domain_and_role():
    class FakeRag:
        def retrieve(self, query_text, **kwargs):
            return {
                "documents": [["Tool: update_budget. Domain: finance. Edit a budget.", "Tool: mark_purchased. Domain: food. Mark purchased."]],
                "metadatas": [[
                    {"tool_name": "update_budget", "tool_domain": "finance"},
                    {"tool_name": "mark_purchased", "tool_domain": "food"},
                ]],
            }

    results = ToolCatalogRepository(FakeRag()).search(
        "mark purchased", role=HouseholdRole.CHILD, tenant_id="tenant-1", domain="food"
    )
    assert [item["tool_name"] for item in results] == ["mark_purchased"]


def test_single_action_detector_rejects_multi_action_requests():
    assert detect_single_action("Add milk to my grocery list")["domain"] == "food"
    assert detect_single_action("Extract the total from this electricity bill")["domain"] == "documents"
    assert detect_single_action("Add milk and create a task to clean") is None


def test_domain_mesh_exposes_owned_and_public_proxy_tools():
    finance = get_domain_spec("finance")
    documents = get_domain_spec("documents")

    assert "log_expense" in finance.owned_tools
    assert "extract_bill_information" in finance.public_proxy_tools
    assert "log_expense" in documents.public_proxy_tools
    assert "extract_bill_information" in allowed_tool_names_for_domain("finance")
    assert "update_inventory_item" not in allowed_tool_names_for_domain("finance")


def test_task_search_tools_are_registered_for_tasks_domain():
    assert "search_tasks" in allowed_tool_names_for_domain("tasks")
    assert "update_task_by_search" in allowed_tool_names_for_domain("tasks")
    assert is_authorized("Child", "tasks", "search_tasks")
    assert is_authorized("Child", "tasks", "update_task_by_search")


def test_entity_resolution_scores_text_fields_and_detects_ambiguity():
    class Item:
        def __init__(self, item_id, title, description):
            self.item_id = item_id
            self.title = title
            self.description = description

    rows = [
        Item("1", "book LPG gas", "home utility refill"),
        Item("2", "book cylinder", "LPG gas refill"),
    ]

    matches = find_entity_matches(
        rows=rows,
        query="book LPG gas",
        id_getter=lambda item: item.item_id,
        label_getter=lambda item: item.title,
        field_getters=[lambda item: f"{item.title} {item.description}"],
    )

    assert matches[0].entity_id == "1"
    assert is_ambiguous_match(matches)
