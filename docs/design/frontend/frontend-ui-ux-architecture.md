# AI Home Manager Frontend UI/UX Architecture

**Role:** Principal Frontend Architect  
**Status:** Proposed design  
**Scope:** Multi-tenant household management frontend

## Architectural context

The frontend is a feature-oriented application over the backend bounded components documented in `docs/design/components/` and `docs/design/backend/`. Each household is a tenant. A user can belong to multiple households, but every rendered resource and API request is bound to exactly one active tenant context.

```ts
type TenantContext = {
  userId: string;
  tenantId: string;
  membershipId: string;
  role: 'Admin' | 'Adult' | 'Child' | 'Guest' | 'Pending';
  capabilities: CapabilityMap;
};
```

### Recommended technology baseline

The repository does not yet lock a frontend framework. This document uses the following implementation baseline because it supports strict component boundaries, typed contracts, and server-state isolation:

- React 19 + TypeScript with strict mode.
- Next.js App Router for routing and authenticated layouts.
- Tailwind CSS plus an accessible headless component layer for styling primitives.
- TanStack Query for server cache, mutations, retries, and invalidation.
- Zustand for minimal global client state: session, active tenant, and shell preferences.
- React Hook Form + Zod for forms and runtime boundary validation.
- Playwright for route and interaction tests; Vitest/Testing Library for component tests.

The architecture does not depend on these libraries' APIs. Equivalent tools are acceptable if they preserve the same ownership and coupling rules.

### Engineering rules

1. **High cohesion:** a component owns the state, validation, and event translation for the UI it directly controls.
2. **Low coupling:** child components receive explicit typed props and emit semantic callbacks; they do not import feature stores or API clients directly.
3. **Component isolation:** screens compose independent blocks through stable interfaces and view models.
4. **Tenant safety:** query keys, route params, mutations, subscriptions, and persisted state include the active tenant boundary.
5. **Backend authority:** client capability checks shape UX; server `401`/`403` responses remain authoritative.
6. **No domain leakage:** Finance UI never becomes a dependency of Inventory UI; cross-domain summaries are owned by the Overview or Chat feature.
7. **Accessible states:** loading, empty, forbidden, error, conflict, and success are designed states, not incidental branches.
8. **Multi-agent transparency:** the UI shows the authorized plan, execution progress, bounded results, assumptions, and partial failures without exposing hidden prompts or unauthorized data.

### Multi-agent frontend model

The frontend treats an agentic request as a typed run rather than an opaque chat response:

```ts
type AgentRun = {
  runId: string;
  tenantId: string;
  sessionId: string;
  status: 'planning' | 'awaiting_confirmation' | 'running' | 'completed' | 'partial' | 'failed' | 'canceled';
  plan: AgentStep[];
  results: AgentResult[];
  assumptions: string[];
  warnings: string[];
};

type AgentStep = {
  stepId: string;
  capability: 'tasks' | 'inventory' | 'finance' | 'calendar' | 'documents' | 'maintenance';
  status: 'planned' | 'authorized' | 'running' | 'succeeded' | 'failed' | 'skipped';
  requiresConfirmation: boolean;
};

type AgentResult = {
  stepId: string;
  title: string;
  summary: string;
  source: string;
  freshness: string;
  confidence?: 'high' | 'medium' | 'low';
};
```

The UI may show capability names, progress, bounded summaries, source labels, freshness, confidence, and warnings. It must not show system prompts, hidden chain-of-thought, raw private records, or results from a denied agent.

## 1. COMPONENT HIERARCHY TREE

The application is composed from shell, feature, and design-system blocks. Feature components do not reach through sibling components to mutate state.

