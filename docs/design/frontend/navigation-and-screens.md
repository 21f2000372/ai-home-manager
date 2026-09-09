# Navigation and Screens

## Application shell

The shell uses a responsive two-level navigation:

- **Global:** household switcher, notifications, chat, current user menu.
- **Tenant:** Overview, Tasks, Calendar, Inventory, Finance, Maintenance, Documents, People & Permissions.

Finance is absent from Child and Guest navigation. A direct URL still receives a backend-driven forbidden state.

## Routes and screens

| Route | Screen | Main stories | Roles |
|---|---|---|---|
| `/welcome` | Sign in / register | US-1.1 | Unauthenticated |
| `/households/new` | Create household | US-1.1 | Authenticated |
| `/households/join` | Invite code/link and personal details | US-1.2 | Authenticated |
| `/households/select` | Household switcher | Multi-tenant | Users with multiple memberships |
| `/t/:tenantId/overview` | Household overview | Cross-domain summary | Active members |
| `/t/:tenantId/tasks` | My tasks / household tasks | US-2.2, US-2.3 | Active members |
| `/t/:tenantId/tasks/new` | Manual task form | US-2.2 | Adult/Admin |
| `/t/:tenantId/calendar` | Shared calendar | US-2.5, US-2.6 | Active members |
| `/t/:tenantId/inventory` | Stock and low-stock view | US-3.1, US-3.2 | Active members |
| `/t/:tenantId/grocery` | Grocery list | US-3.3, US-3.4 | Active members |
| `/t/:tenantId/commodities` | Recurring commodities | US-3.5, US-3.6 | Adult/Admin; read policy for others |
| `/t/:tenantId/finance` | Budget, expenses, bills | US-4.1 to US-4.4 | Adult/Admin |
| `/t/:tenantId/maintenance` | Issues, repairs, appliances | US-5.1 to US-5.3 | Adult/Admin |
| `/t/:tenantId/documents` | Documents and links | US-6.1 | Active members |
| `/t/:tenantId/people` | Members, pending invites, roles | US-1.3 to US-1.5 | Admin; own membership for others |
| `/t/:tenantId/chat` | Conversation workspace | US-2.1, US-3.2, US-4.2, US-6.2, US-6.3 | Active members |

## Screen composition

### Overview

- Active household name and tenant switcher.
- Today’s tasks and calendar commitments.
- Low-stock and upcoming bill indicators according to role.
- Recent notifications.
- Quick actions only when permitted: add task, add grocery item, upload document, report issue.

### People & Permissions

- Active members table: name, age/details visibility, role, status.
- Pending members queue with approve, reject, and role assignment.
- Role-change confirmation dialog.
- Admin-transfer flow with target confirmation and expiry state.
- No personal details of pending members are shown to non-Admins.

### Tasks and calendar

- Default task filter is “Assigned to me”; users can switch to household view when permitted.
- Manual task form supports title, description, assignee, due date, priority, and recurrence.
- Chat-created tasks show parsed fields and require confirmation when ambiguity exists.
- Calendar event creation shows overlap warnings before final submission.

### Inventory and grocery

- Low-stock section uses threshold status, not only a binary empty state.
- Grocery items can be checked off without leaving the list.
- Commodity setup includes quantity, unit, recurrence, preferred brand, and threshold.
- Purchase completion can open an optional cost/receipt step and then updates stock.

### Finance and documents

- Finance dashboard shows budget remaining, recent expenses, and upcoming bills.
- Receipt upload shows upload, extraction, review, save, and link states.
- Document cards show type, processing status, linked domain, and authorized actions.
- Child and Guest users never receive finance data in initial route data, cache, or prefetches.

## Navigation states

- **No tenant:** explain that a household must be created or joined.
- **Pending membership:** show approval status and notification preferences only.
- **Tenant switch pending:** preserve shell, cancel stale feature requests, show a small context-loading state.
- **Forbidden:** explain that the current role cannot access the resource without revealing protected data.
- **Tenant not found:** use a neutral not-found state to avoid cross-tenant existence leakage.
