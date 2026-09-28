import { useMemo, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CalendarDays, CheckCircle2, ClipboardList, Package, ReceiptIndianRupee, ShoppingBasket, Wrench } from 'lucide-react';
import { HouseholdChat } from '@/components/ai/household-chat';
import { Card } from '@/components/design-system/card';
import { getCalendarEvents } from '@/features/calendar-schedule/calendar-api';
import type { CalendarEvent } from '@/features/calendar-schedule/calendar-types';
import { getUpcomingBills } from '@/features/finance/finance-api';
import { getGroceries, getLowStock } from '@/features/food-inventory/inventory-api';
import { getIssues } from '@/features/maintenance/maintenance-api';
import { getTasks } from '@/features/tasks-schedule/task-api';
import type { HouseholdTask } from '@/features/tasks-schedule/task-types';
import { MetricCard } from './metric-card';

const taskQueryKey = ['household', 'tasks'] as const;
const calendarQueryKey = ['household', 'calendar'] as const;
const lowStockQueryKey = ['household', 'inventory', 'low-stock'] as const;
const groceryQueryKey = ['household', 'inventory', 'groceries'] as const;
const upcomingBillsQueryKey = ['household', 'finance', 'upcoming-bills'] as const;
const maintenanceIssuesQueryKey = ['household', 'maintenance', 'issues'] as const;

