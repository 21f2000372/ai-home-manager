export const tenantKeys = {
  root: (tenantId: string) => ['tenant', tenantId] as const,
  membership: (tenantId: string) => [...tenantKeys.root(tenantId), 'membership'] as const,
  tasks: (tenantId: string, filters: Record<string, unknown> = {}) => [...tenantKeys.root(tenantId), 'tasks', filters] as const,
  inventory: (tenantId: string, filter: Record<string, unknown> = {}) => [...tenantKeys.root(tenantId), 'inventory', filter] as const,
  finance: (tenantId: string, filter: Record<string, unknown> = {}) => [...tenantKeys.root(tenantId), 'finance', filter] as const,
  agentRun: (tenantId: string, runId: string) => [...tenantKeys.root(tenantId), 'agent-run', runId] as const,
};