# Database Architecture

## Decision

Use **SQLite as the primary database** for the AI Home Manager modular-monolith MVP.

SQLite is sufficient for the initial workload because the core stories require:

- Atomic household creation with the first Admin membership.
- Atomic Admin transfer without ever leaving a tenant without an Admin.
- Tenant-scoped foreign keys and unique constraints.
- Transactional task, inventory, expense, and budget updates.
- Reliable outbox writes in the same transaction as domain changes.
- Filtered queries for roles, assigned tasks, low stock, budgets, bills, and documents.
- Strong consistency for recurring purchase occurrence idempotency.
- Optional FTS5 support without introducing a separate search database.

SQLite must be configured with foreign-key enforcement enabled, WAL journaling, a busy timeout, parameterized queries, and versioned migrations. Tenant authorization remains an application responsibility because SQLite does not provide PostgreSQL-style Row-Level Security.

## Technology responsibilities

| Need | Technology | Reason |
|---|---|---|
| Users, tenants, memberships, tasks, inventory, finance, maintenance, metadata | SQLite | ACID transactions, joins, constraints, indexes, migrations for the MVP |
| Receipt images, PDFs, warranties, bills, uploaded documents | Object storage | Durable binary storage, private access policies, lifecycle management |
| Short-lived cache and rate limits | Redis, optional | Fast ephemeral data; never authoritative |
| Reliable async delivery | SQLite outbox + worker | Simple MVP reliability and transactional consistency |
| Semantic conversation retrieval | Deferred | Start with structured interactions and keyword search; add a vector service only when required |
| Full-text filtering | SQLite FTS5, optional | Sufficient for household names, document metadata, tasks, and conversation text |

## Why not use another primary database?

- **Document database:** flexible documents are not the dominant shape. The system needs joins and invariants across memberships, roles, tenants, tasks, expenses, and linked documents.
- **Graph database:** cross-domain answers are bounded queries composed by the orchestrator, not arbitrary graph traversal.
- **Separate vector database:** conversational memory starts as structured `AgentInteraction` records; semantic search is deferred until product usage justifies it.
- **Redis as primary storage:** cache eviction and eventual loss are unacceptable for household finance, roles, and task state.

## Tenancy model

Each household is one tenant. A global `users` row may participate in many tenants through `memberships`.

Every request creates an immutable context:

```text
TenantContext {
  userId,
  tenantId,
  membershipId,
  role,
  correlationId
}
```

Rules:

1. Resolve `userId` from the identity token.
2. Resolve `tenantId` through an active membership for that user.
3. Pass `TenantContext` to every use case and repository.
4. Include `tenant_id` on every tenant-owned table.
5. Include `tenant_id` in unique keys, idempotency keys, outbox events, job records, and object-storage paths.
6. Reject missing or mismatched tenant context before a domain handler runs.

SQLite has no built-in Row-Level Security. Enforce tenant isolation through immutable `TenantContext`, repository methods that require `tenantId`, composite tenant-aware foreign keys, and integration tests that attempt cross-tenant access. Application authorization remains mandatory.

## Consistency boundaries

Use one database transaction for:

- Household creation plus first Admin membership.
- Admin transfer plus current/target membership updates.
- Task or purchase mutation plus outbox event.
- Expense creation plus document-link metadata where both records are in SQLite.
- Recurring occurrence creation using a unique `(tenant_id, rule_id, occurrence_date)` constraint.

Do not hold a database transaction open while calling an LLM, OCR provider, email provider, or object-storage upload. Persist an operation state and complete external work asynchronously.

## Outbox and workers

The module transaction writes both domain state and `outbox_messages`. A publisher claims messages with leases, sends them to notification or worker adapters, and records attempts. Consumers use `(tenant_id, event_id)` or an equivalent idempotency key.

The MVP can run this with SQLite and a worker process. SQLite allows one writer at a time, so keep transactions short and move OCR, LLM, notifications, and other long-running work to workers. Add a server database and broker such as Azure Service Bus or Kafka only when throughput, delivery topology, or team ownership justifies it.

## SQLite deployment limits

- Use one shared SQLite database with `tenant_id` on tenant-owned rows for the initial deployment.
- A separate SQLite file per tenant is possible for stronger physical isolation, but complicates discovery, migrations, backups, and cross-tenant administration; do not use it as the default.
- SQLite is not the right primary store for many concurrent writers across multiple application replicas.
- When that limit is reached, preserve the repository and event ports and migrate the implementation to a server database.

## Data lifecycle

- Use object-storage lifecycle rules for abandoned uploads and expired temporary files.
- Keep financial and membership audit records according to the product retention policy.
- Soft-delete or status-transition tenant records where history matters; avoid hard deletion of expenses, role changes, and audit events.
- Deleting a tenant requires an explicit Admin-only workflow, export/retention handling, and a delayed purge job.
