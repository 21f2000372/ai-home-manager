# Database Architecture

## Decision

Use **PostgreSQL as the primary database** for the AI Home Manager modular monolith.

PostgreSQL is the right default because the core stories require:

- Atomic household creation with the first Admin membership.
- Atomic Admin transfer without ever leaving a tenant without an Admin.
- Tenant-scoped foreign keys and unique constraints.
- Transactional task, inventory, expense, and budget updates.
- Reliable outbox writes in the same transaction as domain changes.
- Filtered queries for roles, assigned tasks, low stock, budgets, bills, and documents.
- Strong consistency for recurring purchase occurrence idempotency.
- Optional `pgvector` support without introducing a second database for conversation memory.

## Technology responsibilities

| Need | Technology | Reason |
|---|---|---|
| Users, tenants, memberships, tasks, inventory, finance, maintenance, metadata | PostgreSQL | ACID transactions, joins, constraints, indexes, migrations |
| Receipt images, PDFs, warranties, bills, uploaded documents | Object storage | Durable binary storage, private access policies, lifecycle management |
| Short-lived cache and rate limits | Redis, optional | Fast ephemeral data; never authoritative |
| Reliable async delivery | PostgreSQL outbox + worker | Simple MVP reliability and transactional consistency |
| Semantic conversation retrieval | PostgreSQL + `pgvector`, optional | Keeps conversation data and vector index under tenant-aware controls |
| Full-text filtering | PostgreSQL full-text search initially | Sufficient for household names, document metadata, and task text |

## Why not use another primary database?

- **Document database:** flexible documents are not the dominant shape. The system needs joins and invariants across memberships, roles, tenants, tasks, expenses, and linked documents.
- **Graph database:** cross-domain answers are bounded queries composed by the orchestrator, not arbitrary graph traversal.
- **Separate vector database:** conversational memory starts as structured `AgentInteraction` records; semantic search is optional and can use `pgvector` later.
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

Use PostgreSQL Row-Level Security as defense in depth when the application connection model supports setting a trusted transaction-local tenant value. Application authorization remains mandatory; RLS does not replace role checks.

## Consistency boundaries

Use one database transaction for:

- Household creation plus first Admin membership.
- Admin transfer plus current/target membership updates.
- Task or purchase mutation plus outbox event.
- Expense creation plus document-link metadata where both records are in PostgreSQL.
- Recurring occurrence creation using a unique `(tenant_id, rule_id, occurrence_date)` constraint.

Do not hold a database transaction open while calling an LLM, OCR provider, email provider, or object-storage upload. Persist an operation state and complete external work asynchronously.

## Outbox and workers

The module transaction writes both domain state and `outbox_messages`. A publisher claims messages with leases, sends them to notification or worker adapters, and records attempts. Consumers use `(tenant_id, event_id)` or an equivalent idempotency key.

The MVP can run this with PostgreSQL and a worker process. Add a broker such as Azure Service Bus or Kafka only when throughput, delivery topology, or team ownership justifies it.

## Data lifecycle

- Use object-storage lifecycle rules for abandoned uploads and expired temporary files.
- Keep financial and membership audit records according to the product retention policy.
- Soft-delete or status-transition tenant records where history matters; avoid hard deletion of expenses, role changes, and audit events.
- Deleting a tenant requires an explicit Admin-only workflow, export/retention handling, and a delayed purge job.
