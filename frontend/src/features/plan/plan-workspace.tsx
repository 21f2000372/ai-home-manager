import { FormEvent, useMemo, useState } from 'react';
import { CalendarDays, Check, ChevronDown, CircleDot, Clock3, LoaderCircle, Pencil, Plus, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { useSessionStore } from '@/stores/session-store';
import { createCalendarEvent, getCalendarEvents } from '@/features/calendar-schedule/calendar-api';
import type { CalendarEvent, CreateCalendarEventInput } from '@/features/calendar-schedule/calendar-types';
import { createTask, getHouseholdMembers, getTasks, updateTask, updateTaskStatus, type CreateTaskInput, type HouseholdMember, type HouseholdTask } from '@/features/tasks-schedule/task-api';
import { getNextTaskStatus, toDateTimeLocalValue } from '@/features/tasks-schedule/task-utils';

const taskQueryRoot = ['household', 'tasks'] as const;
const calendarQueryKey = ['household', 'calendar'] as const;

type ComposerKind = 'task' | 'event' | null;
type Scope = 'household' | 'mine';

const taskQueryKey = (scope: Scope) => [...taskQueryRoot, scope] as const;

const emptyTask: CreateTaskInput = { title: '', description: '', assigned_to: '', due_at: '', priority: 'Normal' };
const emptyEvent: CreateCalendarEventInput = { title: '', starts_at: '', ends_at: '' };

export function PlanWorkspace() {
  const queryClient = useQueryClient();
  const user = useSessionStore((state) => state.user);
  const [range, setRange] = useState<'today' | 'week'>('week');
  const [scope, setScope] = useState<Scope>(user?.role === 'Child' ? 'mine' : 'household');
  const [composer, setComposer] = useState<ComposerKind>(null);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [taskForm, setTaskForm] = useState<CreateTaskInput>(emptyTask);
  const [eventForm, setEventForm] = useState<CreateCalendarEventInput>(emptyEvent);
  const [conflicts, setConflicts] = useState<string[]>([]);

  const tasksQuery = useQuery({
    queryKey: taskQueryKey(scope),
    queryFn: () => getTasks(scope === 'mine' ? { assigned_to: 'me' } : {}),
  });
  const eventsQuery = useQuery({ queryKey: calendarQueryKey, queryFn: getCalendarEvents });
  const membersQuery = useQuery({ queryKey: ['household', 'members'] as const, queryFn: getHouseholdMembers });
  const isReadOnly = user?.role === 'Guest';

  const refreshPlan = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: taskQueryRoot }),
      queryClient.invalidateQueries({ queryKey: calendarQueryKey }),
    ]);
  };

  const createTaskMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async () => {
      await refreshPlan();
      setTaskForm(emptyTask);
      setComposer(null);
    },
  });
  const createEventMutation = useMutation({
    mutationFn: createCalendarEvent,
    onSuccess: async (result) => {
      setConflicts([...result.conflicts.calendar_conflicts, ...result.conflicts.task_conflicts].map((conflict) => conflict.title));
      await refreshPlan();
      setEventForm(emptyEvent);
      setComposer(null);
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: HouseholdTask['status'] }) => updateTaskStatus(taskId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: taskQueryRoot }),
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, input }: { taskId: string; input: CreateTaskInput }) => updateTask(taskId, input),
    onSuccess: async () => {
      await refreshPlan();
      closeTaskComposer();
    },
  });

  const days = useMemo(() => buildDays(range), [range]);
  const memberNames = useMemo(() => new Map((membersQuery.data ?? []).map((member) => [member.user_id, member.name])), [membersQuery.data]);
  const visibleTasks = tasksQuery.data ?? [];
  const visibleEvents = eventsQuery.data ?? [];
  const datedTasks = useMemo(() => {
    const firstDay = days[0].key;
    const lastDay = days[days.length - 1].key;
    return visibleTasks.filter((task) => task.due_at && dayKey(new Date(task.due_at)) >= firstDay && dayKey(new Date(task.due_at)) <= lastDay);
  }, [days, visibleTasks]);
  const inboxTasks = useMemo(() => visibleTasks.filter((task) => !task.due_at || !isInDays(task.due_at, days)).sort(taskSort), [days, visibleTasks]);

  function openComposer(kind: Exclude<ComposerKind, null>) {
    setConflicts([]);
    if (kind === 'task') {
      setTaskForm(emptyTask);
      setEditingTaskId(null);
    }
    setComposer(kind);
  }

  function closeTaskComposer() {
    setTaskForm(emptyTask);
    setEditingTaskId(null);
    setComposer(null);
  }

  function beginTaskEdit(task: HouseholdTask) {
    const assignee = (membersQuery.data ?? []).find((member) => member.user_id === task.assigned_to || member.name === task.assigned_to);
    setTaskForm({
      title: task.title,
      description: task.description ?? '',
      assigned_to: assignee?.user_id ?? '',
      due_at: toDateTimeLocalValue(task.due_at),
      priority: task.priority,
    });
    setEditingTaskId(task.task_id);
    setConflicts([]);
    setComposer('task');
  }

  function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!taskForm.title.trim() || isReadOnly) return;
    const input = {
      ...taskForm,
      title: taskForm.title.trim(),
      description: taskForm.description?.trim() || undefined,
      assigned_to: taskForm.assigned_to || undefined,
      due_at: taskForm.due_at ? new Date(taskForm.due_at).toISOString() : undefined,
    };
    if (editingTaskId) {
      updateTaskMutation.mutate({ taskId: editingTaskId, input });
    } else {
      createTaskMutation.mutate(input);
    }
  }

  function submitEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!eventForm.title.trim() || !eventForm.starts_at || !eventForm.ends_at || isReadOnly) return;
    const startsAt = new Date(eventForm.starts_at);
    const endsAt = new Date(eventForm.ends_at);
    if (Number.isNaN(startsAt.getTime()) || Number.isNaN(endsAt.getTime()) || endsAt <= startsAt) return;
    setConflicts([]);
    createEventMutation.mutate({
      title: eventForm.title.trim(),
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
    });
  }

  const error = tasksQuery.error ?? eventsQuery.error ?? membersQuery.error ?? createTaskMutation.error ?? updateTaskMutation.error ?? createEventMutation.error ?? statusMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not update the household plan. Please try again.' : null;
  const loading = tasksQuery.isLoading || eventsQuery.isLoading;

  return <section className="space-y-6">
    <header className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 xl:flex-row xl:items-end">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Tasks & schedule</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Household plan</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 muted">One calm view for commitments, task deadlines, and the work that still needs a home on the schedule.</p>
      </div>
      {!isReadOnly && <div className="flex flex-wrap gap-2"><Button tone="neutral" onClick={() => openComposer('task')}><Plus size={16} />Add task</Button><Button onClick={() => openComposer('event')}><CalendarDays size={16} />Add event</Button></div>}
    </header>

    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <div className="inline-flex w-fit rounded-xl bg-[var(--surface-muted)] p-1" aria-label="Plan range">
        <RangeButton active={range === 'today'} onClick={() => setRange('today')}>Today</RangeButton>
        <RangeButton active={range === 'week'} onClick={() => setRange('week')}>This week</RangeButton>
      </div>
      <div className="inline-flex w-fit rounded-xl border border-[var(--line)] bg-[var(--surface)] p-1" aria-label="Task scope">
        <RangeButton active={scope === 'household'} onClick={() => setScope('household')}>Household</RangeButton>
        <RangeButton active={scope === 'mine'} onClick={() => setScope('mine')}>Assigned to me</RangeButton>
      </div>
    </div>

    {isReadOnly && <p className="rounded-xl border border-[#D19A4C]/35 bg-[#F6EADB] px-4 py-3 text-sm text-[#8A5D2F]">Guest access is read-only. You can review the household plan, but only members can change it.</p>}
    {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
    {conflicts.length > 0 && <p role="status" className="rounded-xl border border-[#D19A4C]/35 bg-[#F6EADB] px-4 py-3 text-sm text-[#8A5D2F]"><strong>Scheduling conflict:</strong> overlaps {conflicts.join(', ')}. The event was still saved.</p>}

    {composer === 'task' && <TaskComposer form={taskForm} members={membersQuery.data ?? []} isEditing={Boolean(editingTaskId)} pending={createTaskMutation.isPending || updateTaskMutation.isPending} onClose={closeTaskComposer} onSubmit={submitTask} setForm={setTaskForm} />}
    {composer === 'event' && <EventComposer form={eventForm} pending={createEventMutation.isPending} onClose={() => setComposer(null)} onSubmit={submitEvent} setForm={setEventForm} />}

    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_19rem]">
      <Card className="overflow-hidden">
        <SectionHeading title={range === 'today' ? 'Today’s timeline' : 'This week’s timeline'} detail="Events occupy time; tasks show their deadline without pretending to be an appointment." />
        {loading ? <LoadingPlan /> : <div className="mt-5 overflow-x-auto"><div className={`grid min-w-[44rem] divide-x divide-[var(--line)] ${range === 'today' ? 'grid-cols-1' : 'grid-cols-7'}`}>{days.map((day) => <DayColumn key={day.key} day={day} events={visibleEvents.filter((item) => isSameDay(item.starts_at, day.date))} tasks={datedTasks.filter((item) => isSameDay(item.due_at!, day.date))} members={memberNames} onEdit={isReadOnly ? undefined : beginTaskEdit} onToggle={(task) => statusMutation.mutate({ taskId: task.task_id, status: getNextTaskStatus(task.status) })} togglingId={statusMutation.variables?.taskId} />)}</div></div>}
      </Card>

      <aside className="space-y-5">
        <Card className="p-5"><SectionHeading title="Task inbox" detail={`${inboxTasks.length} not shown in this range`} />
          <div className="mt-4 space-y-3">{inboxTasks.length ? inboxTasks.map((task) => <div key={task.task_id} className="flex items-start gap-1"><div className="min-w-0 flex-1"><InboxTask task={task} assignee={task.assigned_to ? memberNames.get(task.assigned_to) ?? task.assigned_to : undefined} onToggle={() => statusMutation.mutate({ taskId: task.task_id, status: getNextTaskStatus(task.status) })} pending={statusMutation.isPending && statusMutation.variables?.taskId === task.task_id} /></div>{!isReadOnly && <TaskEditButton task={task} onEdit={() => beginTaskEdit(task)} />}</div>) : <p className="rounded-xl bg-[var(--surface-muted)] p-4 text-sm muted">Everything has a place in this view.</p>}</div>
        </Card>
        <Card className="bg-[#284837] p-5 text-white"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">Planning cue</p><p className="mt-3 text-sm font-semibold leading-6">Use events for fixed commitments. Keep flexible chores in the inbox until the household agrees on a time.</p></Card>
      </aside>
    </div>
  </section>;
}

function RangeButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${active ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--muted)] hover:text-[var(--ink)]'}`}>{children}</button>;
}

function TaskComposer({ form, members, isEditing, pending, onClose, onSubmit, setForm }: { form: CreateTaskInput; members: HouseholdMember[]; isEditing: boolean; pending: boolean; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; setForm: (form: CreateTaskInput) => void }) {
  return <Card className="p-5 sm:p-6"><form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
    <label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Task title</span><input autoFocus required className="task-input" placeholder="e.g. Pick up groceries" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Assignee</span><select className="task-input" value={form.assigned_to ?? ''} onChange={(event) => setForm({ ...form, assigned_to: event.target.value || undefined })}><option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Due</span><input className="task-input" type="datetime-local" value={form.due_at ?? ''} onChange={(event) => setForm({ ...form, due_at: event.target.value })} /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Priority</span><span className="relative block"><select className="task-input appearance-none" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as CreateTaskInput['priority'] })}><option value="Low">Low</option><option value="Normal">Normal</option><option value="High">High</option></select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={16} /></span></label>
    <label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Notes <span className="font-normal muted">(optional)</span></span><textarea className="task-input min-h-20 resize-y py-3" value={form.description ?? ''} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
    <div className="flex justify-end gap-2 md:col-span-2"><Button tone="neutral" onClick={onClose}>Cancel</Button><Button type="submit" disabled={pending}>{pending && <LoaderCircle className="animate-spin" size={16} />}{isEditing ? 'Update task' : 'Create task'}</Button></div>
  </form></Card>;
}