```text
AppRoot
├── SessionProvider
│   ├── AuthBoundary
│   │   ├── PublicRoutes
│   │   │   ├── WelcomePage
│   │   │   ├── RegisterPage
│   │   │   └── JoinHouseholdPage
│   │   └── AuthenticatedApp
│   │       ├── TenantContextProvider
│   │       │   ├── TenantGuard
│   │       │   │   └── AppShell
│   │       │   │       ├── GlobalHeader
│   │       │   │       │   ├── HouseholdSwitcher
│   │       │   │       │   ├── NotificationBell
│   │       │   │       │   └── UserMenu
│   │       │   │       ├── TenantNavigation
│   │       │   │       ├── RouteAnnouncer
│   │       │   │       └── FeatureRoute
│   │       │   │           ├── OverviewPage
│   │       │   │           │   ├── TodayTaskSummary
│   │       │   │           │   ├── CalendarSummary
│   │       │   │           │   ├── InventoryAlertSummary
│   │       │   │           │   ├── BudgetSummary
│   │       │   │           │   └── QuickActionStrip
│   │       │   │           ├── PeoplePage
│   │       │   │           │   ├── MemberList
│   │       │   │           │   ├── PendingMemberQueue
│   │       │   │           │   ├── RoleEditor
│   │       │   │           │   └── AdminTransferDialog
│   │       │   │           ├── TasksPage
│   │       │   │           │   ├── TaskToolbar
│   │       │   │           │   ├── TaskFilterBar
│   │       │   │           │   ├── TaskList
│   │       │   │           │   │   └── TaskRow
│   │       │   │           └── TaskFormPage
│   │       │   │           │   └── TaskForm
│   │       │   │           ├── CalendarPage
│   │       │   │           │   ├── CalendarToolbar
│   │       │   │           │   ├── CalendarGrid
│   │       │   │           │   ├── CalendarListView
│   │       │   │           │   └── ConflictWarning
│   │       │   │           ├── InventoryPage
│   │       │   │           │   ├── StockSummary
│   │       │   │           │   ├── LowStockList
│   │       │   │           │   └── GroceryLink
│   │       │   │           ├── GroceryPage
│   │       │   │           │   ├── GroceryList
│   │       │   │           │   └── PurchaseItemDialog
│   │       │   │           ├── CommodityPage
│   │       │   │           │   └── CommodityRuleForm
│   │       │   │           ├── FinancePage
│   │       │   │           │   ├── BudgetStatus
│   │       │   │           │   ├── ExpenseList
│   │       │   │           │   ├── ReceiptUpload
│   │       │   │           │   └── BillList
│   │       │   │           ├── MaintenancePage
│   │       │   │           │   ├── IssueList
│   │       │   │           │   ├── RepairHistory
│   │       │   │           │   └── ApplianceWarrantyList
│   │       │   │           ├── DocumentsPage
│   │       │   │           │   ├── DocumentUpload
│   │       │   │           │   ├── DocumentList
│   │       │   │           │   └── DocumentLinkStatus
│   │       │   │           └── ChatPage
│   │       │   │               ├── ConversationThread
│   │       │   │               ├── Composer
│   │       │   │               ├── AgentPlanPreview
│   │       │   │               ├── AgentRunTimeline
│   │       │   │               ├── AgentResultGroup
│   │       │   │               ├── EvidencePanel
│   │       │   │               ├── PartialResultBanner
│   │       │   │               └── ActionConfirmation
│   │       │   └── GlobalNotificationCenter
│   └── DesignSystem
│       ├── Button / IconButton
│       ├── TextField / Select / DateField
│       ├── Dialog / Drawer
│       ├── Table / List / Card
│       ├── Badge / Alert / Toast
│       ├── Skeleton / EmptyState / ErrorState / ForbiddenState
│       └── FocusTrap / LiveRegion
```

### Dependency direction

```text
Design system primitives
        ^
Feature presentational components
        ^
Feature containers and view-model hooks
        ^
Typed API clients and query hooks
        ^
Authenticated tenant-aware transport
```

A presentational component may not import a query hook. A query hook may not read another feature's Zustand store. Cross-domain data is composed by a page-level view model or the backend's bounded overview/chat response.

- Agent components receive an `AgentRunViewModel`; they do not select agents, invoke domain APIs, or infer authorization.
- Agent result cards are independently renderable and keyed by `runId + stepId`, allowing parallel completion without list-order coupling.

## 2. ROUTE & LAYOUT ARCHITECTURE

### Route tree

```text
/
├── welcome                                  public
├── register                                public/authenticated redirect
├── households
│   ├── new                                  authenticated, no tenant required
│   ├── join                                 authenticated, no tenant required
│   └── select                               authenticated, no tenant required
└── t/[tenantId]
    ├── layout                              authenticated + tenant membership guard
    ├── overview                            active member
    ├── people                              role-aware
    ├── tasks                               active member
    ├── tasks/new                           Adult/Admin
    ├── calendar                            active member
    ├── inventory                           active member
    ├── grocery                             active member
    ├── commodities                         capability-aware
    ├── finance                             Adult/Admin only
    ├── maintenance                         capability-aware
    ├── documents                           active member
    └── chat                                active member
```

### Route table

