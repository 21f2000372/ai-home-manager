import { FormEvent, useMemo, useState } from 'react';
import { Check, ChevronDown, CircleAlert, LoaderCircle, Plus, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { createTask, getTasks, type CreateTaskInput, type HouseholdTask, updateTaskStatus } from './task-api';

const taskQueryKey = ['household', 'tasks'] as const;

function formatDueDate(value: string | null) {
  if (!value) return 'No due date';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value));
}

function taskTone(task: HouseholdTask) {
  if (task.status === 'Done') return 'bg-[#E4F0E8] text-[#3D5F4E]';
  if (task.priority === 'High') return 'bg-[#F6EADB] text-[#8A5D2F]';
  return 'bg-[#ECEAE4] text-[#676B68]';
}

export function TaskWorkspace() {
  const queryClient = useQueryClient();
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [form, setForm] = useState<CreateTaskInput>({ title: '', description: '', due_at: '', priority: 'Normal' });
  const tasksQuery = useQuery({ queryKey: taskQueryKey, queryFn: getTasks });
  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: taskQueryKey });
      setForm({ title: '', description: '', due_at: '', priority: 'Normal' });
      setIsComposerOpen(false);
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: HouseholdTask['status'] }) => updateTaskStatus(taskId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: taskQueryKey }),
  });
  const summary = useMemo(() => {
    const tasks = tasksQuery.data ?? [];
    return { open: tasks.filter((task) => task.status !== 'Done' && task.status !== 'Cancelled').length, done: tasks.filter((task) => task.status === 'Done').length };
  }, [tasksQuery.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.title.trim()) return;
    const dueAt = form.due_at ? new Date(form.due_at).toISOString().replace('Z', '') : undefined;
    createMutation.mutate({ ...form, title: form.title.trim(), description: form.description?.trim() || undefined, due_at: dueAt });
  }

  const error = tasksQuery.error ?? createMutation.error ?? statusMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not update tasks. Please try again.' : null;

  return <section className="space-y-6"><div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Tasks & schedule</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Household tasks</h1><p className="mt-2 max-w-xl text-sm leading-6 muted">Live tasks from the household API. Create work, keep ownership clear, and complete it as it happens.</p></div><Button onClick={() => setIsComposerOpen((open) => !open)}>{isComposerOpen ? <X size={16} /> : <Plus size={16} />}{isComposerOpen ? 'Close form' : 'Add task'}</Button></div>{isComposerOpen && <TaskComposer form={form} setForm={setForm} isPending={createMutation.isPending} onSubmit={submit} />}{errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}<div className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]"><Card className="p-5 sm:p-6"><SectionHeading title="Current household work" detail={`${summary.open} open · ${summary.done} completed`} />{tasksQuery.isLoading ? <div className="flex min-h-52 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading tasks</div> : tasksQuery.data?.length ? <div className="mt-6 space-y-3">{tasksQuery.data.map((task) => <TaskRow key={task.task_id} task={task} isPending={statusMutation.isPending && statusMutation.variables?.taskId === task.task_id} onToggle={() => statusMutation.mutate({ taskId: task.task_id, status: task.status === 'Done' ? 'Open' : 'Done' })} />)}</div> : <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted"><p className="font-semibold text-[var(--ink)]">No tasks yet</p><p className="mt-1">Add the first household task to get the day organized.</p></div>}</Card><div className="space-y-5"><Card className="p-6"><SectionHeading title="Task rhythm" detail="A quiet view of today" /><div className="mt-6 grid grid-cols-2 gap-3"><Metric value={summary.open} label="Open" /><Metric value={summary.done} label="Done" /></div></Card><Card className="bg-[#284837] p-6 text-white"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">HomeOps tip</p><p className="mt-3 text-lg font-bold leading-snug">Use chat later for natural-language task creation.</p><p className="mt-2 text-sm leading-6 text-[#D2E6D8]">Manual and chat-created tasks will share this same household task list.</p></Card></div></div></section>;
}

function TaskComposer({ form, setForm, isPending, onSubmit }: { form: CreateTaskInput; setForm: (value: CreateTaskInput) => void; isPending: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Card className="p-5 sm:p-6"><form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}><label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Task title</span><input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="task-input" placeholder="e.g. Pick up groceries" /></label><label><span className="mb-1.5 block text-sm font-semibold">Due date</span><input type="datetime-local" value={form.due_at ?? ''} onChange={(event) => setForm({ ...form, due_at: event.target.value })} className="task-input" /></label><label><span className="mb-1.5 block text-sm font-semibold">Priority</span><span className="relative block"><select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as CreateTaskInput['priority'] })} className="task-input appearance-none"><option value="Low">Low</option><option value="Normal">Normal</option><option value="High">High</option></select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={16} /></span></label><label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Notes <span className="font-normal muted">(optional)</span></span><textarea value={form.description ?? ''} onChange={(event) => setForm({ ...form, description: event.target.value })} className="task-input min-h-24 resize-y py-3" placeholder="Add any useful household context" /></label><div className="md:col-span-2 flex justify-end"><Button type="submit" disabled={isPending}>{isPending && <LoaderCircle className="animate-spin" size={16} />}{isPending ? 'Saving…' : 'Create task'}</Button></div></form></Card>;
}

function TaskRow({ task, isPending, onToggle }: { task: HouseholdTask; isPending: boolean; onToggle: () => void }) {
  const isDone = task.status === 'Done';
  return <article className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4 transition hover:bg-[#ECEAE4]/60"><button aria-label={`${isDone ? 'Reopen' : 'Complete'} ${task.title}`} onClick={onToggle} disabled={isPending} className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border transition ${isDone ? 'border-[#5E9278] bg-[#5E9278] text-white' : 'border-[#B9B9B2] text-transparent hover:border-[#5E9278] hover:text-[#5E9278]'}`}>{isPending ? <LoaderCircle className="animate-spin" size={14} /> : <Check size={14} />}</button><div className="min-w-0 flex-1"><p className={`text-sm font-semibold ${isDone ? 'text-[#676B68] line-through' : 'text-[var(--ink)]'}`}>{task.title}</p>{task.description && <p className="mt-1 text-sm muted">{task.description}</p>}<p className="mt-2 text-xs muted">{formatDueDate(task.due_at)}{task.assigned_to ? ` · Assigned to ${task.assigned_to}` : ''}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${taskTone(task)}`}>{task.status === 'InProgress' ? 'In progress' : task.status}</span></article>;
}

function Metric({ value, label }: { value: number; label: string }) {
  return <div className="rounded-xl bg-[#ECEAE4] p-4"><p className="text-2xl font-bold">{value}</p><p className="mt-1 text-xs muted">{label}</p></div>;
}
