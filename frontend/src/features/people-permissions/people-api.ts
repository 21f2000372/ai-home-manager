import { request } from '@/lib/api/request';

export type HouseholdRole = 'Admin' | 'Adult' | 'Child' | 'Guest';

export type PendingMember = {
  user_id: string;
  name: string;
  email: string;
  date_of_birth: string | null;
};

export type ActiveMember = {
  user_id: string;
  name: string;
  role: HouseholdRole;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function createInvite() {
  return request<{ invite_code: string }>('/api/auth/invite', { method: 'POST' }, requestContext());
}

export function getPendingMembers() {
  return request<PendingMember[]>('/api/auth/members/pending', {}, requestContext());
}

export function approveMember(userId: string, role: HouseholdRole) {
  return request<{ message: string }>(`/api/auth/members/${userId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  }, requestContext());
}

export function getActiveMembers() {
  return request<ActiveMember[]>('/api/auth/members', {}, requestContext());
}

export function changeMemberRole(userId: string, role: Exclude<HouseholdRole, 'Admin'>) {
  return request<{ message: string }>(`/api/auth/members/${userId}/role`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  }, requestContext());
}

export function transferAdmin(successorId: string) {
  return request<{ message: string }>('/api/auth/transfer-admin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ successor_id: successorId }),
  }, requestContext());
}