| Path | Page | Nested layout | Guard | Dynamic parameters / URL state |
|---|---|---|---|---|
| `/welcome` | Sign in/register entry | Public layout | Public | `returnTo` only after validation |
| `/households/new` | Create household | Auth layout | Authenticated | None |
| `/households/join` | Invite code/link + details | Auth layout | Authenticated | `invite` token, never personal data |
| `/households/select` | Select household | Auth layout | Authenticated | `next` validated allowlisted route |
| `/t/[tenantId]` | Tenant shell | Auth + Tenant layout | Active membership | `tenantId` |
| `/t/[tenantId]/overview` | Household overview | Tenant layout | Active member | `section` optional |
| `/t/[tenantId]/people` | People and Permissions | Tenant layout | `members.read`; write actions capability-gated | `status`, `role`, `page` |
| `/t/[tenantId]/tasks` | Tasks | Tenant layout | `tasks.read` | `assignedTo`, `status`, `date`, `sort` |
| `/t/[tenantId]/tasks/new` | Manual task entry | Tenant layout | `tasks.create` | `returnTo` allowlisted |
| `/t/[tenantId]/calendar` | Shared calendar | Tenant layout | `calendar.read` | `view`, `date`, `mode` |
| `/t/[tenantId]/inventory` | Inventory | Tenant layout | `inventory.read` | `stock`, `sort` |
| `/t/[tenantId]/grocery` | Grocery list | Tenant layout | `grocery.read` | `list`, `status` |
| `/t/[tenantId]/commodities` | Recurring commodities | Tenant layout | capability-gated | `status`, `page` |
| `/t/[tenantId]/finance` | Budget, expenses, bills | Tenant layout | `finance.read` | `category`, `period`, `page` |
| `/t/[tenantId]/maintenance` | Issues and repairs | Tenant layout | capability-gated | `status`, `assetId` |
| `/t/[tenantId]/documents` | Private documents | Tenant layout | `documents.read` | `type`, `linked`, `page` |
| `/t/[tenantId]/chat` | Chat workspace | Tenant layout | `chat.use` | `sessionId` |

### Layout behavior

- `AuthLayout` owns session bootstrap and redirects unauthenticated users to `/welcome`.
- `TenantLayout` resolves `[tenantId]` through the membership endpoint before rendering tenant data.
- `TenantLayout` renders a neutral `TenantNotAccessible` page for both unknown and unauthorized tenants.
- `FinanceLayout` is capability-gated and does not prefetch finance data for Child or Guest.
- Route loaders and client query hooks use the same `tenantId`; no page derives tenant identity from a child form field.
- A tenant switch updates the URL first only after membership validation, then resets tenant-scoped caches.

## 3. STATE TAXONOMY & COUPLING MAP

### State ownership map

| State domain | Server cache state | Global client state | URL/route state | Local component state |
|---|---|---|---|---|
| Identity | `GET /session`, refresh status; invalidate on sign-in/out | `userId`, auth status, token adapter state | `returnTo` allowlisted path | Sign-in field errors, submit pending |
| Tenant/membership | `GET /households`, `GET /t/[tenantId]/membership`, capabilities; invalidate after role/admin transfer | `activeTenantId`, active membership, shell preference | `[tenantId]`, `next` | Switcher open, switch pending |
| People | Members/pending-member queries; invalidate on approve/reject/role change | None | `status`, `role`, `page` | Confirm dialogs, selected member |
| Tasks | Task list/detail/recurrence queries; invalidate on task mutation | None | `assignedTo`, `status`, `date`, `sort` | Form draft, validation, delete/complete dialog |
| Calendar | Events by visible range; invalidate after event mutation | None | `view`, `date`, `mode` | Drag state, conflict dialog, selected event |
| Inventory/grocery | Inventory, low-stock, grocery, commodity queries; invalidate after purchase/stock mutation | None | `stock`, `list`, `status`, `sort` | Checked item, purchase dialog |
| Finance | Budget, expense, bill queries; never fetched without capability | None | `category`, `period`, `page` | Receipt review, delete confirmation |
| Documents | Document list/detail/classification status; invalidate after upload/link | None | `type`, `linked`, `page` | File selection, progress, preview dialog |
| Maintenance | Issues, repairs, appliances, warranties; invalidate after mutations | None | `status`, `assetId` | Issue form, repair dialog |
| Chat and agent runs | Conversation messages, plan, per-agent status/results, session history; invalidate on new message/event or run completion | Draft only if needed; never store authoritative plan/results globally | `sessionId`, `runId` | Composer text, expanded evidence, confirmation, cancel state |
| Notifications | Notification list/unread count; invalidate on event/read | Toast queue only | `filter` optional | Toast visibility |

### Coupling map

```text
SessionStore ───────► TenantStore ───────► PermissionContext
      │                     │                    │
      └──────────────► ApiClient ◄───────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
          TaskQueries   InventoryQueries  FinanceQueries
                │             │             │
          TaskViewModel  InventoryVM    FinanceVM
                │             │             │
            Task UI      Inventory UI   Finance UI
```

Rules:

- `TenantStore` may expose the active `TenantContext` but never raw server entities to feature components.
- `PermissionContext` exposes derived booleans/capabilities, not role-check logic duplicated throughout JSX.
- Query hooks accept `tenantId` explicitly or obtain it from a typed tenant hook; they never use a global unscoped cache key.
- Feature view models translate API DTOs into display models and own no cross-feature mutation.
- Child components receive data and callbacks; they never call `router`, `queryClient`, or a domain API directly.

### Query key and invalidation contract

```ts
const taskKeys = {
  all: (tenantId: string) => ['tenant', tenantId, 'tasks'] as const,
  list: (tenantId: string, filters: TaskFilters) =>
    ['tenant', tenantId, 'tasks', 'list', filters] as const,
};
```

A successful mutation invalidates only the affected tenant and related read models:

- Task mutation: task list, assigned-task list, overview task summary.
- Role change: membership, capabilities, navigation permissions.
- Purchase completion: grocery occurrence, inventory, low-stock, optional budget.
- Document classification: document list/detail and linked-domain status.
- Tenant switch: cancel previous requests and remove or invalidate all previous-tenant keys.

### Multi-agent query and event contract

The Chat feature consumes a typed agent-run resource rather than treating the assistant response as an unstructured string:

```text
POST /api/v1/tenants/{tenantId}/conversations/messages
GET  /api/v1/tenants/{tenantId}/agent-runs/{runId}
GET  /api/v1/tenants/{tenantId}/agent-runs/{runId}/events
POST /api/v1/tenants/{tenantId}/agent-runs/{runId}/confirm
POST /api/v1/tenants/{tenantId}/agent-runs/{runId}/cancel
```

Each event is tenant- and session-scoped and carries a monotonic sequence number:

```ts
type AgentRunEvent = {
  runId: string;
  tenantId: string;
  sessionId: string;
  sequence: number;
  type: 'plan.created' | 'step.started' | 'step.completed' | 'step.failed' | 'run.completed' | 'run.partial' | 'run.canceled';
  stepId?: string;
  occurredAt: string;
  payload: unknown;
};
```

The client discards events for the wrong tenant/session, ignores duplicate sequence numbers, and requests a fresh snapshot when a sequence gap is detected. A failed step can be retried without rerunning successful steps.

## 4. COMPONENT SPECIFICATIONS (COMPONENT-WISE BREAKDOWN)

The following contracts use TypeScript-like notation. The types are UI-facing view-model contracts, not database entities.

### 4.1 Application shell components

#### Component Name: `HouseholdSwitcher`

- **Single Responsibility Statement:** Display available household tenants and emit a validated tenant selection.
- **Props API / Inputs:**

```ts
type HouseholdOption = {
  tenantId: string;
  name: string;
  role: Role;
  status: 'Active' | 'Pending';
};

type HouseholdSwitcherProps = {
  activeTenantId: string | null;
  households: HouseholdOption[];
  disabled?: boolean;
  onSelect: (tenantId: string) => void;
};
```

- **Events / Outputs:** `onSelect(tenantId)`; never mutates tenant state itself.
- **Internal State Requirements:** open/closed menu, keyboard active option, switch pending.
- **Visual/UX States:** loading skeleton; no-household empty state; pending membership badge; switch error; active state.

#### Component Name: `TenantGuard`

- **Single Responsibility Statement:** Resolve the route tenant and gate rendering until membership and capability context are known.
- **Props API / Inputs:**

```ts
type TenantGuardProps = {
  tenantId: string;
  requiredCapability?: Capability;
  children: React.ReactNode;
};
```

- **Events / Outputs:** `onDenied` at the route boundary; no child mutation callbacks.
- **Internal State Requirements:** resolving, accessible, forbidden, not-found.
- **Visual/UX States:** shell-preserving loading; neutral tenant-not-accessible state; forbidden state; retry state.

#### Component Name: `PermissionGate`

- **Single Responsibility Statement:** Render children or a capability-aware fallback based on the current tenant context.
- **Props API / Inputs:**

```ts
type PermissionGateProps = {
  capability: Capability;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  mode?: 'hide' | 'disable' | 'forbidden';
};
```

- **Events / Outputs:** none; it is a pure policy-to-view adapter.
- **Internal State Requirements:** none beyond context subscription.
- **Visual/UX States:** allowed; hidden; disabled with explanation; forbidden.

#### Component Name: `AppShell`

- **Single Responsibility Statement:** Compose global navigation, tenant navigation, route content, and global feedback regions.
- **Props API / Inputs:** `children`, `tenantContext`, `navigationItems`, `notifications`.
- **Events / Outputs:** `onOpenChat`, `onSelectTenant`, `onSignOut` delegated to shell controllers.
- **Internal State Requirements:** mobile navigation drawer, notification panel, route transition pending.
- **Visual/UX States:** authenticated loading shell; mobile/tablet/desktop layouts; offline banner; session-expired state.

