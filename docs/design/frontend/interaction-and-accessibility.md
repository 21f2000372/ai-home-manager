# Interaction and Accessibility

## Responsive layout

Design for three practical layouts:

- **Mobile:** bottom navigation for primary tenant views, stacked sections, full-width forms, sticky save/submit action where appropriate.
- **Tablet:** compact side navigation, two-column dashboard sections, split list/detail where space permits.
- **Desktop:** persistent tenant navigation, dense tables for Admin workflows, side-by-side list/detail and calendar views.

The active tenant, role, and page title must remain visible at every viewport. Do not rely on hover-only actions or horizontal scrolling for core workflows.

## Interaction standards

- Use a clear primary action per screen.
- Use confirmation dialogs for role changes, Admin transfer, deletion/removal, and finance record creation from uncertain OCR.
- Use inline validation for forms and preserve drafts after recoverable errors.
- Show conflict warnings before calendar submission and allow the user to revise or continue only where the policy permits.
- Show parsed chat commands as editable structured fields before executing ambiguous writes.
- Use status badges with text, not color alone: Pending, Active, Rejected, Scheduled, Purchased, Low stock, Processing, Linked.
- Use familiar icons with accessible labels for navigation, upload, notifications, filters, and list actions.

## Accessibility requirements

Target WCAG 2.2 AA:

- Full keyboard operation for navigation, dialogs, tables, calendars, grocery check-off, and chat.
- Visible focus indicators with sufficient contrast.
- Semantic headings, landmarks, labels, descriptions, and form error associations.
- Minimum touch target of 44 by 44 CSS pixels.
- Do not encode role, stock, financial, or conflict status by color alone.
- Announce async upload, extraction, save, notification, and error states with polite/live regions.
- Dialog focus is trapped and returned to the triggering control on close.
- Tables provide column headers and mobile alternatives where scanning becomes impractical.
- Calendar supports keyboard date navigation and an accessible list view.
- Respect reduced-motion preferences and avoid motion as the only status signal.

## Role-aware UX

| State | Experience |
|---|---|
| Admin | Full People & Permissions controls, finance, recurring bills, and tenant settings |
| Adult | Tasks, calendar, inventory, documents, maintenance, and permitted finance workflows |
| Child | Own tasks and shared calendar; no finance navigation or protected data |
| Guest | Read-only today's tasks/schedule; write controls absent or disabled with explanation |
| Pending | Approval status and personal details only; no tenant dashboard |

A disabled control should include a reason when the user can see the surrounding workflow. For sensitive finance or Admin features, prefer omission plus a neutral route-level forbidden state over revealing protected metadata.

## Form standards

- Labels describe the field; placeholders are examples only.
- Required fields are marked and validated on submit and, where useful, on blur.
- Assignee selectors list only members visible and valid for the active tenant.
- Age and personal details have privacy-aware visibility and are never exposed in public invite URLs.
- Recurrence forms preview the next occurrence before saving.
- Receipt/document forms show accepted types, size limits, upload progress, extraction confidence, and review controls.
- Destructive or privilege-changing actions require explicit confirmation and explain the consequence.

## Loading, empty, and error states

Every screen defines:

- Initial loading skeleton that preserves layout.
- Empty state with one useful next action.
- Retryable network error.
- Forbidden state for role restrictions.
- Tenant-switching state that prevents stale data display.
- Conflict state for calendar and Admin transfer races.
- Offline or interrupted upload state where applicable.

## Security-sensitive interaction rules

- Never display another tenant's data while a tenant switch is in progress.
- Do not place tokens, document URLs, receipt content, or finance responses in URLs or analytics payloads.
- Do not infer authorization from hidden controls; always handle a server `403`.
- Avoid exposing whether a tenant, member, or financial record exists when the current context is unauthorized.
