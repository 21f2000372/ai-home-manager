# Food and Inventory Agent Workflow

## Purpose and ownership

The Inventory Agent manages stock, low-stock queries, grocery lists, meal requirements, recurring commodities, and purchase completion. It owns stock state and occurrence idempotency.

**Ports:** `Inventory Commands`, `Inventory Queries`, `Membership Queries`, `Expense Commands`, `Inventory Events`.

## CRUD operations

| CRUD | Inventory-owned operation | WhatsApp event |
|---|---|---|
| Create | Add inventory item, grocery item, or commodity rule | `InventoryItemCreated`, `GroceryItemCreated`, or `CommodityRuleCreated` |
| Read | Read stock, low-stock items, grocery list, or occurrences | Optional redacted grocery/stock summary on request |
| Update | Adjust stock, edit item threshold, mark purchased, or skip occurrence | `StockUpdated`, `PurchaseCompleted`, or `GroceryItemUpdated` |
| Delete | Remove item, grocery entry, or recurrence rule | `InventoryItemDeleted` or `CommodityRuleDeleted` |

The Inventory application service performs CRUD and emits events after commit. WhatsApp messages contain item labels and safe status only; cost details are sent only to recipients authorized for Finance data.

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center
actor "Household member" as User
participant "Inventory Agent" as Agent
participant "Authorization" as Auth
participant "Inventory Application" as App
participant "Stock + Recurrence Policies" as Rules
database "Inventory Store" as Store
participant "Finance Port" as Finance
participant "Notification Port" as Notify

User -> Agent: create/read/update/delete inventory data
Agent -> Auth: authorize inventory capability
alt denied
  Auth --> Agent: deny
  Agent --> User: safe denial
else allowed
  Auth --> Agent: TenantContext
  Agent -> App: typed inventory command/query
  App -> Rules: evaluate threshold or occurrence
  App -> Store: tenant-scoped read/write
  alt purchase with cost
    App -> Finance: record cost through port
    Finance --> App: accepted or pending review
  end
  App -> Notify: low-stock or purchase event
  App --> Agent: bounded result
  Agent --> User: result
end

participant "Tenant Scheduler" as Scheduler
Scheduler -> App: generate occurrence(tenant, rule, date)
App -> Store: create if idempotency key absent
@enduml
```

## Security and domain rules

- Inventory data is scoped to one tenant and role-filtered before a response is generated.
- Recurring occurrence identity is `tenantId + ruleId + occurrenceDate`.
- Marking an occurrence purchased updates stock in the same domain transaction.
- Purchase cost crosses into Finance only as a typed `record cost` command.
- Low-stock notifications contain only the household's permitted item data.
- Recipe or meal-plan requests provide requirements through a query port; the agent does not read meal or task tables.

## Cohesion and coupling

Stock thresholds, grocery occurrences, and purchase state remain inside Inventory policies and aggregates. Finance, Notifications, and the orchestrator see events or narrow ports, preserving low coupling.
