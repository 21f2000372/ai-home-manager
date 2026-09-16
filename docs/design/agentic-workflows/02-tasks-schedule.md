# Tasks and Schedule Agent Workflow

## Purpose and ownership

The Tasks Agent manages tasks, assignments, recurring chores, calendar events, and conflict warnings. It owns task and schedule invariants. Chat and forms both produce the same typed command.

**Ports:** `Task Commands`, `Task Queries`, `Membership Queries`, `Task Events`.

## CRUD operations

| CRUD | Tasks-owned operation | WhatsApp event |
|---|---|---|
| Create | Create task, recurrence rule, or calendar event | `TaskCreated`, `RecurrenceCreated`, or `CalendarEventCreated` |
| Read | Read assigned tasks, occurrences, or shared calendar | Optional redacted schedule summary on request |
| Update | Edit, complete, skip, reschedule, or reassign | `TaskUpdated` or `CalendarEventUpdated` |
| Delete | Cancel task, recurrence, or calendar event | `TaskDeleted` or `CalendarEventDeleted` |

The Task application service owns all CRUD validation. Every mutation carries an idempotency key and expected version; WhatsApp is notified only from the committed event, never directly by the agent.

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center
actor "Member" as User
participant "Task Agent" as Agent
participant "Authorization" as Auth
participant "Task Application" as App
participant "Membership Queries" as Members
participant "Assignee / Recurrence / Conflict Policies" as Rules
database "Task + Calendar Store" as Store

User -> Agent: create/read/update/delete task or event
Agent -> Auth: authorize tenant capability
alt denied
  Auth --> Agent: deny
  Agent --> User: 403, no domain call
else allowed
  Auth --> Agent: TenantContext
  Agent -> App: typed command
  App -> Members: validate assignee membership
  Members --> App: member status
  App -> Rules: validate recurrence and overlap
  alt invalid assignee or hard conflict
    Rules --> App: reject or warning
    App --> Agent: correction / confirmation required
    Agent --> User: no side effect
  else valid
    Rules --> App: valid
    App -> Store: idempotent tenant-scoped commit
    Store --> App: task/event
    App --> Agent: committed result
    Agent --> User: result + warning if applicable
  end
end
@enduml
```

## Security and domain rules

- The assignee must belong to the active household.
- Guest writes are denied before the Task Agent runs.
- Recurrence occurrences use an idempotency key derived from tenant, rule, and date.
- Calendar overlap is a warning by default; creating an event that requires explicit confirmation remains pending.
- Read models apply role visibility and `assigned-to-me` filtering at the application boundary.

## Cohesion and coupling

The agent does not parse recurrence logic or query the calendar store directly. It depends on the Task application port. Finance receives purchase costs or task-related amounts only through an explicit command port; no module imports Task tables.
