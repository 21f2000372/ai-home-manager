# People and Permissions Component

## Story coverage

- US-1.1: create a household and make the first user Admin.
- US-1.2: join with an invite code or link and provide name and age.
- US-1.3: Admin reviews pending members and assigns a role.
- US-1.4: Admin changes roles.
- US-1.5: Admin transfer with confirmation.
- US-1.6 and US-1.7: role-scoped access for Child and Guest.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "People & Permissions API" as Api
component "Identity & Registration Adapter" as Identity
component "Membership Application" as Membership
component "Household Policy" as Policy
component "Membership Authorization" as Authorization
component "Permission Policy" as Permissions
component "Member Repository Adapter" as Profiles
component "Household Repository Adapter" as Households
component "Invite Repository Adapter" as Invites
component "Notification Adapter" as Notifications
component "Tenant Isolation Policy" as TenantPolicy
database "Identity / Membership Store" as Store
interface "People Commands" as ProfileCommands
interface "Membership Queries" as MembershipQueries
interface "Authorization Context" as AuthContext
interface "Notification Events" as NotificationEvents
interface "Tenant Context" as TenantContext

Api ..> ProfileCommands : requires
Api ..> Identity : authenticates / registers
Membership - ProfileCommands : provides
Membership - MembershipQueries : provides
Authorization - AuthContext : provides
Membership ..> AuthContext : requires
Membership ..> TenantContext : selects active household tenant
Membership ..> Policy : applies
Authorization ..> Permissions : evaluates role permissions
Membership ..> Profiles : persists profiles
Membership ..> Households : persists households
Membership ..> Invites : persists invites
Membership ..> NotificationEvents : publishes
Profiles ..> Store
Households ..> Store
Invites ..> Store
TenantPolicy ..> Store : tenant-scoped reads/writes
Notifications ..> NotificationEvents : consumes

note right of Policy
  First household user becomes Admin.
  Pending members have no resource access.
  A household must always retain an Admin.
end note
@enduml
```

## Responsibilities and rules


The component owns identity-linked member data, household tenants, memberships, invites, and permission decisions. It does not own tasks, finance records, or UI decisions. A user may create multiple household tenants and may hold memberships in multiple tenants; each operation selects one active tenant. Other components consume the `Membership Queries` interface instead of reading this store directly. The application service implements registration, invitation, approval, rejection, role changes, and admin transfer behind one command interface; this keeps the domain policy independent of HTTP and persistence details.

### Enforce role-scoped access

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Household member" as User
participant "API Gateway" as Gateway
participant "Membership Authorization" as Membership
participant "Permission Policy" as Policy
participant "Requested Domain API" as Domain

User -> Gateway: Request(resource, action, tenantId)
Gateway -> Membership: Resolve membership(userId, tenantId)
Membership --> Gateway: role + membership status
Gateway -> Policy: can(role, status, resource, action)
alt allowed
  Policy --> Gateway: allow
  Gateway -> Domain: Execute with TenantContext
  Domain --> Gateway: tenant-scoped result
  Gateway --> User: 200 response
else denied
  Policy --> Gateway: deny
  Gateway --> User: 403 Forbidden
end

note over Membership, Policy
  Child finance access and Guest writes are denied here,
  before the domain API or agent is invoked.
end note
@enduml
```

## Role and permission contract

Authorization is evaluated against both the active `tenantId` and the member's role. A pending membership has no household-resource permission.

| Role/state | Allowed profile and household actions | Allowed shared-resource actions | Restricted actions |
|---|---|---|---|
| Admin / Active | Review pending members, assign or change roles, create invites, transfer Admin | Read and write household resources | Cannot remove or demote the last Admin |
| Adult / Active | Read own profile and membership | Read and write according to each domain's Adult policy | Cannot perform Admin-only membership operations |
| Child / Active | Read own profile, own tasks, and shared calendar | Read permitted schedule data | Finance, budget, bill, Admin, and other members' private data return 403 |
| Guest / Active | Read own profile | Read-only access to today's schedule and tasks | All writes/deletes and finance, budget, bill, and Admin operations return 403 |
| Any / Pending | View own approval status | None | No household data or resource access |

