import { useMemo, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CalendarDays, ClipboardList, Package, ReceiptIndianRupee, ShoppingBasket, WalletCards, Wrench } from 'lucide-react';
import { HouseholdChat } from '@/components/ai/household-chat';
import { Card } from '@/components/design-system/card';
import { getCalendarEvents } from '@/features/calendar-schedule/calendar-api';
import type { CalendarEvent } from '@/features/calendar-schedule/calendar-types';
import { getBudgetStatus, getBudgets, getUpcomingBills, type Budget, type BudgetStatus } from '@/features/finance/finance-api';
import { getGroceries, getLowStock } from '@/features/food-inventory/inventory-api';
import { getIssues } from '@/features/maintenance/maintenance-api';
import { getTasks } from '@/features/tasks-schedule/task-api';
import type { HouseholdTask } from '@/features/tasks-schedule/task-types';
import { useSessionStore } from '@/stores/session-store';
import { MetricCard } from './metric-card';
import { parseServerDate, formatLocalDateTime } from '@/lib/date-utils';

const taskQueryKey = ['household', 'tasks'] as const;
const calendarQueryKey = ['household', 'calendar'] as const;
const lowStockQueryKey = ['household', 'inventory', 'low-stock'] as const;
const groceryQueryKey = ['household', 'inventory', 'groceries'] as const;
const budgetQueryKey = ['household', 'finance', 'budgets'] as const;
const upcomingBillsQueryKey = ['household', 'finance', 'upcoming-bills'] as const;
const maintenanceIssuesQueryKey = ['household', 'maintenance', 'issues'] as const;

