# Frontend Implementation Plan

## 1. Implementation baseline

Build the frontend as a React + TypeScript application using feature modules aligned with the backend components and user stories.

| Concern | Recommended library / approach | Ownership rule |
|---|---|---|
| UI runtime | React 19 + TypeScript strict mode | Components receive typed props and emit semantic callbacks |
| Routing | Next.js App Router | Route layouts enforce authentication, tenant membership, and capabilities |
| Styling | Tailwind CSS + accessible headless primitives | Design-system components own visual behavior |
| Server state | TanStack Query | All remote data, mutations, retries, and invalidation live here |
| Global client state | Zustand | Only session shell, active tenant selection, and non-server UI preferences |
| Forms | React Hook Form | Form draft and submission lifecycle stay local to the form |
| Runtime validation | Zod | Validate API boundaries and form payloads before mutation |
| HTTP | Typed `fetch` wrapper or generated OpenAPI client | Inject auth, tenant route, correlation ID, and idempotency key |
| Dates | `date-fns` or `Temporal` adapter | Centralize timezone and household locale behavior |
| Accessible primitives | Radix UI, Headless UI, or equivalent | Keyboard and focus behavior belongs in reusable primitives |
| Icons | Lucide React or equivalent | Icon buttons require accessible labels/tooltips |
| Testing | Vitest, Testing Library, MSW, Playwright | Test component contracts, API behavior, and user journeys |
| Error monitoring | Sentry or equivalent | Capture route, feature, tenant-safe correlation data, never sensitive payloads |

The repository does not currently lock a framework configuration. This plan assumes Next.js App Router, but the boundaries remain valid for React Router or another React host.

## 2. Delivery principles

- **Server state is not Zustand state.** Tasks, members, inventory, finance, documents, and agent runs remain in TanStack Query.
- **Zustand owns coordination state only.** Session status, active tenant selector, shell preferences, and ephemeral notification queue are appropriate; server entities are not.
- **Tenant context is explicit.** Every tenant query key, route, mutation, event stream, and persisted UI selection includes `tenantId`.
- **One behavior, one use case.** Manual task entry and chat task entry call the same typed `CreateTask` mutation.
- **Capabilities are derived once.** A permission selector produces capabilities for rendering; the backend remains authoritative.
- **Feature modules do not import sibling stores.** Cross-domain views use page-level composition or backend overview/chat responses.
- **Async agent work is observable.** Plans, step status, results, evidence, partial failures, retry, and cancel are modeled as first-class UI state.

## 3. Recommended project structure

```text
src/
├── app/                              # Next.js routes and layouts only
│   ├── (public)/welcome/page.tsx
│   ├── (auth)/households/new/page.tsx
│   ├── (auth)/households/join/page.tsx
│   └── (tenant)/t/[tenantId]/
│       ├── layout.tsx
│       ├── overview/page.tsx
│       ├── people/page.tsx
│       ├── tasks/page.tsx
│       ├── tasks/new/page.tsx
│       ├── calendar/page.tsx
│       ├── inventory/page.tsx
│       ├── grocery/page.tsx
│       ├── commodities/page.tsx
│       ├── finance/page.tsx
│       ├── maintenance/page.tsx
│       ├── documents/page.tsx
│       └── chat/page.tsx
├── features/
│   ├── people-permissions/
│   ├── tasks-schedule/
│   ├── food-inventory/
│   ├── finance-budget/
│   ├── maintenance/
│   ├── documents/
│   └── conversation/
├── components/
│   ├── app-shell/
│   ├── design-system/
│   ├── tenant/
│   ├── permissions/
│   └── feedback/
├── lib/
│   ├── api/                          # transport and typed endpoint clients
│   ├── auth/                         # session adapter
│   ├── query/                        # QueryClient and cache policies
│   ├── tenant/                       # TenantContext resolution
│   ├── validation/                   # shared Zod schemas
│   ├── dates/
│   └── telemetry/
├── stores/
│   ├── session-store.ts              # minimal Zustand state
│   ├── tenant-store.ts               # active tenant selector only
│   ├── shell-store.ts                # navigation/preferences
│   └── notification-store.ts         # ephemeral toast queue
└── test/
    ├── fixtures/
    ├── msw/
    └── e2e/
```

### Feature module contract

Each feature follows the same internal layout:

```text
features/tasks-schedule/
├── api/
│   ├── task-queries.ts
│   ├── task-mutations.ts
│   └── task-keys.ts
├── components/
│   ├── task-form.tsx
│   ├── task-list.tsx
│   └── task-row.tsx
├── models/
│   ├── task-dto.ts
│   ├── task-view-model.ts
│   └── task-schemas.ts
├── routes/
│   └── tasks-view-model.ts
└── index.ts
```

`index.ts` exports the feature's public components and hooks. Internal modules remain private to the feature.

