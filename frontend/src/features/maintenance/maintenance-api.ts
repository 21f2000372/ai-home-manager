import { request } from '@/lib/api/request';

export type Appliance = { appliance_id: string; name: string; brand: string | null; model: string | null; purchased_at: string | null; warranty_ends_at: string | null };
export type Warranty = Pick<Appliance, 'appliance_id' | 'name' | 'brand' | 'model' | 'warranty_ends_at'> & { days_remaining: number };
export type Issue = { issue_id: string; description: string; status: IssueStatus; priority: Priority; reported_by: string; accountable_to: string | null; appliance_id: string | null; created_at: string };
export type Repair = { repair_id: string; serviced_at: string; provider: string | null; cost_minor: number | null; currency: string; notes: string | null; appliance_id: string | null; logged_by: string };
export type Priority = 'Low' | 'Normal' | 'High';
export type IssueStatus = 'Open' | 'InProgress' | 'Resolved' | 'Closed';
export type ApplianceInput = Omit<Appliance, 'appliance_id'>;
export type IssueInput = Pick<Issue, 'description' | 'priority' | 'appliance_id'> & { status?: IssueStatus };
export type RepairInput = Pick<Repair, 'serviced_at' | 'provider' | 'cost_minor' | 'currency' | 'notes' | 'appliance_id'>;

const context = () => ({ correlationId: crypto.randomUUID() });
const json = (method: 'POST' | 'PUT', body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const getAppliances = () => request<Appliance[]>('/api/maintenance/appliances', {}, context());
export const getExpiringWarranties = () => request<Warranty[]>('/api/maintenance/appliances/warranties/expiring?days=30', {}, context());
export const createAppliance = (input: ApplianceInput) => request<Appliance>('/api/maintenance/appliances', json('POST', input), context());
export const updateAppliance = (id: string, input: ApplianceInput) => request<Appliance>(`/api/maintenance/appliances/${id}`, json('PUT', input), context());
export const deleteAppliance = (id: string) => request<{ message: string }>(`/api/maintenance/appliances/${id}`, { method: 'DELETE' }, context());

export const getIssues = () => request<Issue[]>('/api/maintenance/issues', {}, context());
export const createIssue = (input: IssueInput) => request<Issue>('/api/maintenance/issues', json('POST', input), context());
export const updateIssue = (id: string, input: Partial<IssueInput>) => request<Issue>(`/api/maintenance/issues/${id}`, json('PUT', input), context());
export const deleteIssue = (id: string) => request<{ message: string }>(`/api/maintenance/issues/${id}`, { method: 'DELETE' }, context());

export const getRepairs = () => request<Repair[]>('/api/maintenance/repairs', {}, context());
export const createRepair = (input: RepairInput) => request<Repair>('/api/maintenance/repairs', json('POST', input), context());
export const deleteRepair = (id: string) => request<{ message: string }>(`/api/maintenance/repairs/${id}`, { method: 'DELETE' }, context());