export function OverviewDashboard() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const queryClient = useQueryClient();
  const tasksQuery = useQuery({ queryKey: taskQueryKey, queryFn: () => getTasks() });
  const eventsQuery = useQuery({ queryKey: calendarQueryKey, queryFn: getCalendarEvents });
  const lowStockQuery = useQuery({ queryKey: lowStockQueryKey, queryFn: getLowStock });
  const groceriesQuery = useQuery({ queryKey: groceryQueryKey, queryFn: () => getGroceries(false) });
  const billsQuery = useQuery({ queryKey: upcomingBillsQueryKey, queryFn: () => getUpcomingBills(7) });
  const issuesQuery = useQuery({ queryKey: maintenanceIssuesQueryKey, queryFn: () => getIssues() });

  const activeTasks = useMemo(
    () => (tasksQuery.data ?? []).filter((task) => task.status !== 'Done' && task.status !== 'Cancelled'),
    [tasksQuery.data],
  );
  const upcomingEvents = useMemo(() => getUpcomingEvents(eventsQuery.data ?? []), [eventsQuery.data]);
  const openIssues = useMemo(
    () => (issuesQuery.data ?? []).filter((issue) => issue.status !== 'Resolved' && issue.status !== 'Closed'),
    [issuesQuery.data],
  );

  const attentionItems = [
    ...(lowStockQuery.data ?? []).map((item) => ({
      id: `stock-${item.item_id}`,
      title: `${item.name} is low`,
      detail: formatQuantity(item.quantity, item.unit),
      to: workspacePath(tenantId, 'inventory'),
      icon: <Package size={16} />,
      tone: 'orange' as const,
    })),
    ...(billsQuery.data ?? []).map((bill) => ({
      id: `bill-${bill.bill_id}`,
      title: `${bill.payee} payment due`,
      detail: bill.days_remaining === 0 ? 'Due today' : `${bill.days_remaining} day${bill.days_remaining === 1 ? '' : 's'} remaining`,
      to: workspacePath(tenantId, 'finance'),
      icon: <ReceiptIndianRupee size={16} />,
      tone: 'blue' as const,
    })),
    ...openIssues.map((issue) => ({
      id: `issue-${issue.issue_id}`,
      title: issue.description,
      detail: `${issue.priority} priority maintenance issue`,
      to: workspacePath(tenantId, 'maintenance'),
      icon: <Wrench size={16} />,
      tone: 'red' as const,
    })),
  ].slice(0, 5);

  const hasPartialError = [tasksQuery, eventsQuery, lowStockQuery, groceriesQuery, billsQuery, issuesQuery].some((query) => query.isError);

  return (
    <div className="space-y-6">
      {hasPartialError && (
        <p role="status" className="rounded-xl border border-[#D19A4C]/35 bg-[#F6EADB] px-4 py-3 text-sm text-[#8A5D2F]">
          Some dashboard information could not be loaded. You can still use the available household workspaces.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={<ClipboardList />} value={metricValue(tasksQuery.isLoading, activeTasks.length)} label="Tasks to do" tone="green" />
        <MetricCard icon={<CalendarDays />} value={metricValue(eventsQuery.isLoading, upcomingEvents.length)} label="Upcoming events" tone="blue" />
        <MetricCard icon={<AlertTriangle />} value={metricValue(lowStockQuery.isLoading, lowStockQuery.data?.length ?? 0)} label="Low-stock items" tone="orange" />
        <MetricCard icon={<ShoppingBasket />} value={metricValue(groceriesQuery.isLoading, groceriesQuery.data?.length ?? 0)} label="Items to buy" tone="green" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <DashboardCard title="Next on the household calendar" actionLabel="View calendar" to={workspacePath(tenantId, 'calendar')}>
          {eventsQuery.isLoading ? <LoadingRows label="Loading upcoming events" /> : upcomingEvents.length ? (
            <div className="space-y-3">
              {upcomingEvents.slice(0, 4).map((event) => <TimelineItem key={event.event_id} event={event} />)}
            </div>
          ) : <EmptyState message="No upcoming events. Add the next household plan to the shared calendar." />}
        </DashboardCard>

        <DashboardCard title="Needs attention" actionLabel="Review inventory" to={workspacePath(tenantId, 'inventory')}>
          {lowStockQuery.isLoading || billsQuery.isLoading || issuesQuery.isLoading ? <LoadingRows label="Checking household alerts" /> : attentionItems.length ? (
            <div className="space-y-3">
              {attentionItems.map((item) => <AttentionItem key={item.id} {...item} />)}
            </div>
          ) : <EmptyState message="Nothing urgent right now. Your household is in good shape." />}
        </DashboardCard>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <DashboardCard title="Active household tasks" actionLabel="View tasks" to={workspacePath(tenantId, 'tasks')}>
          {tasksQuery.isLoading ? <LoadingRows label="Loading tasks" /> : activeTasks.length ? (
            <div className="space-y-3">
              {activeTasks.slice(0, 4).map((task) => <TaskItem key={task.task_id} task={task} />)}
            </div>
          ) : <EmptyState message="No active tasks. Add one when something needs an owner." />}
        </DashboardCard>

        <DashboardCard title="Shopping list" actionLabel="Open grocery list" to={workspacePath(tenantId, 'grocery')}>
          {groceriesQuery.isLoading ? <LoadingRows label="Loading grocery list" /> : groceriesQuery.data?.length ? (
            <div className="space-y-3">
              {groceriesQuery.data.slice(0, 4).map((item) => (
                <div key={item.grocery_item_id} className="flex items-center gap-3 rounded-xl bg-[var(--surface-muted)] px-4 py-3">
                  <ShoppingBasket size={16} className="shrink-0 text-[#5E9278]" />
                  <div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{item.name}</p><p className="mt-0.5 text-xs muted">{formatOptionalQuantity(item.quantity, item.unit)}</p></div>
                </div>
              ))}
            </div>
          ) : <EmptyState message="The grocery list is empty. Add an item when the household needs something." />}
        </DashboardCard>
      </div>

      <HouseholdChat
        title="Ask the household assistant"
        description="Use plain language to create a task, plan an event, or coordinate household work from one place."
        initialMessage="Tell me what you need to organize, and I will help turn it into a household action."
        onMessageProcessed={() => queryClient.invalidateQueries({ queryKey: ['household'] })}
      />
    </div>
  );
}

function DashboardCard({ title, actionLabel, to, children }: { title: string; actionLabel: string; to: string; children: ReactNode }) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3"><h2 className="font-display text-lg font-semibold text-[var(--ink)]">{title}</h2><Link to={to} className="shrink-0 text-xs font-semibold text-[#3D7C63] hover:text-[#284837] hover:underline">{actionLabel}</Link></div>
      <div className="mt-5">{children}</div>
    </Card>
  );
}