function EventComposer({ form, pending, onClose, onSubmit, setForm }: { form: CreateCalendarEventInput; pending: boolean; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; setForm: (form: CreateCalendarEventInput) => void }) {
  return <Card className="p-5 sm:p-6"><form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
    <label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Event title</span><input autoFocus required className="task-input" placeholder="e.g. School parent meeting" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Starts</span><input required className="task-input" type="datetime-local" value={form.starts_at} onChange={(event) => setForm({ ...form, starts_at: event.target.value })} /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Ends</span><input required className="task-input" type="datetime-local" value={form.ends_at} onChange={(event) => setForm({ ...form, ends_at: event.target.value })} /></label>
    <div className="flex justify-end gap-2 md:col-span-2"><Button tone="neutral" onClick={onClose}>Cancel</Button><Button type="submit" disabled={pending}>{pending && <LoaderCircle className="animate-spin" size={16} />}Create event</Button></div>
  </form></Card>;
}

function DayColumn({ day, events, tasks, members, onEdit, onToggle, togglingId }: { day: Day; events: CalendarEvent[]; tasks: HouseholdTask[]; members: Map<string, string>; onEdit?: (task: HouseholdTask) => void; onToggle: (task: HouseholdTask) => void; togglingId?: string }) {
  return <div className="min-h-80 p-3"><div className={`rounded-xl px-2 py-2 ${isToday(day.date) ? 'bg-[#E4F0E8]' : ''}`}><p className="text-xs font-bold uppercase tracking-[0.12em] text-[#676B68]">{day.weekday}</p><p className="mt-1 text-lg font-bold text-[var(--ink)]">{day.label}</p></div><div className="mt-3 space-y-2">{events.map((event) => <EventCard key={event.event_id} event={event} />)}{tasks.map((task) => <div key={task.task_id} className="flex items-start gap-1"><div className="min-w-0 flex-1"><TaskDeadlineCard task={task} assignee={task.assigned_to ? members.get(task.assigned_to) ?? task.assigned_to : undefined} onToggle={() => onToggle(task)} pending={togglingId === task.task_id} /></div>{onEdit && <TaskEditButton task={task} onEdit={() => onEdit(task)} />}</div>)}{events.length === 0 && tasks.length === 0 && <p className="px-2 pt-4 text-xs muted">Open</p>}</div></div>;
}

