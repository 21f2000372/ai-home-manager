import { create } from 'zustand';

export type Notification = { id: string; title: string; message?: string; tone: 'info' | 'success' | 'warning' | 'error' };
type NotificationState = { notifications: Notification[]; push: (notification: Notification) => void; dismiss: (id: string) => void; clear: () => void };

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  push: (notification) => set((state) => ({ notifications: [...state.notifications, notification] })),
  dismiss: (id) => set((state) => ({ notifications: state.notifications.filter((notification) => notification.id !== id) })),
  clear: () => set({ notifications: [] }),
}));