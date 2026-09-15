# AI Home Manager — User Stories

Organized by domain, following your six-domain schema. Each story uses the standard format
(**As a / I want / So that**) with acceptance criteria, and is tagged with the role(s) it applies to.

---

## 1. People & Permissions (Auth + RBAC)

**US-1.1 — Create a household**
As a new user, I want to register and automatically become the Admin of a new household,
so that someone is always accountable for managing members and settings.
- *Acceptance:* First user to register for a household is auto-assigned the Admin role; no separate "make me admin" step exists.

**US-1.2 — Join an existing household**
As a family member, I want to join my household using an invite code or link,
so that I don't have to create a duplicate household by mistake.
- *Acceptance:* Before joining, the invitee provides basic personal details, including name and age; the account enters a pending-member state and cannot access household data until an Admin assigns a role.

**US-1.3 — Approve a new member and assign a role**
As an Admin, I want to review the details of a person joining through my invite code or link and assign Adult, Child, or Guest,
so that household access reflects the person's age, relationship, and responsibility.
- *Acceptance:* Only Admins can approve pending members and assign their role; the invitee is notified of the decision; personal details are visible only to authorized household administrators.

**US-1.4 — Manage member roles**
As an Admin, I want to change another member's role (Adult, Child, Guest),
so that access matches their real responsibility and trust level in the household.
- *Acceptance:* Only Admins can change roles; system blocks demoting the last remaining Admin.

**US-1.5 — Transfer household administration**
As an Admin, I want to transfer the Admin role to another Adult member,
so that household management can continue when responsibility changes.
- *Acceptance:* Only the current Admin can initiate the transfer; the new Admin must explicitly confirm; the previous Admin becomes an Adult; the system never allows a household without an Admin.

**US-1.6 — Role-scoped visibility**
As a Child, I want to see my own tasks and the shared calendar,
so that I can stay organized without being exposed to financial or admin information.
- *Acceptance:* Expense, Budget, and Bill endpoints return 403 for Child-role tokens.

**US-1.7 — Guest read-only access**
As a Guest (e.g., a relative or sitter), I want read-only access to today's schedule and tasks,
so that I can help out without being able to change household data.
- *Acceptance:* Guest role has "read" permission only, no "write"/"delete" on any resource.

---

## 2. Tasks & Schedule

**US-2.1 — Create a task via chat**
As an Adult member, I want to type "remind Sam to take out the trash Friday" in chat,
so that I can create a task quickly using natural language.
- *Acceptance:* Task Agent parses assignee, action, and due date; validates the household member and creates a Task row.

**US-2.2 — Create a task manually**
As an Adult member, I want to create a task through a manual form,
so that I can enter structured details when chat is inconvenient or ambiguous.
- *Acceptance:* The form supports title, description, assignee, due date, priority, and optional recurrence; required fields are validated and the task follows the same permissions and storage rules as a chat-created task.

**US-2.3 — View my assigned tasks**
As any household member, I want to see a filtered list of tasks assigned specifically to me,
so that I know what I'm responsible for without scanning the whole household list.

**US-2.4 — Recurring chores**
As an Admin, I want to set up a recurring weekly chore (e.g., "take out trash every Friday"),
so that I don't have to recreate the same task manually every week.

**US-2.5 — Shared calendar visibility**
As an Adult member, I want to see everyone's calendar events in one shared view,
so that I can plan around the household's commitments, not just my own.

**US-2.6 — Cross-domain reminder**
As a household member, I want the system to warn me if a new event conflicts with an existing one,
so that I don't double-book without realizing it.
- *Acceptance:* Calendar Agent checks for time-overlap on create and returns a conflict warning.

---

## 3. Food & Inventory

**US-3.1 — Low-stock alerts**
As an Adult member, I want to be notified when an inventory item drops below a threshold,
so that we don't run out of essentials unexpectedly.

**US-3.2 — Ask what's running low**
As any member, I want to ask "what are we out of?" in chat,
so that I get a quick grocery list without opening the inventory screen.
- *Acceptance:* Inventory Agent queries items where quantity ≤ low_stock_threshold and returns a summarized list.

