# AI Agent Architecture

## Overview

The assistant is a multi-domain household management agent built on
**LangGraph**, using a federated domain-agent mesh over the existing
retrieve → planner → specialist → authorize → execute pipeline. It is exposed
to the app via a single entry point, `run_agent()`, called from the
`/api/agent/message` Flask route.

LLM calls go through `langchain_openai.ChatOpenAI`, pointed at OpenRouter
via `OPENROUTER_BASE_URL` / `OPENROUTER_API_KEY`. Interaction history is
persisted to SQLite (SQLAlchemy) and, best-effort, embedded into a Chroma
vector store for role-aware retrieval-augmented context in later turns.

## Graph Topology

```
                 ┌────────────┐
   entry ───────►│  retrieve  │  (recent AgentInteraction rows)
                 └─────┬──────┘
                       ▼
                 ┌────────────┐
                 │  planner   │  (splits message into PlannedActions)
                 └─────┬──────┘
                       ▼
      ┌───────────►┌────────────┐
      │            │ specialist │  (per-domain ReAct step, ≤1 tool call)
      │            └─────┬──────┘
      │        no tool   │   tool requested
      │        needed    ▼
      │            ┌────────────┐
      │            │ authorize  │  (RBAC: role × domain × tool)
      │            └─────┬──────┘
      │      unauthorized│   authorized
      │                  ▼
      │            ┌────────────┐
      │            │  execute   │  (invoke tool, wrap ToolMessage)
      │            └─────┬──────┘
      │                  │
      └──────────────────┘  (execute → specialist, to inspect the result)
                       │
                       ▼
                 ┌────────────┐
                 │next_action │  (advance action index / finalize)
                 └──┬──────┬──┘
         more actions      all done
                 │              ▼
                 │        ┌────────────┐
                 │        │    save    │  (persist AgentInteraction)
                 │        └─────┬──────┘
                 │              ▼
                 │        ┌────────────┐
                 │        │   embed    │  (best-effort vector upsert)
                 │        └─────┬──────┘
                 │              ▼
                 └────────►    END
        (back to specialist)
```

## Nodes

| Node | File | Responsibility |
|---|---|---|
| `retrieve` | `memory.py` | Loads the last 10 `AgentInteraction` rows for the current conversation/session as short-term context. |
| `planner` | `planner.py` | API gateway layer. Uses deterministic fast paths and structured output to decompose the user message into independent actions, then annotates each action with `domain_agent`, `allowed_tools`, and `shared_services` from the mesh registry. |
| `specialist` | `specialist.py` | Per-action domain agent. Builds a compact prompt from the current action and the mesh contract, binds only owned tools plus explicit public proxy tools, forces `parallel_tool_calls=False`, and returns either a final response or exactly one pending tool call. |
| `authorize` | `authorize.py` / `permissions.py` | RBAC gate. Validates role, routed domain, and requested tool against the mesh and `TOOL_PERMISSIONS`. Same-domain tools and explicit public proxy tools are allowed; unknown tools fail closed. |
| `execute` | `execute.py` | Invokes the tool via `ALL_TOOLS_BY_NAME`, captures the result (or failure) as a `ToolMessage`, and records it on the current `PlannedAction`. |
| `next_action` | `actions.py` | Marks the current action `completed` / `unauthorized` / `failed`, advances `current_action_index`, and builds the final human-readable response once all actions are processed. |
| `save` | `memory.py` | Persists the turn as a `Conversation` / `AgentInteraction` row (system of record). |
| `embed` | `memory.py` | Best-effort embeds a `User asked / Assistant replied` summary into Chroma, tagged with `domain_min_role(domain)` so retrieval respects RBAC regardless of which role triggered the original turn. |

## State

`AgentState` (TypedDict) carries, per turn:

- **Request context**: `session_id`, `user_id`, `role`, `conversation_id`, `current_datetime`, `message`
- **RAG**: `retrieved_context`
- **Conversation**: `messages` (LangChain message list, `add_messages`-reduced)
- **Planning**: `planned_actions`, `current_action_index`
- **Mesh metadata per action**: `domain_agent`, `allowed_tools`, `shared_services`, `delegated_from`
- **In-flight tool call**: `pending_tool_call`, `pending_ai_message`, `tool_result`
- **Authorization**: `authorized`, `auth_error`
- **Loop safety**: `iteration`, `max_iterations` (default 5)
- **Output**: `finished`, `response`, `interaction_id`, `embedded`