export function OverviewDashboard() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const queryClient = useQueryClient();
  const role = useSessionStore((state) => state.user?.role);
  const canUseFinance = role === 'Admin' || role === 'Adult';
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();
  const periodPrefix = `${year}-${String(month).padStart(2, '0')}`;
  const tasksQuery = useQuery({ queryKey: taskQueryKey, queryFn: () => getTasks() });
  const eventsQuery = useQuery({ queryKey: calendarQueryKey, queryFn: getCalendarEvents });
  const lowStockQuery = useQuery({ queryKey: lowStockQueryKey, queryFn: getLowStock });
  const groceriesQuery = useQuery({ queryKey: groceryQueryKey, queryFn: () => getGroceries(false) });
  const billsQuery = useQuery({ queryKey: [...upcomingBillsQueryKey, 7], queryFn: () => getUpcomingBills(7), enabled: canUseFinance });
  const budgetsQuery = useQuery({ queryKey: budgetQueryKey, queryFn: getBudgets, enabled: canUseFinance });
  const issuesQuery = useQuery({ queryKey: maintenanceIssuesQueryKey, queryFn: () => getIssues() });
  const activeTasks = useMemo(() => (tasksQuery.data ?? []).filter((task) => task.status !== 'Done' && task.status !== 'Cancelled'), [tasksQuery.data]);
  const upcomingEvents = useMemo(() => getUpcomingEvents(eventsQuery.data ?? []), [eventsQuery.data]);
  const openIssues = useMemo(() => (issuesQuery.data ?? []).filter((issue) => issue.status !== 'Resolved' && issue.status !== 'Closed'), [issuesQuery.data]);
  const currentBudgets = useMemo(() => (budgetsQuery.data ?? []).filter((budget) => budget.period_start?.startsWith(periodPrefix)), [budgetsQuery.data, periodPrefix]);
  const statusQueries = useQueries({ queries: currentBudgets.map((budget) => ({ queryKey: [...budgetQueryKey, 'status', budget.budget_id, year, month], queryFn: () => getBudgetStatus(budget.category, month, year), enabled: canUseFinance })) });
  const budgetStatuses = useMemo(() => new Map(currentBudgets.map((budget, index) => [budget.budget_id, statusQueries[index]?.data])), [currentBudgets, statusQueries]);
  const attentionItems = [
    ...(lowStockQuery.data ?? []).map((item) => ({ id: `stock-${item.item_id}`, title: `${item.name} is low`, detail: formatQuantity(item.quantity, item.unit), to: workspacePath(tenantId, 'inventory'), icon: <Package size={15} />, tone: 'orange' as const })),
    ...(canUseFinance ? (billsQuery.data ?? []).map((bill) => ({ id: `bill-${bill.bill_id}`, title: `${bill.payee} payment due`, detail: bill.days_remaining === 0 ? 'Due today' : `${bill.days_remaining} day${bill.days_remaining === 1 ? '' : 's'} remaining`, to: workspacePath(tenantId, 'finance'), icon: <ReceiptIndianRupee size={15} />, tone: 'blue' as const })) : []),
    ...openIssues.map((issue) => ({ id: `issue-${issue.issue_id}`, title: issue.description, detail: `${issue.priority} priority maintenance issue`, to: workspacePath(tenantId, 'maintenance'), icon: <Wrench size={15} />, tone: 'red' as const })),
  ].slice(0, 4);
  const hasPartialError = [tasksQuery, eventsQuery, lowStockQuery, groceriesQuery, issuesQuery, ...(canUseFinance ? [billsQuery, budgetsQuery, ...statusQueries] : [])].some((query) => query.isError);
  const budgetLoading = budgetsQuery.isLoading || statusQueries.some((query) => query.isLoading);
  const reviewPath = attentionItems[0]?.to ?? workspacePath(tenantId, 'plan');

  return <div className="space-y-5">
    <HouseholdChat compact title="Ask HomeOps" description="Ask about tasks, schedules, shopping, or household decisions." initialMessage="What would you like to organize?" suggestions={['What needs attention today?', 'Plan this weekend', 'What is running low?']} showAttachments={false} showVoice={false} onMessageProcessed={() => queryClient.invalidateQueries({ queryKey: ['household'] })} />
    {hasPartialError && <p role="status" className="rounded-xl border border-[#D19A4C]/35 bg-[#F6EADB] px-4 py-3 text-sm text-[#8A5D2F]">Some dashboard information could not be loaded. Available household workspaces still work normally.</p>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard icon={<ClipboardList />} value={metricValue(tasksQuery.isLoading, activeTasks.length)} label="Open tasks" tone="green" />
      <MetricCard icon={<CalendarDays />} value={metricValue(eventsQuery.isLoading, upcomingEvents.length)} label="Upcoming events" tone="blue" />
      <MetricCard icon={<AlertTriangle />} value={metricValue(lowStockQuery.isLoading, lowStockQuery.data?.length ?? 0)} label="Low stock" tone="orange" />
      <MetricCard icon={<ShoppingBasket />} value={metricValue(groceriesQuery.isLoading, groceriesQuery.data?.length ?? 0)} label="To buy" tone="green" />
    </div>
    <div className={`grid gap-4 ${currentBudgets.length ? 'xl:grid-cols-[1.15fr_0.85fr_0.85fr]' : 'xl:grid-cols-[1.15fr_0.85fr]'}`}>
      <DashboardCard title="Today’s plan" actionLabel="Open plan" to={workspacePath(tenantId, 'plan')}>{tasksQuery.isLoading || eventsQuery.isLoading ? <LoadingRows label="Loading today’s plan" /> : <TodayPlan tasks={activeTasks} events={upcomingEvents} />}</DashboardCard>
      <DashboardCard title="Needs attention" actionLabel="Review" to={reviewPath}>{lowStockQuery.isLoading || issuesQuery.isLoading || (canUseFinance && billsQuery.isLoading) ? <LoadingRows label="Checking household alerts" /> : attentionItems.length ? <div className="space-y-2">{attentionItems.map((item) => <AttentionItem key={item.id} {...item} />)}</div> : <EmptyState message="Nothing urgent right now." />}</DashboardCard>
      {currentBudgets.length > 0 && <BudgetSummary budgets={currentBudgets} statuses={budgetStatuses} loading={budgetLoading} to={workspacePath(tenantId, 'finance')} />}
    </div>
    <div className="grid gap-4 xl:grid-cols-2">
      <DashboardCard title="Task inbox" actionLabel="View all" to={workspacePath(tenantId, 'plan')}>{tasksQuery.isLoading ? <LoadingRows label="Loading tasks" /> : activeTasks.length ? <div className="space-y-2">{activeTasks.slice(0, 4).map((task) => <TaskItem key={task.task_id} task={task} />)}</div> : <EmptyState message="No active tasks. Add one when something needs an owner." />}</DashboardCard>
      <DashboardCard title="Shopping list" actionLabel="Open list" to={workspacePath(tenantId, 'grocery')}>{groceriesQuery.isLoading ? <LoadingRows label="Loading grocery list" /> : groceriesQuery.data?.length ? <div className="space-y-2">{groceriesQuery.data.slice(0, 4).map((item) => <div key={item.grocery_item_id} className="flex items-center gap-3 rounded-lg bg-[var(--surface-muted)] px-3 py-2.5"><ShoppingBasket size={15} className="shrink-0 text-[#5E9278]" /><div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{item.name}</p><p className="mt-0.5 text-xs muted">{formatOptionalQuantity(item.quantity, item.unit)}</p></div></div>)}</div> : <EmptyState message="The grocery list is empty." />}</DashboardCard>
    </div>
  </div>;
}