### 4.2 People & Permissions components

#### Component Name: `PendingMemberQueue`

- **Single Responsibility Statement:** Present pending join requests and emit approve/reject intents.
- **Props API / Inputs:**

```ts
type PendingMember = {
  userId: string;
  name: string;
  age: number;
  relationship?: string;
  submittedAt: string;
};

type PendingMemberQueueProps = {
  members: PendingMember[];
  isLoading: boolean;
  onApprove: (userId: string, role: MemberRole) => void;
  onReject: (userId: string) => void;
};
```

- **Events / Outputs:** semantic approve/reject callbacks; no API calls.
- **Internal State Requirements:** selected member, role-selection dialog, confirmation pending.
- **Visual/UX States:** skeleton; empty “No pending requests”; mutation error; forbidden fallback.

#### Component Name: `MemberList`

- **Single Responsibility Statement:** Render active tenant members and expose role-edit intent.
- **Props API / Inputs:** `members`, `canManageRoles`, `onEditRole`, `onStartTransfer`.
- **Events / Outputs:** member-selected, role-edit-requested, transfer-requested.
- **Internal State Requirements:** table sort/filter UI only; no membership data copy.
- **Visual/UX States:** loading; empty household; stale refresh; forbidden; last-Admin protected action message.

#### Component Name: `RoleEditor`

- **Single Responsibility Statement:** Validate and confirm one member-role change.
- **Props API / Inputs:**

```ts
type RoleEditorProps = {
  member: MemberView;
  allowedRoles: MemberRole[];
  onSubmit: (role: MemberRole) => void;
  onCancel: () => void;
};
```

- **Events / Outputs:** `onSubmit(role)`, `onCancel()`.
- **Internal State Requirements:** selected role, dirty state, form errors.
- **Visual/UX States:** default; submitting; server conflict; last-Admin warning; success close.

#### Component Name: `AdminTransferDialog`

- **Single Responsibility Statement:** Explain the consequences of Admin transfer and collect explicit confirmation.
- **Props API / Inputs:** `currentAdmin`, `targetAdult`, `expiresAt`, `onConfirm`, `onCancel`.
- **Events / Outputs:** `onConfirm()`, `onCancel()`.
- **Internal State Requirements:** confirmation checkbox, pending, expired, rejected.
- **Visual/UX States:** confirmation; target confirmation pending; expired; completed; conflict/error.

### 4.3 Tasks and schedule components

#### Component Name: `TaskForm`

- **Single Responsibility Statement:** Collect and validate structured task input, then emit a domain-neutral create command.
- **Props API / Inputs:**

```ts
type TaskDraft = {
  title: string;
  description?: string;
  assigneeId: string;
  dueAt?: string;
  priority: 'Low' | 'Normal' | 'High';
  recurrence?: RecurrenceDraft;
};

type TaskFormProps = {
  members: MemberOption[];
  initialValue?: Partial<TaskDraft>;
  onSubmit: (draft: TaskDraft) => void;
  onCancel: () => void;
};
```

- **Events / Outputs:** `onSubmit(draft)`, `onCancel()`.
- **Internal State Requirements:** React Hook Form draft, Zod validation, recurrence disclosure.
- **Visual/UX States:** default; validation errors; submitting; conflict/domain error; saved.

#### Component Name: `TaskList`

- **Single Responsibility Statement:** Render a filtered task collection and emit task interaction intents.
- **Props API / Inputs:** `tasks`, `filters`, `onFilterChange`, `onComplete`, `onSelect`.
- **Events / Outputs:** filter-changed, task-completed, task-selected.
- **Internal State Requirements:** row action pending, keyboard selection.
- **Visual/UX States:** skeleton; empty assigned list; error retry; optimistic completion rollback.

#### Component Name: `CalendarView`

- **Single Responsibility Statement:** Render events for a visible date range and emit create/select/navigation intents.
- **Props API / Inputs:** `events`, `visibleRange`, `onRangeChange`, `onCreate`, `onSelect`.
- **Events / Outputs:** range-changed, event-selected, create-requested.
- **Internal State Requirements:** selected event, view mode, drag preview.
- **Visual/UX States:** loading; empty day; conflict warning; keyboard list view; error retry.

### 4.4 Food and inventory components

#### Component Name: `LowStockList`

- **Single Responsibility Statement:** Show inventory items below threshold and emit grocery-add intent.
- **Props API / Inputs:** `items`, `onAddToGrocery`, `onSelectItem`.
- **Events / Outputs:** add-to-grocery, item-selected.
- **Internal State Requirements:** none beyond row action pending.
- **Visual/UX States:** skeleton; all-stocked empty state; stale/error; low-stock severity labels.

