# Secure Multi-Agent Home Operations Workflow

This is the shared runtime workflow for chat, web actions, scheduled jobs, and document-triggered operations. It follows the reference pattern of state, router, tool agents, validation, conditional retry, and notification, but places identity and authorization before planning.

## Agent topology

- **Conversation Router**: classifies intent and builds a minimal plan.
- **Domain Agents**: Task, Inventory, Finance, Calendar, Maintenance, Document, and People agents.
- **Validation Gate**: checks schema, policy, tenant scope, invariants, idempotency, and confirmation state.
- **Notification Agent**: publishes a user-safe result after the owning module commits.
- **State Object**: holds the request envelope, plan, bounded results, validation status, and audit reference.

```plantuml
@startuml
skinparam shadowing false
skinparam componentStyle uml2
skinparam packageStyle rectangle
skinparam ArrowColor #475569

actor "Household member" as User
component "Web / Chat / Job Adapter" as Adapter
component "Identity + Tenant Resolver" as Identity
component "Authorization Policy" as Auth
component "Conversation Router" as Router
component "Workflow State" as State
component "Validation Gate" as Validate
component "Notification Agent" as Notify
component "WhatsApp Notification Adapter" as WhatsApp
component "Audit / Outbox" as Audit

package "Domain Agents" {
  component "People Agent" as People
  component "Tasks Agent" as Tasks
  component "Inventory Agent" as Inventory
  component "Finance Agent" as Finance
  component "Maintenance Agent" as Maintenance
  component "Documents Agent" as Documents
}

database "Domain Stores" as Stores

User --> Adapter : request
Adapter --> Identity : authenticate + resolve tenant
Identity --> Auth : TenantContext
Auth --> Router : authorized capabilities only
Router --> State : intent + minimal plan
State --> People
State --> Tasks
State --> Inventory
State --> Finance
State --> Maintenance
State --> Documents
People --> Validate
Tasks --> Validate
Inventory --> Validate
Finance --> Validate
Maintenance --> Validate
Documents --> Validate
Validate --> Stores : owning application port
Stores --> Audit : transaction + event
Audit --> Notify : committed result
Notify --> Adapter : safe response
Notify --> WhatsApp : redacted event
WhatsApp --> User : opt-in template message

Validate ..> Auth : recheck before side effect
Router ..> Auth : capability planning
note right of Validate
  Fail closed on missing context,
  stale policy, invalid data,
  ambiguity, or duplicate command.
end note
@enduml
```

## Runtime contract

1. The adapter creates a correlation ID and authenticates the caller.
2. The tenant resolver selects one active household from memberships. Pending, removed, or suspended memberships stop here.
3. Authorization derives capabilities from role, resource, action, and domain policy. It does not trust the prompt, UI, or agent.
4. The router produces a bounded plan. The plan contains capability names and typed port calls, never repository operations.
5. Each domain agent receives a redacted `TenantContext` plus only the fields required by its port.
6. The validation gate rechecks authorization and validates the command inside the owning module.
7. The owner commits state and an outbox event atomically. Retries use a tenant-scoped idempotency key.
8. Notifications expose the outcome, not hidden records, credentials, raw prompts, or internal stack traces.

## CRUD and post-operation WhatsApp notification

Each domain agent calls its owning module with one of four typed operations: `create`, `read`, `update`, or `delete`. The module applies authorization and tenant filtering before the operation. Create, update, and delete write an outbox event in the same transaction as the state change. Read returns a role-filtered projection and creates an access event only when an explicit WhatsApp summary was requested.

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center
actor "Authorized member" as User
participant "Domain Agent" as Agent
participant "Authorization Policy" as Auth
participant "Owning Application Service" as App
database "Module Store" as Store
participant "Transactional Outbox" as Outbox
participant "WhatsApp Adapter" as WhatsApp

User -> Agent: CRUD request
Agent -> Auth: authorize(operation, tenant, role)
alt denied
  Auth --> Agent: deny
  Agent --> User: 403, no tool call
else allowed
  Auth --> Agent: TenantContext
  Agent -> App: typed CRUD operation
  App -> Store: validate + execute tenant-scoped operation
  alt create/update/delete
    Store --> App: committed entity + version
    App -> Outbox: write redacted event atomically
    Outbox -> WhatsApp: deliver after commit
    WhatsApp --> User: opt-in safe notification
  else read
    Store --> App: filtered read model
    opt explicit WhatsApp summary requested
      App -> Outbox: write access-summary event
      Outbox -> WhatsApp: deliver after policy check
    end
  end
  App --> Agent: result
  Agent --> User: response
end
@enduml
```

## Failure and approval loop

```plantuml
@startuml
start
:Authenticate caller;
if (Active membership?) then (no)
  :Return 401/403;
  stop
else (yes)
  :Resolve TenantContext;
endif
:Classify intent;
:Build minimal capability plan;
if (Every capability authorized?) then (no)
  :Return safe denial;
  :Audit policy result;
  stop
else (yes)
  :Call narrow domain port;
endif
:Validate schema, invariants,
idempotency, and data scope;
if (Human approval required?) then (yes)
  :Persist PendingApproval;
  :Notify authorized approver;
  stop
else (no)
  if (Validation passes?) then (yes)
    :Commit domain state + outbox event;
    :Notify result;
    stop
  else (no)
    :Ask for clarification or return correction;
    :Persist no side effect;
    stop
  endif
endif
@enduml
```

## Security invariants

- No LLM provider, OCR service, or domain agent is called before authorization.
- Financial and private-document data are filtered before prompt construction.
- Tool outputs are treated as untrusted input and validated against typed schemas.
- Prompt injection in a document or chat message cannot grant a capability.
- Logs contain identifiers and policy outcomes, not access tokens, file contents, or full financial payloads.
- Scheduled workers reconstruct tenant context from the job envelope and never use an ambient tenant.
- WhatsApp delivery is asynchronous, redacted, opt-in, rate-limited, and independent of the domain transaction.
- A WhatsApp provider outage queues delivery without replaying or duplicating the CRUD operation.
