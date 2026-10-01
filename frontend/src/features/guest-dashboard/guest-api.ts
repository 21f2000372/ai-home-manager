import { request } from '@/lib/api/request';

/**
 * A task assigned to the current user, surfaced to a Guest as a notification.
 * Reuses the existing /api/tasks endpoints — no dedicated notifications table.
 */
export type GuestNotification = {
  task_id: string;
  title: string;
  description: string | null;
  assigned_to: string | null;
  due_at: string | null;
  priority: 'Low' | 'Normal' | 'High';
  status: 'Open' | 'InProgress' | 'Done' | 'Cancelled';
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

/**
 * Fetch the notifications for the logged-in guest: tasks assigned to them
 * that are still Open (awaiting a response). Uses the existing task list
 * endpoint with the assigned_to=me + status=Open filters.
 */
export function getGuestNotifications() {
  return request<GuestNotification[]>('/api/tasks?assigned_to=me&status=Open', {}, requestContext());
}

/** Fetch tasks the guest has already responded to (accepted / rejected). */
export function getGuestResponded() {
  return request<GuestNotification[]>('/api/tasks?assigned_to=me', {}, requestContext());
}

/** Accept a notification → task moves to InProgress. */
export function acceptNotification(taskId: string) {
  return request<{ task_id: string; status: string }>(
    `/api/tasks/${taskId}/status`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'InProgress' }),
    },
    requestContext(),
  );
}

/** Reject a notification → task moves to Cancelled. */
export function rejectNotification(taskId: string) {
  return request<{ task_id: string; status: string }>(
    `/api/tasks/${taskId}/status`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Cancelled' }),
    },
    requestContext(),
  );
}