function EventCard({ event }: { event: CalendarEvent }) {
  return <article className="rounded-xl border border-[#5E9278]/25 bg-[#E4F0E8] p-3 text-[#284837]"><div className="flex gap-2"><CalendarDays className="mt-0.5 shrink-0" size={15} /><div className="min-w-0"><p className="text-sm font-semibold leading-5">{event.title}</p><p className="mt-1 text-xs text-[#3D5F4E]">{timeRange(event)}</p></div></div></article>;
}

function TaskDeadlineCard({ task, assignee, onToggle, pending }: { task: HouseholdTask; assignee?: string; onToggle: () => void; pending: boolean }) {
  const done = task.status === 'Done';
  return <article className={`rounded-xl border p-3 ${done ? 'border-[#D9D8D2] bg-[#ECEAE4] text-[#676B68]' : task.priority === 'High' ? 'border-[#D19A4C]/45 bg-[#F6EADB]' : 'border-[var(--line)] bg-[var(--surface)]'}`}><div className="flex gap-2"><button type="button" aria-label={`${done ? 'Reopen' : 'Complete'} ${task.title}`} onClick={onToggle} disabled={pending} className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border ${done ? 'border-[#5E9278] bg-[#5E9278] text-white' : 'border-[#B9B9B2] text-transparent hover:border-[#5E9278] hover:text-[#5E9278]'}`}>{pending ? <LoaderCircle className="animate-spin" size={12} /> : <Check size={12} />}</button><div className="min-w-0"><p className={`text-sm font-semibold leading-5 ${done ? 'line-through' : 'text-[var(--ink)]'}`}>{task.title}</p><p className="mt-1 flex items-center gap-1 text-xs muted"><Clock3 size={12} />Due {timeLabel(task.due_at!)}{assignee ? ` · ${assignee}` : ''}</p></div></div></article>;
}

function InboxTask({ task, assignee, onToggle, pending }: { task: HouseholdTask; assignee?: string; onToggle: () => void; pending: boolean }) {
  const done = task.status === 'Done';
  return <article className="flex gap-3 rounded-xl border border-[var(--line)] p-3"><button type="button" aria-label={`${done ? 'Reopen' : 'Complete'} ${task.title}`} onClick={onToggle} disabled={pending} className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border ${done ? 'border-[#5E9278] bg-[#5E9278] text-white' : 'border-[#B9B9B2] text-transparent hover:border-[#5E9278] hover:text-[#5E9278]'}`}>{pending ? <LoaderCircle className="animate-spin" size={12} /> : <Check size={12} />}</button><div className="min-w-0"><p className={`text-sm font-semibold ${done ? 'line-through text-[#676B68]' : 'text-[var(--ink)]'}`}>{task.title}</p><p className="mt-1 text-xs muted">{task.due_at ? `Due ${dateTimeLabel(task.due_at)}` : 'No due date'}{assignee ? ` · ${assignee}` : ''}</p><p className={`mt-2 inline-flex items-center gap-1 text-xs font-semibold ${task.priority === 'High' ? 'text-[#8A5D2F]' : 'text-[#676B68]'}`}><CircleDot size={12} />{task.priority} priority</p></div></article>;
}