#### Component Name: `GroceryList`

- **Single Responsibility Statement:** Display grocery occurrences and emit check-off or purchase-detail intents.
- **Props API / Inputs:** `items`, `onTogglePurchased`, `onOpenPurchaseDetails`.
- **Events / Outputs:** purchase-toggled, details-requested.
- **Internal State Requirements:** pending item ID, filter tab.
- **Visual/UX States:** loading; empty list; purchased; skipped; mutation conflict; offline retry.

#### Component Name: `CommodityRuleForm`

- **Single Responsibility Statement:** Collect recurring commodity details and preview the next occurrence.
- **Props API / Inputs:** `initialValue`, `onSubmit`, `onCancel`, `canEdit`.
- **Events / Outputs:** submit rule; cancel; preview schedule.
- **Internal State Requirements:** quantity/unit, preferred brand, recurrence, threshold, preview result.
- **Visual/UX States:** validation; preview loading; invalid recurrence; save success/error.

### 4.5 Finance and document components

#### Component Name: `BudgetStatus`

- **Single Responsibility Statement:** Present a tenant-scoped budget summary without owning finance fetching.
- **Props API / Inputs:** `category`, `period`, `limit`, `spent`, `remaining`, `status`.
- **Events / Outputs:** `onChangePeriod`, `onOpenExpenses`.
- **Internal State Requirements:** selected period only.
- **Visual/UX States:** skeleton; no budget configured; healthy/near-limit/over-limit; forbidden; error.

#### Component Name: `ReceiptUpload`

- **Single Responsibility Statement:** Manage receipt file selection and staged upload/review UI.
- **Props API / Inputs:** `accept`, `maxBytes`, `onUpload`, `onReview`, `onCancel`.
- **Events / Outputs:** file-selected, upload-requested, review-confirmed, canceled.
- **Internal State Requirements:** file metadata, progress, extraction result, confidence, review edits.
- **Visual/UX States:** idle; uploading; processing; low-confidence review; linked; rejected file; retry.

#### Component Name: `DocumentList`

- **Single Responsibility Statement:** Render authorized tenant documents and emit preview/link/download intents.
- **Props API / Inputs:** `documents`, `onPreview`, `onLink`, `onDownload`.
- **Events / Outputs:** preview-requested, link-requested, download-requested.
- **Internal State Requirements:** selected document and preview dialog only.
- **Visual/UX States:** skeleton; empty; processing; linked; unavailable; forbidden; download error.

### 4.6 Maintenance and chat components

#### Component Name: `IssueForm`

- **Single Responsibility Statement:** Collect a maintenance issue and emit a validated issue draft.
- **Props API / Inputs:** `appliances`, `initialValue`, `onSubmit`, `onCancel`.
- **Events / Outputs:** submit/cancel.
- **Internal State Requirements:** form draft and selected appliance.
- **Visual/UX States:** default; validation; submitting; saved; error.

#### Component Name: `ConversationThread`

- **Single Responsibility Statement:** Render a chronological conversation and associate each assistant response with its agent-run summary.
- **Props API / Inputs:** `messages`, `runs`, `sessionId`, `onConfirmAction`, `onRetry`, `onCancelRun`.
- **Events / Outputs:** action-confirmed, message-retried, session-selected, run-canceled.
- **Internal State Requirements:** scroll anchor and expanded run ID; draft composer state belongs to `Composer`.
- **Visual/UX States:** empty prompt suggestions; planning; running; completed; partial result; denied capability; failed; canceled.

#### Component Name: `AgentPlanPreview`

- **Single Responsibility Statement:** Explain the authorized capabilities that will be used before an agent run starts.
- **Props API / Inputs:** `runId`, `steps`, `assumptions`, `requiresConfirmation`, `onConfirm`, `onEdit`, `onCancel`.
- **Events / Outputs:** confirm-plan, edit-requested, cancel-run.
- **Internal State Requirements:** expanded step and confirmation pending.
- **Visual/UX States:** planning; waiting for confirmation; unauthorized step omitted; expired plan; plan error.

#### Component Name: `AgentRunTimeline`

- **Single Responsibility Statement:** Show ordered and parallel execution status for one tenant-scoped agent run.
- **Props API / Inputs:** `runId`, `steps`, `startedAt`, `status`, `onCancel`.
- **Events / Outputs:** cancel-run, step-selected.
- **Internal State Requirements:** expanded step and live-region announcement cursor.
- **Visual/UX States:** queued; parallel steps running; slow step; retryable step failure; canceled; complete.

#### Component Name: `AgentResultGroup`

