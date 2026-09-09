# State and API Integration

## State categories

| State | Examples | Owner |
|---|---|---|
| Identity session | Authenticated user, token refresh, sign out | Session provider |
| Tenant context | Active tenant, membership, role, capabilities | Tenant provider |
| Server state | Tasks, calendar, inventory, finance, documents, members | Query/cache layer |
| Form state | Draft task, invite details, receipt review | Feature form |
| Ephemeral UI state | Dialog open, selected tab, toast, upload progress | Local component state |
| Conversation state | Messages, plan status, action confirmation | Chat query/cache layer |

Do not copy server entities into a global client store unless a feature needs a derived view. Keep server state normalized by resource and tenant.

## Query key convention

Every tenant-scoped query key includes the tenant:

```text
['tenant', tenantId, 'tasks', { assignedTo, status }]
['tenant', tenantId, 'inventory', 'low-stock']
['tenant', tenantId, 'finance', 'budget-status', category, period]
['tenant', tenantId, 'documents', filters]
['tenant', tenantId, 'conversation', sessionId]
```

On tenant change, invalidate or remove all keys for the previous tenant and cancel requests whose context no longer matches.

## API client contract

The API client should inject:

- Access token.
- Active `tenantId` route segment.
- Correlation ID.
- Idempotency key for retryable commands.
- Upload content type and size metadata.

The client must not inject a role as an authorization claim. The server resolves current membership and role.

## API response handling

Normalize backend errors into feature-safe states:

| Status | Frontend behavior |
|---|---|
| `400` | Show field or request validation errors |
| `401` | Refresh session once, then return to sign-in |
| `403` | Render forbidden state and remove protected data from view/cache |
| `404` | Show tenant-scoped not-found state |
| `409` | Show conflict and refresh the relevant resource |
| `422` | Show domain-rule message, such as last Admin or calendar overlap |
| `429` | Show retry-after state without duplicate submission |
| `5xx` | Show recoverable error and preserve safe form draft |

## Mutation patterns

- **Task creation:** manual and chat adapters call the same `CreateTask` mutation; invalidate assigned and household task queries.
- **Role change/Admin transfer:** use explicit confirmation; invalidate membership and capability queries after success.
- **Purchase completion:** update grocery occurrence optimistically only when rollback is reliable; refresh inventory and optional finance summaries after the event.
- **Receipt upload:** use a staged upload; poll extraction status; require user review before creating an expense when fields are uncertain.
- **Document upload:** show private upload progress, classification status, link status, and retry actions.
- **Chat actions:** display the parsed command and confirmation state before executing write commands.

## Cache and privacy rules

- Never prefetch Finance routes for Child or Guest.
- Never cache a protected query under a key without `tenantId` and role-sensitive capability context.
- Clear tenant-scoped cache on sign out, membership revocation, and tenant switch.
- Do not persist receipt images, document binaries, or sensitive finance responses in general browser storage.
- Keep optimistic updates out of role and membership transitions unless the server response is authoritative.

## Realtime and notifications

The first version can use polling or request refresh after mutations. If realtime updates are added, event subscriptions must be scoped by `tenantId` and authenticated membership. Events should invalidate queries rather than mutate unrelated feature stores directly.

Examples:

- `TaskCreated(tenantId)` invalidates task and overview queries.
- `InventoryLowStock(tenantId)` invalidates inventory and notification queries.
- `RoleChanged(tenantId)` refreshes capabilities and navigation.
- `AdminTransferred(tenantId)` refreshes both users' membership contexts.
- `DocumentClassified(tenantId)` refreshes document and linked-domain status.