**US-3.3 — Build a grocery list from a recipe or meal plan**
As an Adult member, I want to say "we're having pasta Saturday, what do we need,"
so that the system cross-references inventory and suggests what to buy.

**US-3.4 — Mark grocery items purchased**
As any member, I want to check off items on the grocery list as I shop,
so the list stays accurate for whoever shops next.

**US-3.5 — Manage recurring daily commodities**
As a household member, I want to add commodities such as milk, bread, or eggs to a daily or custom recurring shopping list,
so that routine purchases are remembered and can be bought without adding them from scratch each day.
- *Acceptance:* A member can set an item, quantity, unit, recurrence schedule, preferred brand, and optional low-stock threshold; each occurrence appears on the active grocery list and can be marked purchased or skipped.

**US-3.6 — Track recurring commodity consumption**
As an Adult member, I want recurring commodity purchases to update inventory and optionally record their cost,
so that stock levels and household spending remain accurate over time.
- *Acceptance:* Marking an occurrence purchased updates inventory; the user can enter or attach a receipt for the price; low-stock alerts and budget calculations include these items.

---

## 4. Finance & Budgeting

**US-4.1 — Log an expense from a receipt photo**
As an Adult member, I want to upload a photo of a grocery receipt,
so that the expense is logged automatically without manual data entry.
- *Acceptance:* Document is parsed, an Expense record is created, and the Document is linked back via `linked_domain`/`linked_record_id`.

**US-4.2 — Check budget status**
As an Adult member, I want to ask "how much is left in the groceries budget this month,"
so that I can make informed spending decisions in the moment.

**US-4.3 — Bill due reminders**
As an Admin, I want to be reminded a few days before a recurring bill is due,
so that nothing is paid late.

**US-4.4 — Restrict financial visibility**
As an Admin, I want Expense, Bill, and Budget data hidden from Child and Guest roles,
so that sensitive financial information stays within trusted members only.
- *Acceptance:* Enforced at the Authorize step before any Finance Agent call, not just hidden in the UI.

---

## 5. Home & Maintenance

**US-5.1 — Log a repair**
As an Adult member, I want to log that the dishwasher was serviced and by whom,
so that we have a maintenance history if the same issue recurs.

**US-5.2 — Warranty tracking**
As an Admin, I want to be notified when an appliance's warranty is about to expire,
so that I can get repairs done while still covered.

**US-5.3 — Report an issue**
As any Adult member, I want to submit a maintenance request ("the AC is making noise"),
so that it's tracked and not forgotten in a group chat.

---

## 6. Documents + Cross-Domain Reasoning

**US-6.1 — Upload any household document**
As any member, I want to upload a bill, warranty, or receipt as a photo or PDF,
so that it's stored, parsed, and linked to the right domain automatically.

**US-6.2 — Ask a cross-domain question**
As an Adult member, I want to ask "can we afford groceries and still make Saturday's dinner,"
so that the system reasons across Inventory, Expenses, and Calendar in one answer instead of me checking three screens.
- *Acceptance:* Orchestrator's Plan step routes the query to Inventory Agent, Expense Agent, and Calendar Agent, and synthesizes a single combined response.

**US-6.3 — Conversational memory**
As a returning user, I want the system to remember context from a recent conversation,
so that I don't have to repeat information I already gave it.
- *Acceptance:* Remember step persists `AgentInteraction` records the orchestrator can reference in the same session.

---

## Suggested MVP scope (first sprint)

If you need to cut scope for a first working demo, prioritize in this order:
1. US-1.1, US-1.2, US-1.3, US-1.4, US-1.5 (auth + RBAC — the foundation everything else needs)
2. US-2.1, US-2.2, US-2.3 (single working agent, manual entry, and task views prove the whole pipeline)
3. US-3.2, US-4.2 (a second and third agent, proves multi-agent works)
4. US-6.2 (cross-domain reasoning — the actual "innovation" claim in your proposal)

Everything else (admin transfer, recurring tasks and commodities, warranty tracking, document OCR) is real value but can follow
once the core pipeline is proven end-to-end.
