# Agentic Home Operations Workflows

These workflow documents describe how AI Home Manager uses multiple specialized agents to operate a household while preserving strong module ownership, tenant isolation, and human control.

Reference workflow image: [agentworkflow.jpeg](../../agentworkflow.jpeg)

The image is a visual reference for a stateful router, tool agents, validation, conditional loops, and notification. This design applies that shape to household operations, with security as the first gate rather than an afterthought.

## Workflow set

| Document | Bounded context | Primary agent capability |
|---|---|---|
| [System workflow](00-system-workflow.md) | Cross-cutting | Secure routing and orchestration |
| [People and permissions](01-people-permissions.md) | Household identity | Membership, roles, approvals |
| [Tasks and schedule](02-tasks-schedule.md) | Planning | Tasks, recurrence, calendar |
| [Food and inventory](03-food-inventory.md) | Household supplies | Stock, grocery lists, purchases |
| [Finance and budget](04-finance-budget.md) | Money control plane | Ledger, budgets, bills, forecasts |
| [Home and maintenance](05-home-maintenance.md) | Property operations | Issues, repairs, warranties |
| [Documents](06-documents.md) | Evidence and files | Upload, classification, linking |
| [Conversation orchestrator](07-conversation-orchestrator.md) | Agent coordination | Intent, plans, bounded delegation |
| [Federated agent mesh](09-federated-agent-mesh.md) | Backend AI runtime | Domain agents, shared tools, bill extraction |

## Non-negotiable agent rules

1. **Authenticate before interpreting.** Identity and active household membership are resolved before an LLM, parser, or domain agent receives user content.
2. **Authorize before tool use.** The plan is checked capability by capability. Denied capabilities are never sent to a domain port.
3. **Agents do not own domain state.** Agents translate intent into commands or bounded queries. Domain application services enforce invariants.
4. **Tenant context is explicit.** Every command, query, event, job, memory record, and object-storage operation carries `tenantId`, `userId`, `role`, and `correlationId`.
5. **Least data, least privilege.** An agent receives only the fields required for its task. Finance values and private documents are never included for unauthorized roles.
6. **Validate before side effects.** Mutating commands use domain validation, idempotency, and confirmation for material or irreversible changes.
7. **Human approval is a state, not a prompt suggestion.** High-risk operations remain `PendingApproval` until an authorized human confirms through the application boundary.
8. **Audit every decision.** Record actor, tenant, capability, policy result, tool calls, result classification, and correlation ID without storing secrets or unnecessary raw prompts.
9. **Fail closed.** Missing tenant context, stale authorization, ambiguous intent, policy failure, or provider failure produces no side effect.
10. **Cross-domain work uses ports.** Modules communicate through narrow command/query/event ports; no agent or module reads another module's tables.

## CRUD and WhatsApp contract

Every bounded module exposes CRUD through its own authorized application port. Agents may request these operations, but the owning module remains responsible for validation, tenant scope, role policy, optimistic concurrency, and idempotency.

| Operation | Contract | Notification behavior |
|---|---|---|
| Create | `create(context, command, idempotencyKey)` | Emit `EntityCreated` after commit. |
| Read | `read(context, query)` | Return a filtered read model. Send a WhatsApp summary only when the user explicitly requests it and policy allows it. |
| Update | `update(context, entityId, patch, expectedVersion)` | Emit `EntityUpdated` after commit. Reject stale versions. |
| Delete | `delete(context, entityId, expectedVersion)` | Emit `EntityDeleted` after commit. Prefer archive/soft-delete where audit or legal retention requires it. |

The transactional outbox publishes the event only after the module transaction succeeds. A WhatsApp Notification Adapter consumes the event, applies recipient authorization and data redaction, honors household opt-in and quiet hours, and sends a template message through the WhatsApp provider. WhatsApp delivery is retried independently and never rolls back the CRUD transaction.

WhatsApp messages must contain the operation, module, safe entity label, result status, timestamp, and correlation ID. They must not contain access tokens, invite secrets, private document contents, full financial details, or data the recipient cannot read in the active tenant. A failed delivery is audited and placed in a retry/dead-letter queue; it is never treated as a failed domain operation.

## Standard envelope

```json
{
  "correlationId": "uuid",
  "tenantId": "uuid",
  "userId": "uuid",
  "role": "Admin|Adult|Child|Guest",
  "sessionId": "uuid",
  "capability": "inventory.read",
  "idempotencyKey": "tenant-scoped-key",
  "dataClassification": "household|private|financial",
  "trace": { "parentId": "uuid" }
}
```

The envelope is validated at every module boundary. A client-supplied `tenantId` is only a selector; membership resolution is the source of truth.

## Cohesion and coupling test

A module workflow is cohesive when its agent can complete its work using its own application services, policies, repositories, and ports. Coupling is acceptable only through these contracts:

- `Membership Queries` for household membership checks.
- Narrow domain commands and read models for cross-domain requests.
- Domain events through the transactional outbox.
- Notification and document-link ports.

A proposed workflow fails review if an agent imports another module's repository, sends a raw SQL query, receives unrestricted household state, or makes an authorization decision from prompt text alone.
