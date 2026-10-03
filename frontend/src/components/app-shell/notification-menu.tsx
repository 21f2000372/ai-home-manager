import { useEffect, useRef, useState } from 'react';
import { Bell, Check, CheckCheck, LoaderCircle } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  type InAppNotification,
} from '@/features/notifications/notification-api';

const notificationsKey = ['user', 'notifications'] as const;

function formatNotificationTime(isoString: string) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export function NotificationMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: notifications = [], isLoading } = useQuery({
    queryKey: notificationsKey,
    queryFn: getNotifications,
    refetchInterval: 30000,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => markNotificationAsRead(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationsKey });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: markAllNotificationsAsRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationsKey });
    },
  });

  // Close dropdown on clicks outside or pressing Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false);
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const unreadCount = notifications.filter((item) => !item.read).length;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        className="relative rounded-xl p-2 text-[var(--muted)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]"
        aria-label="Notifications"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <Bell size={19} />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#B96359] px-1 text-[10px] font-bold text-white shadow-sm">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 sm:w-96 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-xl">
          <div className="flex items-center justify-between border-b border-[var(--line)] pb-3">
            <div className="flex items-center gap-2">
              <h3 className="font-display text-sm font-semibold text-[var(--ink)]">Notifications</h3>
              {unreadCount > 0 && (
                <span className="rounded-full bg-[#E4F0E8] px-2 py-0.5 text-xs font-semibold text-[#3D5F4E]">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                disabled={markAllReadMutation.isPending}
                onClick={() => markAllReadMutation.mutate()}
                className="inline-flex items-center gap-1 text-xs font-semibold text-[#5E9278] hover:text-[#4D7A64] hover:underline disabled:opacity-50"
              >
                <CheckCheck size={14} />
                Mark all read
              </button>
            )}
          </div>

          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="flex min-h-24 items-center justify-center gap-2 text-xs muted">
                <LoaderCircle className="animate-spin" size={16} />
                Loading notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-xs font-semibold text-[var(--ink)]">All caught up</p>
                <p className="mt-1 text-xs muted">No notifications for your account.</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.notification_id}
                  onClick={() => {
                    if (!n.read) markReadMutation.mutate(n.notification_id);
                  }}
                  className={`group relative flex cursor-pointer items-start justify-between gap-3 rounded-xl border p-3 text-xs transition ${
                    n.read
                      ? 'border-transparent bg-[var(--surface-muted)] text-[var(--muted)]'
                      : 'border-[#5E9278]/30 bg-[#E4F0E8]/50 text-[var(--ink)] shadow-sm'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {!n.read && <span className="size-1.5 rounded-full bg-[#5E9278]" />}
                      <p className={`font-semibold ${n.read ? 'text-[var(--ink)]' : 'text-[#284837]'}`}>
                        {n.title}
                      </p>
                    </div>
                    <p className="mt-1 leading-relaxed">{n.message}</p>
                    <p className="mt-1.5 text-[10px] muted">{formatNotificationTime(n.created_at)}</p>
                  </div>

                  {!n.read && (
                    <button
                      type="button"
                      title="Mark as read"
                      aria-label="Mark as read"
                      onClick={(e) => {
                        e.stopPropagation();
                        markReadMutation.mutate(n.notification_id);
                      }}
                      className="rounded-lg p-1 text-[var(--muted)] hover:bg-white hover:text-[#5E9278]"
                    >
                      <Check size={14} />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}