function TaskEditButton({ task, onEdit }: { task: HouseholdTask; onEdit: () => void }) {
  return <button type="button" aria-label={`Edit ${task.title}`} title={`Edit ${task.title}`} onClick={onEdit} className="grid size-8 shrink-0 place-items-center rounded-lg text-[#676B68] transition hover:bg-[#ECEAE4] hover:text-[#284837] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5E9278]"><Pencil size={15} /></button>;
}

function LoadingPlan() { return <div className="flex min-h-80 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading household plan</div>; }

type Day = { date: Date; key: string; weekday: string; label: string };
function buildDays(range: 'today' | 'week'): Day[] { const start = startOfDay(new Date()); const count = range === 'today' ? 1 : 7; return Array.from({ length: count }, (_, index) => { const date = new Date(start); date.setDate(start.getDate() + index); return { date, key: dayKey(date), weekday: new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(date), label: new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date) }; }); }
function startOfDay(value: Date) { return new Date(value.getFullYear(), value.getMonth(), value.getDate()); }
function dayKey(value: Date) { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`; }
function isSameDay(value: string, day: Date) { const date = new Date(value); return !Number.isNaN(date.getTime()) && dayKey(date) === dayKey(day); }
function isInDays(value: string, days: Day[]) { return days.some((day) => isSameDay(value, day.date)); }
function isToday(value: Date) { return dayKey(value) === dayKey(new Date()); }
function timeLabel(value: string) { return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(value)); }
function dateTimeLabel(value: string) { return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value)); }
function timeRange(event: CalendarEvent) { return `${timeLabel(event.starts_at)}–${timeLabel(event.ends_at)}`; }
function taskSort(left: HouseholdTask, right: HouseholdTask) { if (left.status === 'Done' && right.status !== 'Done') return 1; if (right.status === 'Done' && left.status !== 'Done') return -1; return (left.due_at ?? '9999').localeCompare(right.due_at ?? '9999'); }
