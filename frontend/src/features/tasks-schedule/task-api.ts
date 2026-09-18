import { request } from '@/lib/api/request';

export type TaskStatus = 'Open' | 'InProgress' | 'Done' | 'Cancelled';
export type TaskPriority = 'Low' | 'Normal' | 'High';

export type HouseholdTask = {
  task_id: string;
  title: string;
  description: string | null;
  assigned_to: string | null;
  due_at: string | null;
  priority: TaskPriority;
  status: TaskStatus;
};

export type CreateTaskInput = {
  title: string;
  description?: string;
  due_at?: string;
  priority: TaskPriority;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function getTasks() {
  return request<HouseholdTask[]>('/api/tasks', {}, requestContext());
}

export function createTask(input: CreateTaskInput) {
  return request<{ task_id: string; title: string; status: TaskStatus }>('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}

export function updateTaskStatus(taskId: string, status: TaskStatus) {
  return request<{ task_id: string; status: TaskStatus }>(`/api/tasks/${taskId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }, requestContext());
}