## Domains, Mesh, and Tools

Registered in `tools/__init__.py`, one module per domain:

- **finance** — `log_expense`, `create_budget`, `create_recurring_bill`, plus list/get/update/delete for each
- **tasks** — `create_task`, `complete_task`, calendar event CRUD
- **food** — grocery list CRUD, `mark_purchased`, inventory CRUD
- **maintenance** — appliance CRUD, issue CRUD, repair CRUD
- **documents** — document metadata CRUD, bill extraction, document links
- **general** — no tools; conversational only

The federated mesh is registered in `domain_mesh.py`. Each `DomainAgentSpec`
declares:

- owned tools
- public proxy tools from other domains
- shared MCP-style services
- allowed delegation targets
- domain-specific prompt rules

This prevents a flat tool graph. A finance action can use approved document
proxies such as `extract_bill_information`, but it cannot call arbitrary
document update/delete tools.

## Authorization Model (`permissions.py`)

- `TOOL_DOMAINS`: tool name → owning domain (defense against a specialist calling a tool outside its routed domain)
- `TOOL_PERMISSIONS`: `(domain, tool)` → minimum `HouseholdRole`; unlisted pairs fall back to `DEFAULT_MIN_ROLE = ADULT` (fail-closed)
- `allowed_tool_names_for_domain(domain)`: mesh-derived list of owned and public proxy tools available to the routed domain
- `DOMAIN_MIN_ROLE`: minimum role to *retrieve* embedded content from a domain, keyed by domain rather than by whichever role happened to trigger the original interaction (e.g. any Adult can retrieve finance history, not just the Admin who logged it)

## Bill and Document Workflow

Document tools now support:

- `extract_bill_information`: heuristic extraction from readable bill, receipt, invoice, or statement text
- `link_document_to_record`: link a stored document to a finance, maintenance, food, or task record
- `list_document_links`: inspect document-to-record links

The agent must not claim OCR or binary upload occurred. If readable bill text
is missing, it asks for the text or upload/OCR pipeline. Paid bills are logged
through finance tools, then linked to the source document when IDs are known.

Detailed flow: [Federated agent mesh](09-federated-agent-mesh.md).

## Notable Design Choices

- **Deferred message commit**: the specialist's tool-call `AIMessage` is held in `pending_ai_message` and only appended to `messages` inside `execute`, after authorization passes — keeps rejected/unauthorized tool calls out of the LLM's conversation history entirely.
- **Single tool call per specialist turn**: `parallel_tool_calls=False` plus explicit truncation to `tool_calls[0]` if the model returns more than one, with a warning log.
- **Two independent context layers**: `retrieve_node` (recent SQL history, always available) vs. the router's/planner's vector-store lookup (semantic, RBAC-filtered, best-effort — failures are swallowed since retrieval is an enhancement, not a blocking dependency).
- **Loop safety**: `max_iterations` (default 5) caps specialist re-entries per action to prevent runaway tool-call loops.

## Current Components
| Component                        | Status                    |
|-----------------------------------|----------------------------|
| Flask API                         | ✅                         |
| `run_agent()`                     | ✅                         |
| LangGraph orchestration           | ✅                         |
| Conversation retrieval            | ✅                         |
| Planner / multi-intent routing    | ✅                         |
| Federated domain mesh             | ✅                         |
| Specialist domain agents          | ✅                         |
| Sequential tool execution         | ✅                         |
| Tool-call sanitization            | ✅                         |
| Authorization                     | ✅                         |
| CRUD tools                        | ✅                         |
| Bill text extraction              | ✅ heuristic               |
| Document-to-record links          | ✅                         |
| Memory persistence                | ✅                         |
| Embedding/retrieval               | ✅                         |
| Bulk grocery handling             | 🔧 Being refined           |
| Entity resolution                 | 🔧 Next architecture piece |
| Family graph                      | 🔧 Planned                 |
| Duplicate detection               | ❌ Not implemented         |
| User confirmation                 | ❌ Not implemented         |
