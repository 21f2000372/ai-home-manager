# Backend Security and Operations

## Tenant isolation

Tenant isolation is enforced in layers:

1. Identity token establishes `userId`.
2. Tenant Context Resolver verifies an active membership.
3. Authorization checks tenant role and resource action.
4. Application use case receives immutable `TenantContext`.
5. Repository methods require tenant context and add `tenant_id` predicates.
6. Object storage adapters require tenant context and use tenant-scoped keys.
7. Events, jobs, caches, audit records, and logs carry tenant and correlation identifiers.
8. SQLite has no Row-Level Security, so repository tenant predicates, composite keys, connection-level foreign-key enforcement, and cross-tenant integration tests are mandatory.

No module may accept a bare user-supplied tenant ID as authorization evidence.

## RBAC matrix

| Role | Household administration | Tasks and schedule | Inventory | Finance | Documents |
|---|---|---|---|---|---|
| Admin | Full tenant administration | Read/write | Read/write | Read/write | Read/write |
| Adult | Read own membership | Read/write by domain policy | Read/write by domain policy | Read/write | Read/write by domain policy |
| Child | Own profile only | Own tasks and shared calendar read | Domain-specific read policy | Denied with 403 | Domain-specific policy |
| Guest | Own profile only | Today's schedule/tasks read-only | Read-only only if explicitly allowed | Denied with 403 | Read-only only if explicitly allowed |
| Pending | Approval status only | Denied | Denied | Denied | Denied |

The matrix is enforced in application authorization and tested again in sensitive domain policies.

## Authentication and authorization

- Validate JWT/OIDC tokens at the edge and map claims to a global `userId`.
- Do not place mutable tenant roles in long-lived tokens as the only source of truth; membership changes must take effect without waiting for token expiry.
- Resolve current role from the tenant membership store or a carefully invalidated cache.
- Use least privilege for service credentials and database roles.
- Keep Finance and Document ports behind authorization checks.

## Secrets and sensitive data

- Store database, object-storage, OCR, notification, and LLM credentials in a secret manager.
- Never log receipt contents, document binaries, access tokens, or LLM prompts containing sensitive finance data.
- Encrypt the SQLite database file and object storage at rest; use TLS in transit.
- Use private object storage containers/buckets and short-lived authorized download URLs.
- Hash invite codes at rest and expire/revoke them.
- Validate upload MIME type, size, extension, and malware status before processing.

## Audit events

Record tenant-scoped audit events for:

- Household creation and deletion requests.
- Invite creation, use, approval, rejection, and expiry.
- Role changes and Admin transfers.
- Finance access allowed/denied.
- Document upload, classification, linking, and download.
- Cross-tenant access attempts.

Audit events should contain actor, tenant, action, resource type/id, result, correlation ID, and timestamp, but no secrets or raw document content.

## Reliability and recovery

- SQLite: encrypted snapshots, transactionally consistent backup procedure, restore tests, and WAL checkpoint monitoring.
- Object storage: versioning and lifecycle rules for documents.
- Outbox: retry with exponential backoff, dead-letter state, and operator replay.
- Workers: leases, idempotency keys, bounded retries, and tenant-aware failure records.
- APIs: request timeouts, cancellation, payload limits, and idempotency for commands.
- LLM/OCR providers: circuit breakers and asynchronous retry; never hold a database transaction open during provider calls.

## Observability

Use structured logs and traces with:

- `correlationId`
- `tenantId` only where permitted by privacy policy
- `userId` or a privacy-safe actor identifier
- module and operation name
- result and latency

Metrics should be aggregated by module and tenant plan/size rather than exposing household names. Alert on authorization failures, cross-tenant attempts, outbox backlog, worker retry growth, database latency, and object-storage failures.

## Capacity and evolution

Start with SQLite plus object storage and a worker process. Add Redis for high-volume caching/rate limits. Move to a server database when concurrent writes or multiple active replicas exceed SQLite's single-writer model. Add a broker when outbox volume or independent scaling requires it. Split modules into services only after ownership, traffic, and operational boundaries justify the cost; retain the same tenant-aware ports and event contracts.
