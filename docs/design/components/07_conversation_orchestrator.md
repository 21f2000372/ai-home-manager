# Conversation and Cross-Domain Orchestrator Component

## Story coverage

- US-2.1: convert a chat request into a task command.
- US-3.2: answer what is running low.
- US-4.2: answer budget questions.
- US-6.2: combine Inventory, Finance, and Calendar information.
- US-6.3: persist recent conversational context.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Chat Adapter" as Chat
component "Conversation API" as Api
component "Conversation Application" as ConversationApp
component "Agent Registry" as Registry
component "Intent / Plan Adapter" as Planner
component "Task Agent Adapter" as TaskAgent
component "Inventory Agent Adapter" as InventoryAgent
component "Finance Agent Adapter" as FinanceAgent
component "Calendar Agent Adapter" as CalendarAgent
component "Response Adapter" as Response
component "Conversation Memory Adapter" as Memory
component "Tenant Context Resolver" as TenantResolver
component "LLM Provider" as LLM
interface "Conversation Commands" as ConversationCommands
interface "Task Commands / Queries" as TaskPort
interface "Inventory Queries" as InventoryPort
interface "Finance Queries" as FinancePort
interface "Calendar Queries" as CalendarPort
interface "Membership Authorization" as Authorization
interface "Tenant Context" as TenantContext

Chat ..> ConversationCommands : requires
Api ..> ConversationCommands : requires
ConversationApp - ConversationCommands : provides
ConversationApp ..> Authorization : requires
ConversationApp ..> TenantContext : requires active household
ConversationApp ..> Planner : uses
ConversationApp ..> Registry : resolves agents
Registry ..> TaskAgent
Registry ..> InventoryAgent
Registry ..> FinanceAgent
Registry ..> CalendarAgent
TaskAgent ..> TaskPort : requires
InventoryAgent ..> InventoryPort : requires
FinanceAgent ..> FinancePort : requires
CalendarAgent ..> CalendarPort : requires
TenantResolver - TenantContext : provides
ConversationApp ..> Response : uses
ConversationApp ..> Memory : persists context
Planner ..> LLM
Response ..> LLM

note right of ConversationApp
  Plan only authorized capabilities.
  Agents receive bounded commands
  or read models, never repositories.
end note
@enduml
```

## Responsibilities and rules

- `Intent Classifier` identifies task, inventory, finance, calendar, or cross-domain intent.
- `Plan Builder` creates a small execution plan and rechecks authorization for every capability.
- Agents translate language into domain commands or bounded read queries; they do not own domain state.
- `Response Synthesizer` combines results and clearly reports unavailable or denied information.
- `Conversation Memory` persists `AgentInteraction` records scoped to the user, household, and session.

The orchestrator depends on ports, not domain repositories. This keeps LLM behavior replaceable and prevents prompt-driven code from bypassing RBAC.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class Conversation {
  +conversationId: UUID
  +tenantId: UUID
  +userId: UUID
  +sessionId: UUID
}
class AgentInteraction {
  +interactionId: UUID
  +tenantId: UUID
  +intent: String
  +response: String
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface TenantContextResolver {
  +resolve(userId: UUID, tenantId: UUID): TenantContext
}
interface DomainQueryPort {
  +query(context: TenantContext, request): ReadModel
}
class ConversationService {
  +answer(context: TenantContext, message: String): Response
}
class PlanBuilder {
  +build(context: TenantContext, intent: Intent): Plan
}
class AuthorizationPolicy {
  +authorize(context: TenantContext, capability: Capability): Boolean
}
class MemoryRepository {
  +save(interaction: AgentInteraction)
  +recent(context: TenantContext): List<AgentInteraction>
}

Conversation "1" -- "0..*" AgentInteraction
ConversationService ..> TenantContextResolver
ConversationService ..> PlanBuilder
ConversationService ..> AuthorizationPolicy
ConversationService ..> DomainQueryPort
ConversationService ..> MemoryRepository
PlanBuilder ..> AuthorizationPolicy
MemoryRepository ..> TenantContext
TenantContext ..> Conversation : scopes
TenantContext ..> AgentInteraction : scopes
@enduml
```

The active tenant is resolved before planning and passed to every agent port. Conversation memory is keyed by both `tenantId` and `sessionId`, so context from one household cannot leak into another household's answer.

## Behavior diagram: cross-domain question

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Adult member" as User
participant "Chat Adapter" as Chat
participant "Conversation Service" as Conversation
participant "Tenant Context Resolver" as Resolver
participant "Authorization Policy" as Authorization
participant "Plan Builder" as Planner
participant "Inventory Query Port" as Inventory
participant "Finance Query Port" as Finance
participant "Calendar Query Port" as Calendar
participant "Conversation Memory" as Memory

User -> Chat: Ask cross-domain question
Chat -> Conversation: message + tenant selector
Conversation -> Resolver: Resolve user membership
Resolver --> Conversation: TenantContext
Conversation -> Authorization: Authorize capabilities
Authorization --> Conversation: allowed capabilities
Conversation -> Planner: Build bounded plan
Planner -> Inventory: Query(TenantContext, needs)
Inventory --> Planner: inventory read model
Planner -> Finance: Query(TenantContext, budget)
Finance --> Planner: finance read model
Planner -> Calendar: Query(TenantContext, schedule)
Calendar --> Planner: calendar read model
Planner --> Conversation: combined answer inputs
Conversation -> Memory: Save AgentInteraction(tenantId, sessionId)
Memory --> Conversation: saved
Conversation --> Chat: response and warnings
Chat --> User: Answer
@enduml
```

The orchestrator authorizes the plan before calling any domain port and passes the same tenant context to every query, preventing cross-household synthesis or memory leakage.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Conversation Orchestrator" as Boundary {
  component "Intent Classifier" as Intent
  component "Plan Builder" as Planner
  component "Agent Registry" as Registry
  component "Task Agent" as TaskAgent
  component "Inventory Agent" as InventoryAgent
  component "Finance Agent" as FinanceAgent
  component "Calendar Agent" as CalendarAgent
  component "Response Synthesizer" as Response
  component "Memory Service" as Memory
  component "Conversation Port" as ConversationPort
  component "Task Port" as TaskPort
  component "Inventory Port" as InventoryPort
  component "Finance Port" as FinancePort
  component "Calendar Port" as CalendarPort

  ConversationPort --> Intent
  Intent --> Planner
  Planner --> Registry
  Registry --> TaskAgent
  Registry --> InventoryAgent
  Registry --> FinanceAgent
  Registry --> CalendarAgent
  TaskAgent --> TaskPort
  InventoryAgent --> InventoryPort
  FinanceAgent --> FinancePort
  CalendarAgent --> CalendarPort
  TaskAgent --> Response
  InventoryAgent --> Response
  FinanceAgent --> Response
  CalendarAgent --> Response
  Response --> Memory
}
interface "Conversation Commands" as Contract
interface "Task Commands and Queries" as Tasks
interface "Inventory Queries" as Inventory
interface "Finance Queries" as Finance
interface "Calendar Queries" as Calendar
Contract --> Boundary.ConversationPort
Boundary.TaskPort --> Tasks
Boundary.InventoryPort --> Inventory
Boundary.FinancePort --> Finance
Boundary.CalendarPort --> Calendar
@enduml
```

The internal structure keeps planning, agent selection, domain adapters, response synthesis, and memory separate. Each agent requires only its own narrow interface, so adding a new domain agent does not change existing domain components.
