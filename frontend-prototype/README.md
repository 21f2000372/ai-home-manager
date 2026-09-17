# 🏡 HomeOps: Privacy-Aware Multi-Agent Household Coordinator

> **"Tell HomeOps what changed. Ask HomeOps what needs to happen."**

HomeOps is a **privacy-aware multi-agent household intelligence system**. It maintains a shared, permission-aware household state and orchestrates specialized AI agents to convert natural-language household events into coordinated cross-domain actions.

---

## 🌟 Core Product Message

HomeOps is **not**:
- ❌ An isolated grocery shopping app
- ❌ A basic chatbot
- ❌ A simple to-do list manager
- ❌ A disconnected calendar

HomeOps **is**:
- ✅ **A privacy-aware multi-agent system** that reasons over a shared household state and coordinates tasks, resources, schedules, food, finances, and responsibilities according to household context and member permissions.

---

## 🤖 Multi-Agent Architecture

HomeOps utilizes a centralized **Orchestrator** that coordinates three concurrent specialist agents:

```
                          ┌───────────────────────────┐
                          │   User Natural Request    │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │    Central Orchestrator   │
                          │ (Intent, RBAC, Synthesis) │
                          └──────┬──────┬──────┬──────┘
                                 │      │      │
          ┌──────────────────────┘      │      └──────────────────────┐
          ▼                             ▼                             ▼
┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
│   Context Agent   │         │  Document Agent   │         │ Operations Agent  │
│ ───────────────── │         │ ───────────────── │         │ ───────────────── │
│ • Member Roles    │         │ • Verified RAG    │         │ • Inventory Check │
│ • Travel & Avail  │         │ • Low-Salt Directive│       │ • Budget Balances │
│ • Preferences     │         │ • Warranties & Rx │         │ • Task Dispatch   │
└─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
          │                             │                             │
          └──────────────────────┐      │      ┌──────────────────────┘
                                 ▼      ▼      ▼
                          ┌───────────────────────────┐
                          │   Shared Household State  │
                          │   (Reactive Pub/Sub Hub)  │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │  Coordinated Action Plan  │
                          │   (6 Connected Domains)   │
                          └───────────────────────────┘
```

### 1. **Central Orchestrator**
- Parses unstructured household input and routes domain sub-intents.
- Enforces caller Role-Based Access Control (RBAC) privacy boundaries.
- Synthesizes specialist agent outputs into an actionable, unified plan.

### 2. **Context Agent**
- Tracks household members, availability windows (e.g. *Mom traveling until Friday*), and roles.
- Manages contextual retrieval and dynamic capacity re-indexing.

### 3. **Document Agent (Verified Knowledge Base & RAG)**
- Ingests and extracts structured ground truths from household documents (e.g., *Dr. Verma's low-salt clinical directive #DOC-MED-01, Grandma's Rx #DOC-MED-02, Daikin AC warranty #DOC-WAR-03*).

### 4. **Operations Agent**
- Computes inventory deficits for upcoming guests (+4 relatives).
- Reassigns tasks from unavailable members to available members.
- Computes expense allocations against the ₹5,000 weekly budget.
- Schedules appliance maintenance prior to guest arrivals.

---

## 🔄 Standard 7-Stage Workflow

Every natural language request passes through an observable 7-stage pipeline:
$$\text{Capture} \longrightarrow \text{Understand} \longrightarrow \text{Authorize} \longrightarrow \text{Update} \longrightarrow \text{Plan} \longrightarrow \text{Act} \longrightarrow \text{Remember}$$

1. **Capture**: Ingests raw voice or text update.
2. **Understand**: Extracts entities, temporal deadlines, and domain tags.
3. **Authorize**: Checks caller persona permissions against requested domains.
4. **Update**: Syncs Context Agent with availability shifts.
5. **Plan**: Operations & Document Agents cross-solve domain constraints.
6. **Act**: Formulates structured action dispatches with 1-click execution.
7. **Remember**: Commits applied state changes to persistent memory.

---

## 🎯 Main Benchmark Scenario

The prototype is pre-configured to simulate this primary multi-constraint scenario:

> *"Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."*

### Simulated Synthesis:
- **Food & Inventory**: Missing groceries identified for 4 guests; strictly respects Dad's cardiologist-verified low-salt restriction (`DOC-MED-01`).
- **Finance**: Estimated groceries: **₹1,700**; Medicine: **₹900**; Estimated remaining budget: **₹2,400** (healthy buffer from ₹5,000).
- **Tasks**: Grocery shopping assigned to Rajesh; Mom's pending snack task reassigned to Rajesh; Guest room setup assigned to Aarav (Friday post-4 PM).
- **Maintenance**: Daikin AC filter service booked for Friday 10:00 AM under warranty (`DOC-WAR-03`) before relatives arrive.
- **Schedule**:
  - 💊 *Wednesday*: Grandma's Medicine Refill (₹900)
  - 🛒 *Thursday*: Hospitality Grocery Shopping (₹1,700)
  - 🔧 *Friday (10 AM)*: Daikin AC Tune-Up Visit
  - 🛏️ *Friday (4 PM)*: Guest Bedroom Linen Preparation
  - ✈️ *Friday (7 PM)*: Mom Returns from Travel
  - 👨‍👩‍👧‍👦 *Saturday (11 AM)*: 4 Relatives Arrive

---

## 🛡️ Role-Based Access Control (RBAC) & Privacy Demo

HomeOps features a live **Persona Switcher** in the top navigation bar:
- 👨‍💼 **Rajesh Sharma (Dad / Parent Admin)**: Full visibility into finances, medical records, all tasks, and plan execution.
- 👩‍💼 **Priya Sharma (Mom / Parent Admin)**: Full administrative visibility.
- 👦 **Aarav Sharma (Son / Teenager 16y)**: **Restricted access**. Financial balances and line items are redacted. Permitted to view assigned chores and shared household events.
- 👵 **Savitri Devi (Grandma / Elder Care)**: Healthcare & dietary visibility.

### Live Privacy Verification:
1. Switch to **Rajesh (Parent)** → Ask *"How much budget is remaining?"* → Responds: **"₹2,400 remaining of ₹5,000 budget with line items."**
2. Switch to **Aarav (Teenager)** → Ask the identical question → Responds: **"🛡️ Access Denied by Privacy Policy: Financial information is restricted for your role."**

---

## 🏗️ Code Architecture & Future Backend Readiness

The frontend is decoupled via clean service boundaries ready for future Python/FastAPI/Node backend replacement:

```
src/
├── services/
│   ├── api.js                # Standardized service boundary interface
│   ├── householdService.js   # Reactive Shared State store (pub/sub)
│   ├── agentService.js       # 3-Agent reasoning & 7-stage workflow simulator
│   └── mockData.js           # The Sharma Family synthetic dataset
├── context/
│   └── HouseholdContext.jsx  # React state provider & event dispatcher
└── components/
    ├── layout/               # Header (Persona Switcher), Sidebar, Guided Tour Modal
    ├── agents/               # Pipeline visualizer, DAG activity monitor, Plan card
    └── views/                # 11 Dedicated domain and system views
```

---

## 🚀 How to Run Locally

### Prerequisites
- Node.js (v18 or higher recommended)
- npm

### Quick Start
```bash
# 1. Clone repository or navigate to workspace
cd c:/projects/homeops

# 2. Install dependencies (already installed)
npm install

# 3. Start local development server
npm run dev
```

Open your browser and navigate to:
```
http://localhost:3000
```

### Production Build
```bash
npm run build
npm run preview
```
