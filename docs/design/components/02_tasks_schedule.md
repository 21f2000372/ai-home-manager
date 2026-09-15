# Tasks and Schedule Component

## Story coverage

- US-2.1: create a task through chat.
- US-2.2: create a task through a manual form.
- US-2.3: view assigned tasks.
- US-2.4: recurring chores.
- US-2.5 and US-2.6: shared calendar and conflict warnings.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Task & Schedule API" as Api
component "Task Application" as TaskApp
component "Task & Schedule API" as Api
component "Assignee Policy" as Assignee
component "Recurrence Policy" as Repeat
component "Conflict Policy" as Conflict
component "Task Repository Adapter" as Tasks
component "Event Publisher Adapter" as Events
component "Tenant Isolation Policy" as TenantPolicy
database "Task & Calendar Store" as Store
interface "Task Commands" as TaskCommands
interface "Task Queries" as TaskQueries
interface "Membership Queries" as Membership
interface "Task Events" as TaskEvents
interface "Tenant Context" as TenantContext

Api ..> TaskCommands : requires
Api ..> TaskQueries : requires
TaskApp - TaskCommands : provides
TaskApp - TaskQueries : provides
TaskApp ..> Membership : requires
TaskApp ..> TenantContext : requires active household
TaskApp ..> Assignee : applies
TaskApp ..> Repeat : applies
TaskApp ..> Conflict : applies
TaskApp ..> Tasks : persists
TaskApp ..> TaskEvents : publishes
Tasks ..> Store
TenantPolicy ..> Store : tenant-scoped queries
Events ..> TaskEvents : consumes

note right of TaskApp
  Chat parsing and manual form input
  both end at this same use case.
end note
@enduml
```

## Responsibilities and rules

- Chat and form adapters normalize input into one `CreateTask` command.
- `Assignee Policy` verifies that the assignee belongs to the same household.
- `Task Query Handler` applies the caller's visibility filter, including assigned-to-me views.
- `Recurrence Handler` creates idempotent occurrences for weekly chores.
- `Calendar Handler` checks time overlap before accepting a new event and returns a warning when needed.
- Guest writes are rejected by the shared authorization boundary before handlers execute.

The component owns tasks, calendar events, recurrence definitions, and conflict checks. It does not parse natural language itself; the chat adapter or orchestrator supplies a validated command.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class Task {
  +taskId: UUID
  +tenantId: UUID
  +assigneeId: UUID
  +title: String
  +dueAt: DateTime
  +status: TaskStatus
}
class CalendarEvent {
  +eventId: UUID
  +tenantId: UUID
  +startsAt: DateTime
  +endsAt: DateTime
}
class RecurrenceRule {
  +ruleId: UUID
  +tenantId: UUID
  +expression: String
  +nextOccurrence: DateTime
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface TaskRepository {
  +findByTenant(tenantId: UUID): List<Task>
  +save(task: Task)
}
interface MembershipQueries {
  +isMember(tenantId: UUID, userId: UUID): Boolean
}
class TaskService {
  +create(context: TenantContext, command: CreateTask): Task
  +listAssigned(context: TenantContext): List<Task>
}
class AssigneePolicy {
  +validate(context: TenantContext, assigneeId: UUID): Boolean
}
class ConflictPolicy {
  +hasOverlap(context: TenantContext, event: CalendarEvent): Boolean
}

Task "0..*" --> "0..1" RecurrenceRule
CalendarEvent "0..*" -- "0..1" Task
TaskService ..> TaskRepository
TaskService ..> MembershipQueries
TaskService ..> AssigneePolicy
TaskService ..> ConflictPolicy
TaskService ..> TenantContext
TenantContext ..> Task : scopes
TenantContext ..> CalendarEvent : scopes
@enduml
```

Tasks, events, and recurrence rules carry `tenantId`. `TaskService` receives the tenant context explicitly, while repository and membership ports prevent assignments or queries from crossing household boundaries.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Tasks & Schedule" as Boundary {
  component "Task Command Service" as Commands
  component "Task Query Service" as Queries
  component "Recurrence Service" as Recurrence
  component "Calendar Service" as Calendar
  component "Task Aggregate" as Task
  component "Calendar Aggregate" as Event
  component "Assignee Policy" as Assignee
  component "Conflict Policy" as Conflict
  component "Task Port" as TaskPort
  component "Task Events Port" as EventPort

  TaskPort --> Commands
  TaskPort --> Queries
  TaskPort --> Recurrence
  TaskPort --> Calendar
  Commands --> Assignee
  Commands --> Task
  Queries --> Task
  Recurrence --> Task
  Calendar --> Conflict
  Calendar --> Event
  Task --> EventPort
  Event --> EventPort
}
interface "Task Commands and Queries" as TaskContract
interface "Task Events" as Events
TaskContract --> Boundary.TaskPort
Boundary.EventPort --> Events
@enduml
```

Manual form input and chat input enter through the same `Task Port`. The internal services keep command handling, read filtering, recurrence, and calendar conflict detection independently replaceable.

## Behavior diagram: create a task

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Member" as User
participant "Form or Chat Adapter" as Adapter
participant "Task API" as Api
participant "Authorization Policy" as Authorization
participant "Task Application" as App
participant "Membership Queries" as Membership
participant "Task Repository" as Repository
participant "Event Publisher" as Events

User -> Adapter: Enter task details
Adapter -> Api: CreateTask(TenantContext, command)
Api -> Authorization: Check write permission
Authorization --> Api: allowed or denied
Api -> App: Create task
App -> Membership: Validate assignee in tenant
Membership --> App: valid member
App -> Repository: Save tenant-scoped Task
App -> Events: Publish TaskCreated(tenantId)
Events --> Api: event accepted
Api --> Adapter: Task created
Adapter --> User: Show task
@enduml
```

The manual and chat channels converge on one command, preserving consistent validation and tenant isolation.
