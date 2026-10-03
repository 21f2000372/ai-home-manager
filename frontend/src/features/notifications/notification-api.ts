import { request } from '@/lib/api/request';

export type InAppNotification = {
  notification_id: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function getNotifications() {
  return request<InAppNotification[]>('/api/notifications', {}, requestContext());
}

export function markNotificationAsRead(id: string) {
  return request<{ message: string; notification_id: string }>(
    `/api/notifications/${id}/read`,
    { method: 'PATCH' },
    requestContext()
  );
}

export function markAllNotificationsAsRead() {
  return request<{ message: string; count: number }>(
    '/api/notifications/read-all',
    { method: 'PATCH' },
    requestContext()
  );
}