## 4. Zustand state ownership plan

### Session store

Own only authentication lifecycle metadata:

```ts
type SessionState = {
  userId: string | null;
  status: 'unknown' | 'authenticated' | 'unauthenticated' | 'refreshing';
  setAuthenticated: (userId: string) => void;
  clear: () => void;
};
```

Do not store access tokens in persistent local storage unless the chosen identity provider requires it. Prefer secure, httpOnly cookie/session adapters.

### Tenant store

Own only the active selection and transition state:

```ts
type TenantState = {
  activeTenantId: string | null;
  switchStatus: 'idle' | 'validating' | 'switching' | 'failed';
  selectTenant: (tenantId: string) => void;
  clear: () => void;
};
```

The membership, role, and capability data come from TanStack Query. On a tenant switch:

1. Validate membership for the target tenant.
2. Cancel or ignore requests for the old tenant.
3. Clear sensitive old-tenant views and finance cache.
4. Set the new active tenant.
5. Load capabilities and route data for the new tenant.

### Shell and notification stores

- `shell-store`: mobile navigation open state, density preference, reduced-motion preference if not system-derived.
- `notification-store`: transient toast queue only. Persisted notifications are TanStack Query data.

### Store rules

- No domain entities in Zustand.
- No API calls inside store actions; controllers/hooks call APIs and update stores only with coordination results.
- Store selectors must be narrow and stable.
- Clear session and tenant stores on sign out, membership revocation, or unrecoverable `401`.

## 5. TanStack Query plan

### Query client defaults

```ts
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

Tune stale times per feature. Finance and membership data should be fresher than historical maintenance records.

### Query key factory

```ts
export const tenantKeys = {
  root: (tenantId: string) => ['tenant', tenantId] as const,
  membership: (tenantId: string) => [...tenantKeys.root(tenantId), 'membership'] as const,
  tasks: (tenantId: string, filters: TaskFilters) =>
    [...tenantKeys.root(tenantId), 'tasks', filters] as const,
  inventory: (tenantId: string, filter: InventoryFilter) =>
    [...tenantKeys.root(tenantId), 'inventory', filter] as const,
  finance: (tenantId: string, filter: FinanceFilter) =>
    [...tenantKeys.root(tenantId), 'finance', filter] as const,
  agentRun: (tenantId: string, runId: string) =>
    [...tenantKeys.root(tenantId), 'agent-run', runId] as const,
};
```

### Query and mutation ownership

| Feature | Queries | Mutations | Invalidation |
|---|---|---|---|
| People | Membership, members, pending members, capabilities | Join, approve, reject, role change, Admin transfer | Membership, capabilities, navigation, notifications |
| Tasks | Tasks, assigned tasks, recurrence, calendar | Create, update, complete, create event | Task lists, calendar, overview |
| Inventory | Stock, low stock, grocery, commodity rules | Add item, define rule, purchase, adjust stock | Inventory, grocery, low-stock, budget summary |
| Finance | Budget status, expenses, bills | Record expense, create budget, create bill | Finance views, overview, document link |
| Maintenance | Issues, repairs, appliances, warranties | Report issue, log repair, add appliance | Maintenance views, notifications |
| Documents | Documents, classification status, links | Upload, classify, link | Documents and linked domain view |
| Conversation | Sessions, messages, agent run, run events | Send message, confirm action, retry step, cancel run | Session, run, related feature summaries |

## 6. API and transport implementation

Create a single transport wrapper with typed request/response boundaries:

```ts
type RequestContext = {
  tenantId?: string;
  correlationId: string;
  idempotencyKey?: string;
};

async function request<T>(
  path: string,
  init: RequestInit,
  context: RequestContext,
): Promise<T>;
```

The wrapper must:

- Inject the authenticated session through the approved auth adapter.
- Require `tenantId` for tenant-scoped endpoints.
- Generate and propagate `correlationId`.
- Add `Idempotency-Key` to retryable commands.
- Normalize `400`, `401`, `403`, `404`, `409`, `422`, `429`, and `5xx` errors.
- Reject responses whose tenant metadata does not match the active context.
- Abort requests on tenant switch or route cancellation.

Use generated OpenAPI types where available. If generation is not available, define DTOs and Zod schemas at the API boundary and map DTOs to feature view models.

## 7. Multi-agent frontend implementation

### Agent run lifecycle

Implement the conversation feature around these states:

```text
idle -> planning -> awaiting_confirmation -> running
running -> completed
running -> partial
running -> failed
planning/running -> canceled
```

Components:

- `ConversationThread`: message chronology and run summaries.
- `AgentPlanPreview`: authorized capabilities, assumptions, and confirmation.
- `AgentRunTimeline`: parallel per-step status.
- `AgentResultGroup`: bounded results grouped by capability.
- `EvidencePanel`: source, freshness, and authorized references.
- `PartialResultBanner`: retry failed steps without rerunning successful steps.
- `ActionConfirmation`: explicit confirmation for write commands.

Agent events must be tenant/session scoped and sequence-numbered. The client rejects wrong-tenant events, ignores duplicates, requests a snapshot on sequence gaps, and cancels the stream on tenant change or sign out.

### Agent API hooks

```ts
function useSendMessage(tenantId: string, sessionId: string) {
  return useMutation({
    mutationFn: (message: string) => sendMessage(tenantId, sessionId, message),
  });
}

