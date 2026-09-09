# AI Home Manager Frontend Design

These documents define the frontend experience from the [user stories](../../requirements/ai_home_manager_user_stories.md), [component designs](../components/README.md), and [backend plan](../backend/README.md).

## Documents

| Document | Purpose |
|---|---|
| [frontend-architecture.md](frontend-architecture.md) | Application shell, frontend components, tenant context, and feature boundaries |
| [frontend-ui-ux-architecture.md](frontend-ui-ux-architecture.md) | Principal-level component hierarchy, routes, state coupling, component contracts, and user-story interaction flows |
| [navigation-and-screens.md](navigation-and-screens.md) | Routes, screen responsibilities, role-aware navigation, and key states |
| [state-and-api-integration.md](state-and-api-integration.md) | Server state, client state, API contracts, caching, mutations, and error handling |
| [interaction-and-accessibility.md](interaction-and-accessibility.md) | Responsive behavior, accessibility, forms, loading, empty, error, and permission states |

## Product principles

- The active household is always visible and switchable; data never silently crosses tenants.
- The UI reflects permissions, but backend authorization remains authoritative.
- Chat and manual workflows converge on the same domain action and show the same result states.
- Shared household information is scannable; sensitive finance information is never exposed through navigation or cached views for Child and Guest roles.
- Every feature has usable loading, empty, error, conflict, and forbidden states.
