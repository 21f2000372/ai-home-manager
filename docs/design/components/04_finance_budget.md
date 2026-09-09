# Finance and Budget Component

## Story coverage

- US-4.1: parse a receipt and create a linked expense.
- US-4.2: check remaining budget.
- US-4.3: recurring bill reminders.
- US-4.4: block Child and Guest finance access before agent execution.
- US-3.6: accept optional costs from recurring commodity purchases.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Finance API" as Api
component "Finance Application" as FinanceApp
component "Finance Authorization Policy" as Authorization
component "Budget Policy" as BudgetPolicy
component "Receipt Parser Adapter" as ReceiptParser
component "Finance Repository Adapter" as Repository
component "Tenant Isolation Policy" as TenantPolicy
database "Finance Store" as Store
interface "Finance Commands" as FinanceCommands
interface "Finance Queries" as FinanceQueries
interface "Membership Queries" as Membership
interface "Document Link" as Documents
interface "Notification Events" as NotificationEvents
interface "Tenant Context" as TenantContext

Api ..> FinanceCommands : requires
Api ..> FinanceQueries : requires
FinanceApp - FinanceCommands : provides
FinanceApp - FinanceQueries : provides
FinanceApp ..> Authorization : applies
FinanceApp ..> BudgetPolicy : applies
FinanceApp ..> Membership : requires
FinanceApp ..> TenantContext : requires active household
FinanceApp ..> ReceiptParser : requires
FinanceApp ..> Documents : links receipts
FinanceApp ..> Repository : persists
FinanceApp ..> NotificationEvents : publishes
Repository ..> Store
TenantPolicy ..> Store : tenant-scoped queries

note right of FinanceApp
  Child and Guest receive 403
  for Expense, Budget, and Bill
  operations before any agent call.
end note
@enduml
```

## Responsibilities and rules

- `Finance Authorization Policy` is mandatory for every finance command and query.
- `Expense Handler` accepts parsed receipt data, manual expense data, and purchase-cost commands through separate input ports.
- `Document Link Port` associates a receipt document with `linked_domain` and `linked_record_id`.
- `Budget Query Handler` calculates remaining budget from approved expenses and configured limits.
- `Bill Handler` manages recurring bills and emits due reminders through a notification port.

The component owns expenses, budgets, and bills. It must never rely on the client hiding sensitive data.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class Expense {
  +expenseId: UUID
  +tenantId: UUID
  +amount: Money
  +category: String
  +occurredAt: DateTime
}
class Budget {
  +budgetId: UUID
  +tenantId: UUID
  +category: String
  +limit: Money
  +period: BudgetPeriod
}
class Bill {
  +billId: UUID
  +tenantId: UUID
  +dueAt: DateTime
  +recurrence: String
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface FinanceRepository {
  +findExpenses(tenantId: UUID, period: Period): List<Expense>
  +save(expense: Expense)
}
interface DocumentLink {
  +link(tenantId: UUID, domain: String, recordId: UUID)
}
class FinanceService {
  +recordExpense(context: TenantContext, expense: Expense): Expense
  +remainingBudget(context: TenantContext, category: String): Money
}
class FinanceAuthorization {
  +canAccess(context: TenantContext, action: FinanceAction): Boolean
}
class BudgetPolicy {
  +remaining(limit: Money, expenses: List<Expense>): Money
}

Budget "1" -- "0..*" Expense : category / period
FinanceService ..> FinanceRepository
FinanceService ..> DocumentLink
FinanceService ..> FinanceAuthorization
FinanceService ..> BudgetPolicy
FinanceService ..> TenantContext
TenantContext ..> Expense : scopes
TenantContext ..> Budget : scopes
TenantContext ..> Bill : scopes
@enduml
```

Finance entities always carry `tenantId`, and `FinanceAuthorization` evaluates the role inside that tenant. A Child or Guest from one household cannot access another household's financial records by changing an identifier.

## Behavior diagram: receipt expense and budget query

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Adult member" as User
participant "Finance API" as Api
participant "Finance Authorization" as Authorization
participant "Receipt Parser" as Parser
participant "Finance Service" as Finance
participant "Finance Repository" as Repository
participant "Budget Policy" as Budget

User -> Api: Upload receipt(tenantId, file)
Api -> Authorization: Check Adult finance permission
Authorization --> Api: allowed or 403
Api -> Parser: Extract expense fields
Parser --> Api: amount + category + date
Api -> Finance: Record expense(TenantContext, data)
Finance -> Repository: Save tenant-scoped expense
Repository --> Finance: expenseId
Finance --> Api: expense recorded
Api --> User: Confirmation

User -> Api: Ask remaining budget(category)
Api -> Authorization: Check finance read permission
Authorization --> Api: allowed or 403
Api -> Finance: Query budget(TenantContext, category)
Finance -> Repository: Read tenant expenses and budget
Repository --> Finance: bounded read model
Finance -> Budget: Calculate remaining
Budget --> Finance: remaining amount
Finance --> Api: budget status
Api --> User: Remaining budget
@enduml
```

Authorization is performed before both receipt parsing and budget reads, preventing protected finance work from being reached by Child or Guest members.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Finance & Budget" as Boundary {
  component "Expense Service" as Expense
  component "Budget Service" as Budget
  component "Bill Service" as Bills
  component "Finance Authorization" as Authorization
  component "Expense Aggregate" as ExpenseAggregate
  component "Budget Aggregate" as BudgetAggregate
  component "Bill Aggregate" as BillAggregate
  component "Finance Port" as FinancePort
  component "Document Link Port" as DocumentPort
  component "Finance Events Port" as EventPort

  FinancePort --> Expense
  FinancePort --> Budget
  FinancePort --> Bills
  Expense --> Authorization
  Budget --> Authorization
  Bills --> Authorization
  Expense --> ExpenseAggregate
  Budget --> BudgetAggregate
  Bills --> BillAggregate
  Expense --> DocumentPort
  Bills --> EventPort
  ExpenseAggregate --> EventPort
}
interface "Finance Commands and Queries" as Contract
interface "Domain Document Link" as Documents
interface "Finance Events" as Events
Contract --> Boundary.FinancePort
Boundary.DocumentPort --> Documents
Boundary.EventPort --> Events
@enduml
```

The finance boundary keeps expense, budget, and bill operations separate while sharing one authorization component. This makes the Child and Guest restriction enforceable for every internal path, not only for HTTP endpoints.
