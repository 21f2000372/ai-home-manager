# Backend Design

This folder translates the [user stories](../../requirements/ai_home_manager_user_stories.md) and [component designs](../components/README.md) into backend implementation decisions.

## Documents

| Document | Purpose |
|---|---|
| [database-architecture.md](database-architecture.md) | Database selection, storage responsibilities, tenancy, consistency, and scaling |
| [relational-schema.md](relational-schema.md) | Tenant-aware tables, relationships, indexes, and constraints |
| [backend-module-design.md](backend-module-design.md) | Module boundaries, ports, APIs, events, workers, and request flow |
| [security-and-operations.md](security-and-operations.md) | RBAC, tenant isolation, auditability, backups, observability, and recovery |

## Recommended backend data stack

- **PostgreSQL**: primary relational database and system of record.
- **PostgreSQL Row-Level Security**: defense-in-depth tenant isolation where supported by the chosen deployment model.
- **Object storage** such as Azure Blob Storage or S3-compatible storage: receipt, bill, warranty, image, and PDF binaries.
- **Redis**: optional cache, rate-limit store, distributed lock, and short-lived job coordination. It is not the source of truth.
- **PostgreSQL `pgvector`**: optional vector search for conversation memory; introduce it only when semantic retrieval is required.
- **Outbox table plus worker**: reliable domain-event delivery without requiring a separate message broker in the MVP.

The MVP should avoid adding a separate document database, graph database, or vector database. The stories are transactional and relational: memberships, roles, tasks, inventory, expenses, budgets, bills, repairs, and tenant boundaries require ACID transactions and referential integrity.
