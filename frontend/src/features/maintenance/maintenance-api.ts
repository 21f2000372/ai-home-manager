import { request } from '@/lib/api/request';
import type {
  Appliance,
  CreateApplianceInput,
  CreateIssueInput,
  ExpiringWarranty,
  IssueFilters,
  LogRepairInput,
  MaintenanceIssue,
  Repair,
  UpdateApplianceInput,
  UpdateIssueInput,
} from './maintenance-types';

export type {
  Appliance,
  CreateApplianceInput,
  CreateIssueInput,
  ExpiringWarranty,
  IssueFilters,
  IssueStatus,
  LogRepairInput,
  MaintenanceIssue,
  MaintenancePriority,
  MaintenanceSummary,
  Repair,
  UpdateApplianceInput,
  UpdateIssueInput,
} from './maintenance-types';

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

const base = '/api/maintenance';

export type HouseholdMember = {
  user_id: string;
  name: string;
  role: 'Admin' | 'Adult' | 'Child' | 'Guest';
};

export function getHouseholdMembers() {
  return request<HouseholdMember[]>('/api/auth/members', {}, requestContext());
}

// --- Appliances & warranties (US-5.2) ---

export function getAppliances() {
  return request<Appliance[]>(`${base}/appliances`, {}, requestContext());
}

export function getExpiringWarranties(days = 30) {
  const params = new URLSearchParams();
  params.set('days', String(days));
  return request<ExpiringWarranty[]>(`${base}/appliances/warranties/expiring?${params.toString()}`, {}, requestContext());
}

function cleanAppliancePayload(input: CreateApplianceInput | UpdateApplianceInput) {
  return {
    ...input,
    name: input.name?.trim() || undefined,
    brand: input.brand?.trim() || undefined,
    model: input.model?.trim() || undefined,
    purchased_at: input.purchased_at || undefined,
    warranty_ends_at: input.warranty_ends_at || undefined,
  };
}

export function createAppliance(input: CreateApplianceInput) {
  return request<{ appliance_id: string; name: string; brand: string | null; model: string | null; warranty_ends_at: string | null }>(
    `${base}/appliances`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cleanAppliancePayload(input)),
    },
    requestContext(),
  );
}

export function updateAppliance(applianceId: string, input: UpdateApplianceInput) {
  return request<{ appliance_id: string; name: string; brand: string | null; model: string | null; warranty_ends_at: string | null }>(
    `${base}/appliances/${applianceId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cleanAppliancePayload(input)),
    },
    requestContext(),
  );
}

export function deleteAppliance(applianceId: string) {
  return request<{ message: string }>(`${base}/appliances/${applianceId}`, { method: 'DELETE' }, requestContext());
}

// --- Maintenance issues (US-5.3) ---

export function getIssues(filters: IssueFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== 'All') params.set('status', filters.status);
  if (filters.appliance_id) params.set('appliance_id', filters.appliance_id);
  const query = params.toString();
  return request<MaintenanceIssue[]>(query ? `${base}/issues?${query}` : `${base}/issues`, {}, requestContext());
}

export function reportIssue(input: CreateIssueInput) {
  return request<{ issue_id: string; description: string; status: string; priority: string }>(
    `${base}/issues`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: input.description.trim(),
        priority: input.priority,
        appliance_id: input.appliance_id || undefined,
        accountable_to: input.accountable_to || undefined,
      }),
    },
    requestContext(),
  );
}

export function updateIssue(issueId: string, input: UpdateIssueInput) {
  return request<{ issue_id: string; description: string; status: string; priority: string; accountable_to: string | null }>(
    `${base}/issues/${issueId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: input.description?.trim() || undefined,
        status: input.status,
        priority: input.priority,
        accountable_to: input.accountable_to || undefined,
      }),
    },
    requestContext(),
  );
}

export function deleteIssue(issueId: string) {
  return request<{ message: string }>(`${base}/issues/${issueId}`, { method: 'DELETE' }, requestContext());
}

// --- Repairs & service history (US-5.1, create + delete only) ---

export function getRepairs(applianceId?: string) {
  const params = new URLSearchParams();
  if (applianceId) params.set('appliance_id', applianceId);
  const query = params.toString();
  return request<Repair[]>(query ? `${base}/repairs?${query}` : `${base}/repairs`, {}, requestContext());
}

export function logRepair(input: LogRepairInput) {
  return request<{ repair_id: string; serviced_at: string; provider: string | null; cost_minor: number | null }>(
    `${base}/repairs`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        serviced_at: input.serviced_at,
        appliance_id: input.appliance_id || undefined,
        provider: input.provider?.trim() || undefined,
        cost_minor: input.cost_minor ?? undefined,
        currency: input.currency || 'USD',
        notes: input.notes?.trim() || undefined,
      }),
    },
    requestContext(),
  );
}

export function deleteRepair(repairId: string) {
  return request<{ message: string }>(`${base}/repairs/${repairId}`, { method: 'DELETE' }, requestContext());
}