- **Single Responsibility Statement:** Render bounded results grouped by agent capability without synthesizing new facts in the client.
- **Props API / Inputs:** `results`, `warnings`, `assumptions`, `onOpenSource`.
- **Events / Outputs:** source-opened, result-expanded.
- **Internal State Requirements:** expanded result IDs only.
- **Visual/UX States:** result loading; partial results; no authorized result; stale result; confidence indicator.

#### Component Name: `EvidencePanel`

- **Single Responsibility Statement:** Show source label, freshness, and authorized supporting record links for one agent result.
- **Props API / Inputs:** `source`, `freshness`, `references`, `canOpenReference`.
- **Events / Outputs:** reference-opened.
- **Internal State Requirements:** open/closed only.
- **Visual/UX States:** available; stale; unavailable; reference forbidden; loading.

#### Component Name: `PartialResultBanner`

- **Single Responsibility Statement:** Explain that an answer is incomplete and identify failed or unavailable capabilities.
- **Props API / Inputs:** `failedSteps`, `warnings`, `onRetryFailed`, `onDismiss`.
- **Events / Outputs:** retry-failed, dismissed.
- **Internal State Requirements:** retry pending.
- **Visual/UX States:** partial; retrying; permanently unavailable; resolved.

#### Component Name: `Composer`

- **Single Responsibility Statement:** Capture and submit a chat message without interpreting domain intent.
- **Props API / Inputs:** `value`, `disabled`, `placeholder`, `onChange`, `onSubmit`.
- **Events / Outputs:** `onChange(value)`, `onSubmit(value)`, attachment-selected.
- **Internal State Requirements:** draft text, composition state, attachment selection.
- **Visual/UX States:** empty; typing; submitting; disabled; attachment error.

#### Component Name: `ActionConfirmation`

- **Single Responsibility Statement:** Confirm an agent-proposed write action before it reaches a domain command.
- **Props API / Inputs:** `action`, `affectedDomain`, `tenantId`, `onConfirm`, `onEdit`, `onCancel`.
- **Events / Outputs:** action-confirmed, action-edited, action-canceled.
- **Internal State Requirements:** confirmation pending and edited fields.
- **Visual/UX States:** proposed; edited; submitting; server conflict; forbidden; completed.

## 5. USER STORY INTERACTION FLOWS

### Flow A: Create a household and become Admin (US-1.1)

1. `RegisterPage` owns form state and validates name/identity fields locally.
2. `AuthBoundary` provides the authenticated `userId`; the form never supplies an Admin role.
3. `CreateHouseholdMutation` submits the command through the tenant-neutral API client.
4. Backend creates the tenant and first Admin atomically.
5. On success, `TenantStore` sets the returned `tenantId` and membership.
6. Query cache is scoped to the new tenant and the router navigates to `/t/[tenantId]/overview`.
7. Overview requests only tenant-scoped summaries and renders the Admin quick actions.
8. On conflict or validation error, the form remains mounted with field-safe error messages.

### Flow B: Join and receive a role (US-1.2, US-1.3)

1. `JoinHouseholdPage` reads an invite token from the URL and stores no personal details in the URL.
2. `JoinDetailsForm` owns name, age, and relationship fields.
3. `JoinMutation` sends the invite token and details; the response is a Pending membership, not a tenant access token.
4. The UI navigates to an approval-status screen with no tenant dashboard prefetch.
5. Admin opens `PendingMemberQueue`; `PermissionGate('members.manage')` controls actions.
6. `RoleEditor` collects Adult, Child, or Guest and emits `onSubmit(role)`.
7. `ApproveMemberMutation` invalidates pending members, membership capabilities, and notifications.
8. The invitee receives a notification or refreshes approval status; approval sets active membership and enables tenant selection.
9. Rejection renders a neutral status and does not reveal other household data.

### Flow C: Switch between household tenants

1. `HouseholdSwitcher` emits only a `tenantId`.
2. `TenantStore` validates the selection through `TenantGuard` before committing it as active.
3. The app cancels or ignores in-flight requests associated with the previous tenant.
4. Tenant-scoped query keys are invalidated/removed; protected finance caches are cleared.
5. New route loaders and query hooks receive the new `tenantId`.
6. `PermissionContext` refreshes current role/capabilities from the server.
7. The shell renders the new household only after membership resolution succeeds.
8. If access fails, the old tenant content is cleared and a neutral not-found/forbidden state is shown.

### Flow D: Create a task manually or through chat (US-2.1, US-2.2)

