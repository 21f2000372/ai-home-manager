# Food and Inventory Component

## Story coverage

- US-3.1: low-stock alerts.
- US-3.2: ask what is running low.
- US-3.3: build a grocery list from a recipe or meal plan.
- US-3.4: mark grocery items purchased.
- US-3.5: recurring daily commodities such as milk, bread, or eggs.
- US-3.6: update inventory and optionally record purchase cost.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Food & Inventory API" as Api
component "Inventory Application" as InventoryApp
component "Stock Threshold Policy" as StockPolicy
component "Recurrence Policy" as Repeat
component "Inventory Repository Adapter" as InventoryRepo
component "Event Publisher Adapter" as Events
component "Tenant Isolation Policy" as TenantPolicy
database "Inventory & Grocery Store" as Store
interface "Inventory Commands" as InventoryCommands
interface "Inventory Queries" as InventoryQueries
interface "Membership Queries" as Membership
interface "Expense Commands" as Expenses
interface "Inventory Events" as InventoryEvents
interface "Tenant Context" as TenantContext

Api ..> InventoryCommands : requires
Api ..> InventoryQueries : requires
InventoryApp - InventoryCommands : provides
InventoryApp - InventoryQueries : provides
InventoryApp ..> Membership : requires
InventoryApp ..> TenantContext : requires active household
InventoryApp ..> StockPolicy : applies
InventoryApp ..> Repeat : applies
InventoryApp ..> InventoryRepo : persists
InventoryApp ..> Expenses : optional purchase cost
InventoryApp ..> InventoryEvents : publishes
InventoryRepo ..> Store
TenantPolicy ..> Store : tenant-scoped queries
Events ..> InventoryEvents : consumes

note right of Repeat
  A recurring item produces a dated
  grocery occurrence. The occurrence
  is idempotent for household + rule + date.
end note
@enduml
```

## Responsibilities and rules

- `Inventory Query Handler` returns low-stock and out-of-stock read models.
- `Grocery List Handler` manages one-off items and recipe or meal-plan requirements.
- `Commodity Rule Handler` stores quantity, unit, preferred brand, threshold, and daily/custom recurrence.
- `Purchase Handler` marks an occurrence purchased or skipped, updates stock, and optionally calls the Finance expense port.
- `Stock Threshold Policy` emits a low-stock notification without coupling inventory to a notification provider.

The component owns inventory and grocery state. Finance receives a purchase-cost command through a port; it does not receive direct access to the inventory database.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class InventoryItem {
  +itemId: UUID
  +tenantId: UUID
  +name: String
  +quantity: Decimal
  +lowStockThreshold: Decimal
}
class GroceryItem {
  +groceryItemId: UUID
  +tenantId: UUID
  +name: String
  +purchased: Boolean
}
class CommodityRule {
  +ruleId: UUID
  +tenantId: UUID
  +quantity: Decimal
  +unit: String
  +schedule: String
}
class PurchaseOccurrence {
  +occurrenceId: UUID
  +tenantId: UUID
  +occurrenceDate: Date
  +status: PurchaseStatus
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface InventoryRepository {
  +findItem(tenantId: UUID, itemId: UUID): InventoryItem
  +save(item: InventoryItem)
}
interface ExpenseCommands {
  +recordCommodityCost(tenantId: UUID, amount: Money)
}
class InventoryService {
  +markPurchased(context: TenantContext, occurrenceId: UUID): PurchaseOccurrence
  +lowStock(context: TenantContext): List<InventoryItem>
}
class StockPolicy {
  +isLowStock(item: InventoryItem): Boolean
}
class CommodityPolicy {
  +createOccurrence(rule: CommodityRule, date: Date): PurchaseOccurrence
}

CommodityRule "1" -- "0..*" PurchaseOccurrence
PurchaseOccurrence "0..1" --> InventoryItem
InventoryService ..> InventoryRepository
InventoryService ..> ExpenseCommands
InventoryService ..> StockPolicy
InventoryService ..> CommodityPolicy
InventoryService ..> TenantContext
TenantContext ..> InventoryItem : scopes
TenantContext ..> GroceryItem : scopes
TenantContext ..> CommodityRule : scopes
@enduml
```

Recurring milk, bread, or egg rules generate occurrences using a tenant-scoped idempotency key. Inventory updates and optional expenses are emitted only for the active household tenant.

## Behavior diagram: recurring commodity purchase

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

participant "Tenant Scheduler" as Scheduler
participant "Inventory Application" as App
participant "Commodity Policy" as Policy
participant "Inventory Repository" as Repository
participant "Inventory Aggregate" as Aggregate
participant "Finance Port" as Finance
participant "Notification Port" as Notify

Scheduler -> App: Generate occurrence(tenantId, ruleId, date)
App -> Policy: Calculate occurrence
Policy --> App: occurrence key
App -> Repository: Create if key absent
Repository --> App: created or already exists
alt occurrence created
  App -> Notify: Publish grocery occurrence
  Notify --> App: delivered
end
participant "Household Member" as Member
Member -> App: Mark purchased(tenantId, occurrenceId, cost?)
App -> Aggregate: Increase stock and close occurrence
Aggregate --> App: inventory changed
opt cost supplied
  App -> Finance: Record cost(tenantId, amount)
  Finance --> App: expense recorded
end
App --> Member: Purchase completed
@enduml
```

The occurrence key includes tenant, recurrence rule, and date, making scheduled jobs idempotent independently for every household.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Food & Inventory" as Boundary {
  component "Stock Query Service" as Stock
  component "Grocery List Service" as Grocery
  component "Commodity Recurrence Service" as Commodity
  component "Purchase Service" as Purchase
  component "Meal Requirement Service" as Meal
  component "Inventory Aggregate" as Aggregate
  component "Stock Threshold Policy" as Threshold
  component "Inventory Port" as InventoryPort
  component "Purchase Cost Port" as CostPort
  component "Inventory Events Port" as EventPort

  InventoryPort --> Stock
  InventoryPort --> Grocery
  InventoryPort --> Commodity
  InventoryPort --> Purchase
  InventoryPort --> Meal
  Stock --> Aggregate
  Stock --> Threshold
  Grocery --> Aggregate
  Commodity --> Aggregate
  Purchase --> Aggregate
  Purchase --> CostPort
  Meal --> Aggregate
  Aggregate --> EventPort
}
interface "Inventory Commands and Queries" as Contract
interface "Expense Commands" as Expense
interface "Inventory Events" as Events
Contract --> Boundary.InventoryPort
Boundary.CostPort --> Expense
Boundary.EventPort --> Events
@enduml
```

The boundary separates ordinary grocery items, recurring commodities, meal requirements, stock queries, and purchase completion. All mutations pass through the inventory aggregate, which keeps stock updates and idempotent occurrence handling consistent.