The policy is enforced before task, calendar, inventory, finance, document, or maintenance handlers run. UI visibility is not a substitute for this check.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class User {
  +userId: UUID
  +name: String
  +age: Integer
  +relationship: String
}
class HouseholdTenant {
  +tenantId: UUID
  +name: String
  +status: TenantStatus
}
class Membership {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
  +status: MembershipStatus
}
class PersonalDetails {
  +userId: UUID
  +name: String
  +age: Integer
  +relationship: String
}
class TenantContext {
  +userId: UUID
  +tenantId: UUID
  +role: HouseholdRole
}
class Invite {
  +tenantId: UUID
  +codeHash: String
  +expiresAt: DateTime
  +status: InviteStatus
}
enum HouseholdRole {
  Admin
  Adult
  Child
  Guest
}
enum MembershipStatus {
  Pending
  Active
  Rejected
  Suspended
  Removed
}
class PermissionPolicy {
  +can(context: TenantContext, resource: String, action: Action): Boolean
}
interface MembershipRepository {
  +findByTenant(tenantId: UUID)
  +save(membership: Membership)
}
interface TenantContextResolver {
  +resolve(userId: UUID, tenantId: UUID): TenantContext
}
class MembershipService {
  +registerHousehold(userId: UUID, name: String): HouseholdTenant
  +submitJoin(tenantId: UUID, details: PersonalDetails): Membership
  +approveMember(context: TenantContext, userId: UUID, role: HouseholdRole)
  +rejectMember(context: TenantContext, userId: UUID)
  +changeRole(context: TenantContext, userId: UUID, role: HouseholdRole)
  +transferAdmin(context: TenantContext, targetUserId: UUID)
}
class RolePolicy {
  +canChangeRole(context: TenantContext): Boolean
  +protectLastAdmin(memberships)
}

User "1" -- "0..*" Membership
User "1" -- "1" PersonalDetails
HouseholdTenant "1" -- "0..*" Membership
HouseholdTenant "1" -- "0..*" Invite
Membership "1" --> "1" HouseholdRole
Membership "1" --> "1" MembershipStatus
MembershipService ..> MembershipRepository
MembershipService ..> TenantContextResolver
MembershipService ..> RolePolicy
MembershipService ..> PermissionPolicy
TenantContextResolver ..> MembershipRepository
TenantContext --> HouseholdTenant : selects
TenantContext --> Membership : authorizes
@enduml
```

`HouseholdTenant` is the tenant root. Membership and invite records are tenant-scoped, and the service cannot mutate a membership without a resolved `TenantContext`. The repository interface follows DIP and makes tenant filtering part of the persistence contract.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "People & Permissions" as Boundary {
  component "Registration" as Registration
  component "Invitation" as Invitation
  component "Member Approval" as Approval
  component "Member Rejection" as Rejection
  component "Role Management" as Roles
  component "Admin Transfer" as Transfer
  component "Membership Aggregate" as Aggregate
  component "Role Policy" as RolePolicy
  component "Command Port" as CommandPort
  component "Membership Query Port" as QueryPort
  component "Authorization Port" as AuthorizationPort

  CommandPort --> Registration
  CommandPort --> Invitation
  CommandPort --> Approval
  CommandPort --> Roles
  CommandPort --> Transfer
  Registration --> Aggregate
  Invitation --> Aggregate
  Approval --> Aggregate
  Rejection --> Aggregate
  Roles --> RolePolicy
  Roles --> Aggregate
  Transfer --> RolePolicy
  Transfer --> Aggregate
  Aggregate --> QueryPort
  Aggregate --> AuthorizationPort
}
interface "People Commands" as Commands
interface "Membership Queries" as Queries
interface "Authorization Context" as Auth
Commands --> Boundary.CommandPort
Boundary.QueryPort --> Queries
Boundary.AuthorizationPort --> Auth
@enduml
```

The public component exposes command, membership-query, and authorization ports. Registration, invitation, approval, role management, and admin transfer are separate internal components and share the membership aggregate and role policy rather than bypassing them.

## Behavior diagrams

### Create a household tenant

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Authenticated user" as User
participant "People & Permissions API" as Api
participant "Tenant Context Resolver" as Context
participant "Membership Application" as App
participant "Household Policy" as Policy
participant "Membership Repository" as Repository
participant "Identity Provider" as Identity
database "Tenant Store" as Store

User -> Api: Create household(name)
Api -> Identity: Validate user token
Identity --> Api: userId
Api -> Context: Resolve creation context
Context --> Api: new tenant context
Api -> App: registerHousehold(userId, name)
App -> Policy: Validate household creation
Policy --> App: allowed
App -> Store: Begin transaction
App -> Store: Create HouseholdTenant(tenantId)
App -> Store: Create Membership(userId, Admin)
App -> Store: Commit transaction
App --> Api: tenantId + Admin membership
Api --> User: Household created