1. Manual route renders `TaskForm`; chat route renders `Composer` and `ActionConfirmation`.
2. Manual form emits `TaskDraft`; Task Agent emits the same typed `CreateTask` command after parsing chat.
3. Both paths call the same `useCreateTask` mutation with the active `TenantContext`.
4. Server validates permission, assignee membership, recurrence, and tenant scope.
5. Success invalidates assigned-task, household-task, calendar, and overview summary queries.
6. A `409`/`422` conflict is rendered inline without losing the draft.

### Flow E: Manage a recurring commodity (US-3.5, US-3.6)

1. `CommodityRuleForm` validates quantity, unit, schedule, preferred brand, and threshold.
2. Schedule preview is requested through a read-only query for the active tenant.
3. Save mutation creates the tenant-scoped rule and invalidates commodity/grocery queries.
4. Scheduler creates an idempotent purchase occurrence; the UI receives it through polling or tenant-scoped notification refresh.
5. `GroceryList` emits purchase completion; `PurchaseItemDialog` optionally collects cost/receipt.
6. Success refreshes grocery, inventory, low-stock, and permitted budget summaries.

### Flow F: Upload receipt and review expense (US-4.1)

1. `ReceiptUpload` validates type/size locally and starts a staged private upload.
2. The upload request includes active tenant context through the API client; object storage remains private.
3. Processing status is polled or received through a tenant-scoped event.
4. Extracted fields render in a review form; low confidence requires explicit confirmation.
5. Confirming calls the Finance mutation, which creates the expense and document link.
6. Child and Guest users never mount this flow because the route capability is denied; a server `403` is still handled.

### Flow G: Cross-domain chat question (US-6.2, US-6.3)

1. `Composer` submits a message and active `sessionId`; it does not select agents.
2. Conversation query/mutation resolves the active tenant and current capabilities.
3. The orchestrator creates a plan and returns only authorized Inventory, Finance, and Calendar steps.
4. `AgentPlanPreview` shows the steps, assumptions, and confirmation requirement before execution when the plan includes a write.
5. `AgentRunTimeline` renders parallel step progress using ordered run events.
6. `AgentResultGroup` renders each bounded result with `EvidencePanel` source/freshness details.
7. `PartialResultBanner` identifies failed or denied steps and allows retry without rerunning successful steps.
8. `ConversationThread` renders the synthesized answer and assumptions; the client does not synthesize domain facts.
9. `ConversationMemory` invalidates the current tenant/session query after persistence.
10. Switching tenants cancels the active run, clears the current thread, and requires an explicit session reload, preventing memory leakage.

### Flow H: Agent-proposed task action (US-2.1)

1. User submits “remind Sam to take out the trash Friday.”
2. `AgentPlanPreview` displays the parsed assignee, action, due date, and target capability.
3. User edits or confirms the structured action; `ActionConfirmation` emits a semantic confirmation event.
4. The Task Agent submits the same `CreateTask` contract as the manual `TaskForm`.
5. `AgentRunTimeline` shows authorization, task creation, and event publication without exposing internal prompts.
6. Success invalidates tenant-scoped task, calendar, and overview queries; `422` or `403` leaves the proposed action visible for correction.

## Validation and quality gates

### Component-level tests

- Render components with explicit props and verify semantic callbacks, without mounting feature stores.
- Test loading, empty, forbidden, error, conflict, and success states for every major component.
- Test keyboard navigation and focus return for dialogs, menus, tables, calendar, and chat.

### Feature integration tests

- Tenant A data never renders after switching to Tenant B.
- Child and Guest cannot fetch or prefetch Finance data.
- Pending members cannot render tenant screens.
- Admin transfer refreshes both membership and capability state.
- Manual and chat task creation produce the same mutation contract.
- Multi-agent runs show authorized plans, parallel progress, bounded evidence, cancellation, and partial-failure recovery.
- Receipt review cannot create an expense without explicit confirmation.

### End-to-end scenarios

- Register household, land on tenant overview, and see Admin actions.
- Join household, remain pending, receive approval, and see only permitted navigation.
- Switch between two households and verify tasks, inventory, finance, and chat memory are isolated.
- Create recurring milk purchase, complete it, and observe inventory/expense refresh.
- Ask the cross-domain affordability question as Adult and verify bounded synthesis.

### Definition of done

A frontend feature is complete when:

- Its route, layout, component tree, API hooks, query keys, and capability requirements are documented.
- Components have explicit typed props and semantic callback contracts.
- Server state is tenant-scoped and invalidated after mutations.
- No protected data is prefetched or persisted for unauthorized roles.
- Loading, empty, error, forbidden, conflict, and success states are implemented.
- Keyboard and screen-reader interaction is covered by tests.
- Tenant-switch, sign-out, membership revocation, and stale-response behavior are tested.
- The feature's user-story acceptance criteria can be demonstrated end to end.
