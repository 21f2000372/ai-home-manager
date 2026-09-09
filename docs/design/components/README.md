# AI Home Manager Component Designs

These component designs are derived from [the user stories](../../requirements/ai_home_manager_user_stories.md). Each file owns one bounded responsibility and contains a structural PlantUML component diagram, an internal structure diagram, a tenant-aware class diagram, story coverage, responsibilities, and domain rules.

The diagrams use components, interfaces, adapters, repositories, and dependency relationships. They intentionally do not use actors or user-action bubbles as the primary notation: user stories explain behavior, while these diagrams show the software parts that implement and collaborate for that behavior. The notation follows the [PlantUML component diagram documentation](https://plantuml.com/component-diagram).

Each feature has both an external component view and an internal structure view. The internal diagrams use nested UML 2 components as interaction points because the installed PlantUML renderer does not support the newer `portin` and `portout` keywords; their direction and contract are shown by the connector direction and the adjacent provided/required interface.

Each feature file now follows the same documentation pattern:

1. **Component diagram**: public component boundary, interfaces, adapters, repositories, and tenant isolation.
2. **Tenant-aware class diagram**: entities, policies, repositories, and services that implement the component.
3. **Internal structure diagram**: smaller collaborating components inside the boundary.
4. **Behavior diagrams**: sequence diagrams for runtime interactions; the People & Permissions component also includes a membership state machine.

The behavioral diagrams follow UML sequence/state-machine conventions: lifelines represent runtime participants, messages represent calls or events, `alt`/`opt` show conditional behavior, and state transitions show lifecycle rules. They keep tenant context explicit at every boundary and show authorization before protected work.

## Multi-tenant model

Every household is a tenant. A user can create one household or belong to multiple households, but every active request selects exactly one `tenantId` from the authenticated membership context. Household data is never selected by a client-supplied household ID alone.

- Identity authenticates the user; the active membership selects the tenant.
- Tenant context is propagated through commands, queries, events, jobs, and agent calls.
- Every tenant-owned entity has a `tenantId` and every repository applies tenant filtering.
- Authorization checks both the tenant membership and the role within that tenant.
- Unique constraints and idempotency keys include `tenantId` to prevent cross-household collisions.
- Background jobs iterate tenants explicitly and never run with an ambient global tenant.

| Component | Design file | Story coverage |
|---|---|---|
| People and Permissions | [01_user_people_household.md](01_user_people_household.md) | US-1.1 to US-1.7 |
| Tasks and Schedule | [02_tasks_schedule.md](02_tasks_schedule.md) | US-2.1 to US-2.6 |
| Food and Inventory | [03_food_inventory.md](03_food_inventory.md) | US-3.1 to US-3.6 |
| Finance and Budget | [04_finance_budget.md](04_finance_budget.md) | US-3.6 and US-4.1 to US-4.4 |
| Home and Maintenance | [05_home_maintenance.md](05_home_maintenance.md) | US-5.1 to US-5.3 |
| Household Documents | [06_documents.md](06_documents.md) | US-4.1, US-5.2, and US-6.1 |
| Conversation and Cross-Domain Orchestrator | [07_conversation_orchestrator.md](07_conversation_orchestrator.md) | US-2.1, US-3.2, US-4.2, US-6.2, and US-6.3 |

## Shared design rules

- Components communicate through commands, queries, and ports rather than direct database access.
- Authentication and role authorization happen before component handlers execute.
- Each component owns its state and business invariants.
- Chat and manual UI flows converge on the same application use case where they represent the same behavior.
- Cross-domain questions use bounded read ports and cannot bypass RBAC.
- Components expose narrow interfaces and depend on abstractions rather than concrete databases or external SDKs.
- Tenant isolation is enforced at the application and persistence boundaries, not only in the UI.