function TimelineItem({ event }: { event: CalendarEvent }) {
  return <div className="flex gap-3 rounded-xl border border-[var(--line)] p-4"><div className="grid size-9 shrink-0 place-items-center rounded-lg bg-[#E4F0E8] text-[#3D5F4E]"><CalendarDays size={17} /></div><div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{event.title}</p><p className="mt-1 text-xs muted">{formatDateTime(event.starts_at)}</p></div></div>;
}

function AttentionItem({ title, detail, to, icon, tone }: { title: string; detail: string; to: string; icon: ReactNode; tone: 'orange' | 'blue' | 'red' }) {
  const colors = { orange: 'bg-[#F6EADB] text-[#8A5D2F]', blue: 'bg-[#E0ECF4] text-[#346B8E]', red: 'bg-[#F9E5E2] text-[#A74C42]' };
  return <Link to={to} className="flex items-start gap-3 rounded-xl border border-[var(--line)] p-4 transition hover:bg-[var(--surface-muted)]"><span className={`grid size-8 shrink-0 place-items-center rounded-lg ${colors[tone]}`}>{icon}</span><div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{title}</p><p className="mt-1 text-xs muted">{detail}</p></div></Link>;
}

function TaskItem({ task }: { task: HouseholdTask }) {
  const status = task.status === 'InProgress' ? 'In progress' : task.status;
  return <div className="flex items-start gap-3 rounded-xl border border-[var(--line)] p-4"><CheckCircle2 size={18} className="mt-0.5 shrink-0 text-[#5E9278]" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[var(--ink)]">{task.title}</p><p className="mt-1 text-xs muted">{task.due_at ? `Due ${formatDateTime(task.due_at)}` : 'No due date'}{task.assigned_to ? ` • Assigned to ${task.assigned_to}` : ''}</p></div><span className="rounded-full bg-[#ECEAE4] px-2 py-1 text-xs font-semibold text-[#676B68]">{status}</span></div>;
}

function LoadingRows({ label }: { label: string }) {
  return <div className="space-y-3" aria-label={label}><div className="h-16 animate-pulse rounded-xl bg-[var(--surface-muted)]" /><div className="h-16 animate-pulse rounded-xl bg-[var(--surface-muted)]" /><div className="h-16 animate-pulse rounded-xl bg-[var(--surface-muted)]" /></div>;
}

function EmptyState({ message }: { message: string }) {
  return <p className="rounded-xl bg-[var(--surface-muted)] p-4 text-sm leading-6 muted">{message}</p>;
}

function metricValue(isLoading: boolean, value: number) {
  return isLoading ? '…' : String(value);
}

function workspacePath(tenantId: string | undefined, workspace: string) {
  return `/t/${encodeURIComponent(tenantId ?? 'home-lakeview')}/${workspace}`;
}

function getUpcomingEvents(events: CalendarEvent[]) {
  const now = Date.now();
  return [...events]
    .filter((event) => !Number.isNaN(new Date(event.starts_at).getTime()) && new Date(event.starts_at).getTime() >= now)
    .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date);
}

function formatQuantity(quantity: number, unit: string | null) {
  return `${quantity}${unit ? ` ${unit}` : ''} remaining`;
}

function formatOptionalQuantity(quantity: number | null, unit: string | null) {
  if (quantity === null) return unit ?? 'Quantity not specified';
  return `${quantity}${unit ? ` ${unit}` : ''}`;
}