note over App, Store
  Household and first Admin are created atomically.
  No tenant can exist without an Admin membership.
end note
@enduml
```

### Join and approve a household tenant

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Invitee" as Invitee
actor "Current Admin" as Admin
participant "People & Permissions API" as Api
participant "Invite Service" as Invite
participant "Membership Authorization" as Authorization
participant "Membership Application" as App
participant "Tenant Store" as Store
participant "Notification Service" as Notify

Invitee -> Api: Submit invite + name + age
Api -> Invite: Validate invite code/link
Invite -> Store: Find invite by code hash
Store --> Invite: tenantId + invite status
Invite -> Store: Create pending Membership(tenantId)
Invite --> Api: pending membership
Api --> Invitee: Await Admin approval

Admin -> Api: Review pending member
Api -> Authorization: Check Admin role in tenantId
Authorization --> Api: allowed
alt approve member
  Api -> App: approveMember(tenantId, userId, role)
  App -> Store: Update membership role and status
  App -> Notify: Publish membership approved
  Notify --> Invitee: Approval notification
  App --> Api: active membership
  Api --> Admin: Member approved
else reject member
  Api -> App: rejectMember(tenantId, userId)
  App -> Store: Update membership status to Rejected
  App -> Notify: Publish membership rejected
  Notify --> Invitee: Rejection notification
  Api --> Admin: Member rejected
end

note over Authorization, Store
  The invitee is authenticated but has no tenant
  resource access while membership is pending.
end note
@enduml
```

### Switch active household tenant

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "User" as User
participant "API Gateway" as Gateway
participant "Tenant Context Resolver" as Resolver
participant "Membership Repository" as Membership
participant "Authorization Policy" as Authorization
participant "Feature Component" as Feature

User -> Gateway: Select tenantId
Gateway -> Resolver: resolve(userId, tenantId)
Resolver -> Membership: Find active membership
Membership --> Resolver: membership or none
alt membership is active
  Resolver --> Gateway: TenantContext(userId, tenantId, role)
  Gateway -> Authorization: Validate requested capability
  Authorization --> Gateway: allowed or denied
  Gateway -> Feature: Request with TenantContext
  Feature --> Gateway: Tenant-scoped result
  Gateway --> User: Result for selected household
else no active membership
  Resolver --> Gateway: TenantNotAccessible
  Gateway --> User: 403 Forbidden
end

note over Resolver, Feature
  A client-supplied tenantId is only a selector.
  Membership resolution is the isolation control.
end note
@enduml
```

### Transfer household administration

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Current Admin" as CurrentAdmin
actor "Target Adult" as Target
participant "People & Permissions API" as Api
participant "Authorization Policy" as Authorization
participant "Membership Application" as App
participant "Role Policy" as Policy
database "Tenant Store" as Store

CurrentAdmin -> Api: Request transfer(tenantId, targetUserId)
Api -> Authorization: Check current Admin in tenant
Authorization --> Api: allowed or denied
Api -> App: Start transfer
App -> Policy: Validate target is Adult in same tenant
Policy --> App: valid
App -> Store: Create pending transfer confirmation
App --> Target: Request confirmation
Target -> Api: Confirm transfer
Api -> Authorization: Check target membership in tenant
Authorization --> Api: allowed
Api -> App: Complete transfer
App -> Policy: Protect last Admin invariant
Policy --> App: valid
App -> Store: Target becomes Admin
App -> Store: Current Admin becomes Adult
App --> Api: Transfer completed
Api --> CurrentAdmin: Confirmation
Api --> Target: Admin access granted

note over Policy, Store
  Both membership updates are one tenant-scoped transaction.
end note
@enduml
```

### Membership lifecycle

```plantuml
@startuml
[*] --> Pending : join with invite
Pending --> Active : Admin assigns role
Pending --> Rejected : Admin rejects
Active --> Suspended : Admin suspends
Suspended --> Active : Admin restores
Active --> Removed : member leaves or Admin removes
Rejected --> [*]
Removed --> [*]
@enduml
```

These behavior diagrams use sequence diagrams for interactions and a state machine for membership lifecycle. Every flow carries a tenant identifier, resolves membership before access, and commits tenant-owned changes atomically.