function DashboardCard({ title, actionLabel, to, children }: { title: string; actionLabel: string; to: string; children: ReactNode }) { return <Card className="p-4"><div className="flex items-center justify-between gap-3"><h2 className="font-display text-base font-semibold text-[var(--ink)]">{title}</h2><Link to={to} className="shrink-0 text-xs font-semibold text-[#3D7C63] hover:text-[#284837] hover:underline">{actionLabel}</Link></div><div className="mt-3">{children}</div></Card>; }
function TodayPlan({ tasks, events }: { tasks: HouseholdTask[]; events: CalendarEvent[] }) { const entries = [...events.slice(0, 3).map((event) => ({ id: `event-${event.event_id}`, title: event.title, detail: formatDateTime(event.starts_at), icon: <CalendarDays size={15} className="text-[#3D5F4E]" /> })), ...tasks.slice(0, 3).map((task) => ({ id: `task-${task.task_id}`, title: task.title, detail: task.due_at ? `Due ${formatDateTime(task.due_at)}` : 'No deadline set', icon: <ClipboardList size={15} className="text-[#5E9278]" /> }))].slice(0, 5); return entries.length ? <div className="space-y-2">{entries.map((entry) => <div key={entry.id} className="flex items-center gap-3 rounded-lg border border-[var(--line)] px-3 py-2.5"><span className="grid size-7 shrink-0 place-items-center rounded-lg bg-[#E4F0E8]">{entry.icon}</span><div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{entry.title}</p><p className="mt-0.5 text-xs muted">{entry.detail}</p></div></div>)}</div> : <EmptyState message="Nothing is scheduled yet. Add a task or event to begin." />; }
function BudgetSummary({ budgets, statuses, loading, to }: { budgets: Budget[]; statuses: Map<string, BudgetStatus | undefined>; loading: boolean; to: string }) { return <Card className="p-4"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><WalletCards size={17} className="text-[#346B8E]" /><h2 className="font-display text-base font-semibold text-[var(--ink)]">Budgets</h2></div><Link to={to} className="text-xs font-semibold text-[#3D7C63] hover:underline">Open finance</Link></div>{loading ? <LoadingRows label="Loading budget status" /> : <div className="mt-3 space-y-3">{budgets.slice(0, 3).map((budget) => <BudgetRow key={budget.budget_id} budget={budget} status={statuses.get(budget.budget_id)} />)}</div>}</Card>; }
function BudgetRow({ budget, status }: { budget: Budget; status?: BudgetStatus }) { const spent = status?.spent_minor ?? 0; const progress = Math.min(100, Math.round((spent / Math.max(budget.limit_minor, 1)) * 100)); const exceeded = Boolean(status?.is_exceeded); return <div><div className="flex items-center justify-between gap-2 text-xs"><span className="truncate font-semibold text-[var(--ink)]">{budget.category}</span><span className={exceeded ? 'font-semibold text-[#B96359]' : 'muted'}>{money(status?.remaining_minor ?? budget.limit_minor, budget.currency)} {exceeded ? 'over' : 'left'}</span></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#DCE3DE]"><div className={exceeded ? 'h-full bg-[#B96359]' : 'h-full bg-[#5E9278]'} style={{ width: `${progress}%` }} /></div></div>; }
function AttentionItem({ title, detail, to, icon, tone }: { title: string; detail: string; to: string; icon: ReactNode; tone: 'orange' | 'blue' | 'red' }) { const colors = { orange: 'bg-[#F6EADB] text-[#8A5D2F]', blue: 'bg-[#E0ECF4] text-[#346B8E]', red: 'bg-[#F9E5E2] text-[#A74C42]' }; return <Link to={to} className="flex items-center gap-3 rounded-lg border border-[var(--line)] px-3 py-2.5 transition hover:bg-[var(--surface-muted)]"><span className={`grid size-7 shrink-0 place-items-center rounded-lg ${colors[tone]}`}>{icon}</span><div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--ink)]">{title}</p><p className="mt-0.5 text-xs muted">{detail}</p></div></Link>; }
function TaskItem({ task }: { task: HouseholdTask }) { const status = task.status === 'InProgress' ? 'In progress' : task.status; return <div className="flex items-center gap-3 rounded-lg border border-[var(--line)] px-3 py-2.5"><ClipboardList size={16} className="shrink-0 text-[#5E9278]" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[var(--ink)]">{task.title}</p><p className="mt-0.5 text-xs muted">{task.due_at ? `Due ${formatDateTime(task.due_at)}` : 'No deadline set'}</p></div><span className="rounded-full bg-[#ECEAE4] px-2 py-1 text-[11px] font-semibold text-[#676B68]">{status}</span></div>; }
function LoadingRows({ label }: { label: string }) { return <div className="space-y-2" aria-label={label}><div className="h-12 animate-pulse rounded-lg bg-[var(--surface-muted)]" /><div className="h-12 animate-pulse rounded-lg bg-[var(--surface-muted)]" /></div>; }
function EmptyState({ message }: { message: string }) { return <p className="rounded-lg bg-[var(--surface-muted)] p-3 text-sm leading-5 muted">{message}</p>; }
function metricValue(isLoading: boolean, value: number) { return isLoading ? '…' : String(value); }
function workspacePath(tenantId: string | undefined, workspace: string) { return `/t/${encodeURIComponent(tenantId ?? 'home-lakeview')}/${workspace}`; }
function getUpcomingEvents(events: CalendarEvent[]) {
  const now = Date.now();
  return [...events]
    .filter((event) => {
      const parsed = parseServerDate(event.starts_at);
      return parsed !== null && parsed.getTime() >= now;
    })
    .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
}
function formatDateTime(value: string) {
  const date = parseServerDate(value);
  if (!date) return 'Date unavailable';
  return formatLocalDateTime(value);
}
function formatQuantity(quantity: number, unit: string | null) { return `${quantity}${unit ? ` ${unit}` : ''} remaining`; }
function formatOptionalQuantity(quantity: number | null, unit: string | null) { if (quantity === null) return unit ?? 'Quantity not specified'; return `${quantity}${unit ? ` ${unit}` : ''}`; }
function money(amountMinor: number, currency: string) { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(amountMinor / 100); }
