import { useMemo, useState } from 'react';
import { Bell, Check, LoaderCircle, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { useSessionStore } from '@/stores/session-store';
import {
  acceptNotification,
  getGuestNotifications,
  getGuestResponded,
  rejectNotification,
  type GuestNotification,
} from './guest-api';
import { parseServerDate } from '@/lib/date-utils';

const notificationsKey = ['guest', 'notifications'] as const;
const respondedKey = ['guest', 'responded'] as const;

function formatDue(due: string | null) {
  if (!due) return null;
  const date = parseServerDate(due);
  if (!date) return null;
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

export function GuestDashboardWorkspace() {
  const queryClient = useQueryClient();
  const user = useSessionStore((state) => state.user);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const notificationsQuery = useQuery({ queryKey: notificationsKey, queryFn: getGuestNotifications });
  const respondedQuery = useQuery({ queryKey: respondedKey, queryFn: getGuestResponded });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: notificationsKey }),
      queryClient.invalidateQueries({ queryKey: respondedKey }),
    ]);
  }

  const acceptMutation = useMutation({
    mutationFn: acceptNotification,
    onSuccess: async () => {
      setSelectedId(null);
      await refresh();
    },
  });
  const rejectMutation = useMutation({
    mutationFn: rejectNotification,
    onSuccess: async () => {
      setSelectedId(null);
      await refresh();
    },
  });

  const notifications = notificationsQuery.data ?? [];
  const responded = useMemo(
    () => (respondedQuery.data ?? []).filter((task) => task.status === 'InProgress' || task.status === 'Cancelled'),
    [respondedQuery.data],
  );

  const selected = notifications.find((item) => item.task_id === selectedId) ?? null;
  const isResponding = acceptMutation.isPending || rejectMutation.isPending;

  const error = notificationsQuery.error ?? respondedQuery.error ?? acceptMutation.error ?? rejectMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not load your notifications. Please try again.' : null;

  return (
    <section className="space-y-6">
      <div className="border-b border-[var(--line)] pb-6">
        <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]"><Bell size={14} />Guest access</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Welcome{user?.name ? `, ${user.name}` : ''}</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 muted">You have guest access to this household. Requests shared with you appear below — open one to accept or decline.</p>
      </div>

      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}

      <div className="grid gap-5 lg:grid-cols-[1fr_0.8fr]">
        {/* Notifications */}
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Notifications" detail={`${notifications.length} awaiting your response`} action={<Bell size={18} className="text-[#5E9278]" />} />
          {notificationsQuery.isLoading ? (
            <div className="mt-6 flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading notifications</div>
          ) : notifications.length ? (
            <div className="mt-5 space-y-2">
              {notifications.map((item: GuestNotification) => (
                <button
                  key={item.task_id}
                  type="button"
                  onClick={() => setSelectedId(item.task_id)}
                  className={`flex w-full items-center gap-3 rounded-xl border p-4 text-left transition ${selectedId === item.task_id ? 'border-[#5E9278] bg-[#E4F0E8]' : 'border-[var(--line)] hover:border-[#5E9278]'}`}
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#F6EADB] text-[#8A5D2F]"><Bell size={16} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-[var(--ink)]">{item.title}</span>
                    <span className="block text-xs muted">{formatDue(item.due_at) ? `Due ${formatDue(item.due_at)}` : 'No due date'} · {item.priority} priority</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="mt-6 text-sm muted">No new notifications. You're all caught up.</p>
          )}
        </Card>

        {/* Detail / respond panel */}
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Details" detail="Review and respond" />
          {selected ? (
            <div className="mt-5 space-y-4">
              <div>
                <p className="text-base font-bold text-[var(--ink)]">{selected.title}</p>
                {selected.description && <p className="mt-2 text-sm leading-6 muted">{selected.description}</p>}
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-[var(--surface-muted)] p-3"><dt className="text-xs muted">Due</dt><dd className="mt-1 font-semibold text-[var(--ink)]">{formatDue(selected.due_at) ?? '—'}</dd></div>
                <div className="rounded-xl bg-[var(--surface-muted)] p-3"><dt className="text-xs muted">Priority</dt><dd className="mt-1 font-semibold text-[var(--ink)]">{selected.priority}</dd></div>
              </dl>
              <div className="flex gap-3">
                <Button onClick={() => acceptMutation.mutate(selected.task_id)} disabled={isResponding} className="flex-1"><Check size={16} />Accept</Button>
                <Button tone="neutral" onClick={() => rejectMutation.mutate(selected.task_id)} disabled={isResponding} className="flex-1"><X size={16} />Reject</Button>
              </div>
              {isResponding && <p className="flex items-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={14} />Saving your response…</p>}
            </div>
          ) : (
            <p className="mt-6 text-sm muted">Select a notification to view its details and respond.</p>
          )}

          {responded.length > 0 && (
            <div className="mt-6 border-t border-[var(--line)] pt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] muted">Your recent responses</p>
              <div className="mt-3 space-y-2">
                {responded.slice(0, 5).map((task) => (
                  <div key={task.task_id} className="flex items-center gap-2 text-sm">
                    {task.status === 'InProgress'
                      ? <Check size={14} className="shrink-0 text-[#3D5F4E]" />
                      : <X size={14} className="shrink-0 text-[#8B3F36]" />}
                    <span className="truncate text-[var(--ink)]">{task.title}</span>
                    <span className="ml-auto shrink-0 text-xs muted">{task.status === 'InProgress' ? 'Accepted' : 'Rejected'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </section>
  );
}
