# Home and Maintenance Component

## Story coverage

- US-5.1: log a repair and service history.
- US-5.2: warranty expiration reminders.
- US-5.3: report and track a maintenance issue.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Maintenance API" as Api
component "Maintenance Application" as MaintenanceApp
component "Warranty Policy" as Warranty
component "Maintenance Repository Adapter" as Repository
component "Tenant Isolation Policy" as TenantPolicy
database "Maintenance Store" as Store
interface "Maintenance Commands" as MaintenanceCommands
interface "Maintenance Queries" as MaintenanceQueries
interface "Membership Queries" as Membership
interface "Notification Events" as NotificationEvents
interface "Tenant Context" as TenantContext

Api ..> MaintenanceCommands : requires
Api ..> MaintenanceQueries : requires
MaintenanceApp - MaintenanceCommands : provides
MaintenanceApp - MaintenanceQueries : provides
MaintenanceApp ..> Membership : requires
MaintenanceApp ..> TenantContext : requires active household
MaintenanceApp ..> Warranty : applies
MaintenanceApp ..> Repository : persists
MaintenanceApp ..> NotificationEvents : publishes
Repository ..> Store
TenantPolicy ..> Store : tenant-scoped queries

note right of Warranty
  Warranty reminders are generated
  before expiry according to the
  household notification preference.
end note
@enduml
```

## Responsibilities and rules

- `Issue Handler` tracks description, reporter, status, priority, and accountable member.
- `Repair Handler` records service date, provider, cost, notes, and related appliance.
- `Appliance Handler` stores warranty and appliance details.
- `Warranty Policy` calculates reminder dates and emits a domain event rather than sending a notification directly.

The component owns maintenance history and warranty data; documents are linked through a document port when invoices or warranty certificates are uploaded.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class Appliance {
  +applianceId: UUID
  +tenantId: UUID
  +name: String
  +warrantyEndsAt: Date
}
class MaintenanceIssue {
  +issueId: UUID
  +tenantId: UUID
  +description: String
  +status: IssueStatus
}
class Repair {
  +repairId: UUID
  +tenantId: UUID
  +servicedAt: Date
  +provider: String
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface MaintenanceRepository {
  +findAppliances(tenantId: UUID): List<Appliance>
  +saveRepair(repair: Repair)
}
class MaintenanceService {
  +report(context: TenantContext, issue: MaintenanceIssue): MaintenanceIssue
  +logRepair(context: TenantContext, repair: Repair): Repair
}
class WarrantyPolicy {
  +reminderDate(appliance: Appliance): Date
}

Appliance "1" -- "0..*" Repair
Appliance "1" -- "0..*" MaintenanceIssue
MaintenanceService ..> MaintenanceRepository
MaintenanceService ..> WarrantyPolicy
MaintenanceService ..> TenantContext
TenantContext ..> Appliance : scopes
TenantContext ..> MaintenanceIssue : scopes
TenantContext ..> Repair : scopes
@enduml
```

Appliances, issues, and repairs are tenant-owned records. Warranty jobs must be scheduled per tenant and load appliances through a tenant-filtered repository.

## Behavior diagram: maintenance issue and warranty reminder

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Adult member" as User
participant "Maintenance API" as Api
participant "Authorization Policy" as Authorization
participant "Maintenance Service" as Service
participant "Maintenance Repository" as Repository
participant "Notification Service" as Notify
participant "Tenant Scheduler" as Scheduler

User -> Api: Report issue(TenantContext, description)
Api -> Authorization: Check tenant write permission
Authorization --> Api: allowed or denied
Api -> Service: Create issue
Service -> Repository: Save tenant-scoped issue
Repository --> Service: issueId
Service --> Api: issue created
Api --> User: Show tracking status

Scheduler -> Service: Check warranties(tenantId)
Service -> Repository: Find expiring appliances(tenantId)
Repository --> Service: tenant-scoped appliances
Service -> Notify: Publish warranty reminders
Notify --> User: Reminder for household appliance
@enduml
```

The scheduler supplies a tenant explicitly; it never scans appliances across tenants through a global unfiltered query.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Home & Maintenance" as Boundary {
  component "Issue Service" as Issues
  component "Repair Service" as Repairs
  component "Appliance Service" as Appliances
  component "Warranty Policy" as Warranty
  component "Maintenance Aggregate" as Aggregate
  component "Maintenance Port" as MaintenancePort
  component "Document Link Port" as DocumentPort
  component "Maintenance Events Port" as EventPort

  MaintenancePort --> Issues
  MaintenancePort --> Repairs
  MaintenancePort --> Appliances
  Issues --> Aggregate
  Repairs --> Aggregate
  Appliances --> Aggregate
  Appliances --> Warranty
  Repairs --> DocumentPort
  Aggregate --> EventPort
}
interface "Maintenance Commands and Queries" as Contract
interface "Domain Document Link" as Documents
interface "Maintenance Events" as Events
Contract --> Boundary.MaintenancePort
Boundary.DocumentPort --> Documents
Boundary.EventPort --> Events
@enduml
```

Issue tracking, repair history, appliance data, and warranty calculation are separate internal components. The aggregate remains the single owner of maintenance state and emits events for reminders.