function useAgentRun(tenantId: string, runId: string, enabled: boolean) {
  return useQuery({
    queryKey: tenantKeys.agentRun(tenantId, runId),
    queryFn: () => getAgentRun(tenantId, runId),
    enabled,
  });
}
```

Do not implement agent selection in the browser. The backend orchestrator returns the authorized plan.

## 8. Implementation phases

### Phase 0: foundation

- Create React/TypeScript host, strict compiler settings, lint/format rules, and CI.
- Add design-system primitives, typography, responsive tokens, error boundaries, and accessible focus utilities.
- Add QueryClient, Zustand stores, API transport, auth adapter, and MSW test server.

### Phase 1: identity, tenant, and shell

- Implement session bootstrap and authenticated/public route groups.
- Implement household list, tenant switcher, TenantGuard, capability loading, and cache reset.
- Implement overview shell, global notifications, and role-aware navigation.

Stories: US-1.1, US-1.2, US-1.6, US-1.7.

### Phase 2: People & Permissions

- Implement join details, pending-member queue, role editor, rejection state, and Admin transfer dialog.
- Add confirmation, expiry, forbidden, and last-Admin conflict states.

Stories: US-1.3, US-1.4, US-1.5.

### Phase 3: Tasks and schedule

- Implement assigned task list and manual task form.
- Add chat action confirmation using the shared `CreateTask` mutation.
- Add recurrence form, calendar view, and conflict warning.

Stories: US-2.1 through US-2.6.

### Phase 4: Inventory and commodities

- Implement low-stock, grocery, recurring commodity, purchase, and optional cost flows.
- Refresh inventory and budget summaries after purchase completion.

Stories: US-3.1 through US-3.6.

### Phase 5: Finance and documents

- Implement capability-gated finance routes, budget status, expense list, receipt review, bills, document upload, and links.
- Ensure Child/Guest users never prefetch finance data.

Stories: US-4.1 through US-4.4 and US-6.1.

### Phase 6: maintenance and multi-agent workspace

- Implement issue, repair, appliance, and warranty views.
- Implement conversation sessions, plan preview, run timeline, result/evidence cards, partial retries, cancellation, and write confirmation.
- Add cross-domain affordability flow and tenant/session memory isolation.

Stories: US-5.1 through US-5.3 and US-6.2 through US-6.3.

## 9. Testing plan

### Unit and component tests

- Test components with explicit props and semantic callbacks, without mounting feature stores.
- Test Zustand actions/selectors for tenant switching, sign out, and cache coordination.
- Test Zod schemas and form validation.
- Test capability gates for Admin, Adult, Child, Guest, and Pending.
- Test multi-agent components for plan, parallel progress, evidence, partial, failed, canceled, and confirmation states.

### API and query tests

- MSW handlers cover success, `401`, `403`, `404`, `409`, `422`, `429`, and `5xx` responses.
- Assert every tenant query key includes `tenantId`.
- Assert finance queries are disabled for Child and Guest.
- Assert tenant switching cancels or ignores old-tenant responses.
- Assert duplicate and out-of-order agent events do not corrupt a run.

### End-to-end tests

- Register a household and land on the tenant overview as Admin.
- Join through an invite, remain pending, receive approval, and see role-specific navigation.
- Switch between two tenants and verify no stale tasks, finance, documents, or chat memory appear.
- Create a task manually and through chat and verify the same result contract.
- Complete a recurring commodity purchase and observe inventory and optional budget refresh.
- Upload a receipt and confirm the extracted expense after review.
- Ask a cross-domain question and verify authorized parallel agents, evidence, partial failure recovery, and tenant-scoped memory.

## 10. Definition of done

A frontend slice is complete when:

- Its route, layout, component tree, typed props, callbacks, API hooks, query keys, and capabilities are documented.
- Server state is tenant-scoped and invalidated after mutations.
- Zustand contains only coordination/client state, not domain entities.
- Loading, empty, error, forbidden, conflict, partial, canceled, and success states are implemented.
- Multi-agent writes require explicit confirmation and all agent results show bounded provenance.
- No protected data is prefetched or persisted for unauthorized roles.
- Keyboard and screen-reader behavior is covered by tests.
- Tenant switching, membership revocation, stale responses, event gaps, and sign-out are tested.
- The user-story acceptance criteria can be demonstrated end to end.
