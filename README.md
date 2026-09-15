# ai-home-manager

A multi-agent AI Home Manager for intelligent, secure, and personalized household management.

Household members interact through natural-language chat and document uploads.
Specialized AI agents (tasks, inventory, finance, calendar, maintenance,
documents) collaborate under a central orchestrator, grounded in the
household's own data via RAG, with role-based access enforced before any LLM
call.

---

## Tech stack

| Layer               | Technology                           |
| ------------------- | ------------------------------------ |
| Frontend            | React.js                             |
| Backend             | Python + Flask                       |
| Database / ORM      | SQLite3 + SQLAlchemy                 |
| LLM access          | OpenRouter API                       |
| Agent orchestration | LangGraph                            |
| RAG                 | Embeddings + vector store (ChromaDB) |
| Auth                | JWT + role-based access control      |

---

## Database (built and ready)

The database layer is complete: SQLAlchemy models for all six domains, an
init/seed script, and a role-aware RAG vector-store scaffold.

**Design note:** this is the **single-household, role-based** build
(roles: Admin / Adult / Child / Guest). There is intentionally **no
`tenant_id`** — see the handoff doc before writing queries.

### Quickstart

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. copy env template (optional; sensible defaults exist)
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 3. create the schema and seed one household of sample data
python -m scripts.seed --reset
```

This creates `ai_home_manager.db` at the project root.

### Seed logins (development only, password `password123`)

| Email           | Role  |
| --------------- | ----- |
| admin@home.test | Admin |
| adult@home.test | Adult |
| child@home.test | Child |
| guest@home.test | Guest |

### Using the database from code

```python
from sqlalchemy import select
from app.db.base import get_session
from app.models import User, Task

session = get_session()
try:
    users = session.scalars(select(User)).all()
finally:
    session.close()
```

### Full schema reference

See **[`docs/design/backend/database-handoff.md`](docs/design/backend/database-handoff.md)**
for the complete schema (all 20 tables, enums, constraints), an ER diagram,
usage examples, the RAG vector-store contract, and the design decisions the
backend team needs.

---

## Project layout

```text
app/
├── config.py          # env-driven configuration
├── db/                # engine, session, schema init
├── models/            # SQLAlchemy models (six domains)
├── auth/              # password hashing (JWT/RBAC: backend team)
└── rag/               # Chroma vector-store scaffold (role-aware retrieval)
scripts/
└── seed.py            # create schema + seed sample data
docs/                  # requirements, design, and planning documents
```
