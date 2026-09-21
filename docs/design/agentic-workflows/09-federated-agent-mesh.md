# Federated Agent Mesh Workflow

## Purpose

The backend assistant uses a federated agent mesh for multi-module CRUD and document/bill workflows. The goal is to keep each domain agent small, permissioned, and token-bounded while still allowing safe cross-module work such as:

- extract information from a bill document
- log the paid bill as a finance expense
- link the bill document to the created finance record
- update related inventory, maintenance, task, or schedule records through explicit public tools

The implementation lives under `backend/app/ai/agents`.

## Runtime Shape

```text
User message
  |
  v
retrieve
  |
  v
planner
  |  creates PlannedAction records with:
  |  - domain
  |  - domain_agent
  |  - allowed_tools
  |  - shared_services
  v
specialist
  |  binds only owned tools and public proxy tools for the current domain
  v
authorize
  |  validates role + routed domain + requested tool
  v
execute
  |  invokes the tool through ALL_TOOLS_BY_NAME
  v
next_action
  |  advances to the next planned action or final response
  v
save -> embed -> END
```

## Files

| File | Role |
|---|---|
| `domain_mesh.py` | Registry of domain agents, owned tools, public proxy tools, shared services, and delegation targets. |
| `planner.py` | API gateway layer. Splits the user request into domain-scoped actions and annotates each action with mesh metadata. |
| `specialist.py` | Reasoning layer. Builds a compact domain prompt and binds only tools exposed by the current domain mesh contract. |
| `permissions.py` | RBAC layer. Allows same-domain tools and explicit public proxy tools; rejects unknown or unregistered tool calls. |
| `execute.py` | Action layer. Invokes registered tools and records tool results. |
| `tools/document_tools.py` | Document CRUD, bill extraction, and document-to-record linking tools. |
| `tool_catalog.py` / `tool_catalog.txt` | Retrieval-friendly tool descriptions for compact tool selection. |

## Domain Agent Contracts

Each domain has an explicit contract in `DOMAIN_AGENT_SPECS`.

| Domain | Owns | Public proxy examples |
|---|---|---|
| `finance` | expenses, budgets, recurring bills | `get_document`, `extract_bill_information`, `link_document_to_record` |
| `documents` | document metadata, extraction, document links | `log_expense`, `create_recurring_bill` |
| `food` | grocery list and inventory CRUD | none by default |
| `tasks` | tasks, reminders, calendar-event CRUD | none by default |
| `maintenance` | appliances, issues, repairs | `get_document`, `link_document_to_record` |
| `general` | conversational answers | no tools |

This prevents a flat tool graph. For example, the finance agent can extract bill facts through an approved document proxy, but it does not receive every document update/delete tool.

## Bill and Document Workflow

### Extract bill details

1. User provides readable bill text or OCR output.
2. `planner` routes the action to `documents`.
3. `specialist` selects `extract_bill_information`.
4. `authorize` checks the user role is allowed for document extraction.
5. `execute` returns structured JSON-like facts:
   - payee
   - total amount in minor units
   - currency
   - candidate dates
   - invoice/reference number
   - category hint

If readable text is not available, the assistant should ask for bill text or an upload/OCR pipeline. It must not pretend OCR happened.

### Save bill metadata

Use `create_document` when the file is already stored and a `storage_key` is available. The document agent records metadata only:

- `storage_key`
- `document_type`
- `original_filename`
- `mime_type`

Binary file storage remains outside the agent tool.

### Log a paid bill

1. Extract bill facts through `extract_bill_information`.
2. Use finance tools such as `log_expense` for paid bills.
3. If a `document_id` and created finance record ID are both known, use `link_document_to_record`.

The document agent may call finance proxy tools only when they are listed in its mesh contract and pass RBAC.

### Link documents to module records

Use `link_document_to_record` with:

```json
{
  "document_id": "uuid",
  "linked_domain": "finance",
  "linked_record_id": "uuid"
}
```

Allowed linked domains are `finance`, `maintenance`, `food`, and `tasks`.

## Authorization Rules

The authorization layer enforces:

1. Unknown tools fail closed.
2. Tool/domain mismatches fail closed unless the tool is explicitly exposed as a public proxy in the routed domain.
3. Role checks use `TOOL_PERMISSIONS`.
4. If a proxy tool belongs to another domain, its owning-domain permission is used unless a routed-domain override exists.

This supports controlled cross-module CRUD without letting one domain agent call another module's raw database tools.

## Token Control

The specialist prompt is intentionally compact:

- invariant tool-calling rules come from `ToolPromptBuilder`
- only the current action is included
- candidate tools are bounded
- domain rules come from the mesh summary
- retrieved context is capped

This keeps each subgraph focused and avoids the token growth of a single mega-agent that knows every module.

## Failure Rules

- Missing amount, date, ID, storage key, or readable bill text: ask one clarification.
- Unauthorized tool: mark the current action unauthorized and continue to the next planned action.
- Tool error: mark the current action failed and include the tool result.
- Partial multi-action success: report which actions completed, failed, or were denied.
- Never invent IDs, document storage keys, bill amounts, due dates, or payment status.

## Extension Guide

To add a new module:

1. Add the module's tools under `backend/app/ai/agents/tools`.
2. Register them in `tools/__init__.py`.
3. Add tool ownership and permissions in `permissions.py`.
4. Add a `DomainAgentSpec` in `domain_mesh.py`.
5. Add tool catalog records for retrieval.
6. Add planner rules for routing common user language to the new domain.
7. Add policy tests for ownership, proxy exposure, and fail-closed behavior.

