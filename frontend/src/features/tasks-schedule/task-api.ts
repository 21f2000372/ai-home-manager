import { request } from '@/lib/api/request';
import type { CreateTaskInput, HouseholdMember, HouseholdTask, TaskStatus } from './task-types';

export type { CreateTaskInput, HouseholdMember, HouseholdTask, TaskPriority, TaskStatus } from './task-types';

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export type TaskQueryOptions = {
  assigned_to?: string;
  status?: TaskStatus | 'All';
};

export function getTasks(options: TaskQueryOptions = {}) {
  const params = new URLSearchParams();

  if (options.assigned_to) params.set('assigned_to', options.assigned_to);
  if (options.status && options.status !== 'All') params.set('status', options.status);

  const query = params.toString();
  return request<HouseholdTask[]>(query ? `/api/tasks?${query}` : '/api/tasks', {}, requestContext());
}

export function getHouseholdMembers() {
  return request<HouseholdMember[]>('/api/auth/members', {}, requestContext());
}

export function createTask(input: CreateTaskInput) {
  return request<{ task_id: string; title: string; status: TaskStatus }>('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...input,
      assigned_to: input.assigned_to || undefined,
      due_at: input.due_at || undefined,
    }),
  }, requestContext());
}

export function updateTask(taskId: string, input: CreateTaskInput) {
  return request<HouseholdTask>(`/api/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...input,
      assigned_to: input.assigned_to || undefined,
      due_at: input.due_at || undefined,
    }),
  }, requestContext());
}

export function updateTaskStatus(taskId: string, status: TaskStatus) {
  return request<{ task_id: string; status: TaskStatus }>(`/api/tasks/${taskId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }, requestContext());
}

