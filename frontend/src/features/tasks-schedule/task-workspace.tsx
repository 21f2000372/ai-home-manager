import { FormEvent, useMemo, useState } from 'react';
import { Check, ChevronDown, LoaderCircle, Pencil, Plus, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { HouseholdChat } from '@/components/ai/household-chat';
import { ApiError } from '@/lib/api/request';
import { createTask, getHouseholdMembers, getTasks, updateTask, updateTaskStatus, type CreateTaskInput, type HouseholdMember, type HouseholdTask } from './task-api';
import { buildTaskSummary, formatDueDate, getNextTaskStatus, toDateTimeLocalValue } from './task-utils';

const taskQueryKey = ['household', 'tasks'] as const;

function taskTone(task: HouseholdTask) {
  if (task.status === 'Done') return 'bg-[#E4F0E8] text-[#3D5F4E]';
  if (task.priority === 'High') return 'bg-[#F6EADB] text-[#8A5D2F]';
  return 'bg-[#ECEAE4] text-[#676B68]';
}

function priorityTone(priority: HouseholdTask['priority']) {
  if (priority === 'High') return 'bg-[#F6EADB] text-[#8A5D2F]';
  if (priority === 'Low') return 'bg-[#E4F0E8] text-[#3D5F4E]';
  return 'bg-[#ECEAE4] text-[#676B68]';
}

export function TaskWorkspace() {
  const queryClient = useQueryClient();
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [form, setForm] = useState<CreateTaskInput>({ title: '', description: '', assigned_to: '', due_at: '', priority: 'Normal' });

  const tasksQuery = useQuery({ queryKey: taskQueryKey, queryFn: () => getTasks() });
  const membersQuery = useQuery({ queryKey: ['household', 'members'] as const, queryFn: getHouseholdMembers });

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: taskQueryKey });
      setForm({ title: '', description: '', assigned_to: '', due_at: '', priority: 'Normal' });
      setEditingTaskId(null);
      setIsComposerOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ taskId, input }: { taskId: string; input: CreateTaskInput }) => updateTask(taskId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: taskQueryKey });
      setForm({ title: '', description: '', assigned_to: '', due_at: '', priority: 'Normal' });
      setEditingTaskId(null);
      setIsComposerOpen(false);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: HouseholdTask['status'] }) => updateTaskStatus(taskId, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: taskQueryKey });
    },
  });

  const summary = useMemo(() => buildTaskSummary(tasksQuery.data ?? []), [tasksQuery.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.title.trim()) return;

    const dueAt = form.due_at ? new Date(form.due_at).toISOString() : undefined;
    const input = {
      ...form,
      title: form.title.trim(),
      description: form.description?.trim() || undefined,
      assigned_to: form.assigned_to?.trim() || undefined,
      due_at: dueAt,
    };

    if (editingTaskId) {
      updateMutation.mutate({ taskId: editingTaskId, input });
    } else {
      createMutation.mutate(input);
    }
  }

  function beginEdit(task: HouseholdTask) {
    setForm({
      title: task.title,
      description: task.description ?? '',
      assigned_to: task.assigned_to ?? '',
      due_at: toDateTimeLocalValue(task.due_at),
      priority: task.priority,
    });
    setEditingTaskId(task.task_id);
    setIsComposerOpen(true);
  }

  function closeComposer() {
    setForm({ title: '', description: '', assigned_to: '', due_at: '', priority: 'Normal' });
    setEditingTaskId(null);
    setIsComposerOpen(false);
  }

  const error = tasksQuery.error ?? createMutation.error ?? updateMutation.error ?? statusMutation.error ?? membersQuery.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not update tasks and schedule. Please try again.' : null;

  return (
    <section className="space-y-6">
      <div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Tasks & schedule</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Household tasks</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 muted">Live tasks and schedule information from the backend. Keep work visible, assign ownership, and avoid overbooking the household.</p>
        </div>
        <Button onClick={() => isComposerOpen ? closeComposer() : setIsComposerOpen(true)}>{isComposerOpen ? <X size={16} /> : <Plus size={16} />}{isComposerOpen ? 'Close form' : 'Add task'}</Button>
      </div>

      {isComposerOpen && <TaskComposer members={membersQuery.data ?? []} form={form} setForm={setForm} isEditing={Boolean(editingTaskId)} isPending={createMutation.isPending || updateMutation.isPending} onSubmit={submit} />}
      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
      <HouseholdChat
        title="Create task ideas by chat"
        description="Type, attach readable text, or dictate a request. The assistant will respond through the household agent."
        onMessageProcessed={() => queryClient.invalidateQueries({ queryKey: taskQueryKey })}
      />

      <div className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]">
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Current household work" detail={`${summary.open} open · ${summary.inProgress} in progress · ${summary.done} completed`} />
          {tasksQuery.isLoading ? (
            <div className="flex min-h-52 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading tasks</div>
          ) : tasksQuery.data?.length ? (
            <div className="mt-6 space-y-3">
              {tasksQuery.data.map((task) => (
                <TaskRow
                  key={task.task_id}
                  task={task}
                  isPending={statusMutation.isPending && statusMutation.variables?.taskId === task.task_id}
                  onEdit={() => beginEdit(task)}
                  onToggle={() => statusMutation.mutate({ taskId: task.task_id, status: getNextTaskStatus(task.status) })}
                />
              ))}
            </div>
          ) : (
            <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted">
              <p className="font-semibold text-[var(--ink)]">No tasks yet</p>
              <p className="mt-1">Add the first household task to get the day organized.</p>
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="p-6">
            <SectionHeading title="Task rhythm" detail="A quiet view of today" />
            <div className="mt-6 grid grid-cols-3 gap-3">
              <Metric value={summary.open} label="Open" />
              <Metric value={summary.inProgress} label="In progress" />
              <Metric value={summary.done} label="Done" />
            </div>
          </Card>

          <Card className="bg-[#284837] p-6 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">HomeOps tip</p>
            <p className="mt-3 text-lg font-bold leading-snug">Use chat later for natural-language task creation.</p>
            <p className="mt-2 text-sm leading-6 text-[#D2E6D8]">Manual and chat-created tasks will share this same household task list.</p>
          </Card>
        </div>
      </div>
    </section>
  );
}

function TaskComposer({ members, form, setForm, isEditing, isPending, onSubmit }: { members: HouseholdMember[]; form: CreateTaskInput; setForm: (value: CreateTaskInput) => void; isEditing: boolean; isPending: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return (
    <Card className="p-5 sm:p-6">
      <form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
        <label className="md:col-span-2">
          <span className="mb-1.5 block text-sm font-semibold">Task title</span>
          <input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="task-input" placeholder="e.g. Pick up groceries" />
        </label>

        <label>
          <span className="mb-1.5 block text-sm font-semibold">Assignee</span>
          <select value={form.assigned_to ?? ''} onChange={(event) => setForm({ ...form, assigned_to: event.target.value || undefined })} className="task-input">
            <option value="">Unassigned</option>
            {members.map((member) => <option key={member.user_id} value={member.user_id}>{member.name} ({member.role})</option>)}
          </select>
        </label>

        <label>
          <span className="mb-1.5 block text-sm font-semibold">Due date</span>
          <input type="datetime-local" value={form.due_at ?? ''} onChange={(event) => setForm({ ...form, due_at: event.target.value })} className="task-input" />
        </label>

        <label>
          <span className="mb-1.5 block text-sm font-semibold">Priority</span>
          <span className="relative block">
            <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as CreateTaskInput['priority'] })} className="task-input appearance-none">
              <option value="Low">Low</option>
              <option value="Normal">Normal</option>
              <option value="High">High</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={16} />
          </span>
        </label>

        <label className="md:col-span-2">
          <span className="mb-1.5 block text-sm font-semibold">Notes <span className="font-normal muted">(optional)</span></span>
          <textarea value={form.description ?? ''} onChange={(event) => setForm({ ...form, description: event.target.value })} className="task-input min-h-24 resize-y py-3" placeholder="Add any useful household context" />
        </label>

        <div className="md:col-span-2 flex justify-end">
          <Button type="submit" disabled={isPending}>{isPending && <LoaderCircle className="animate-spin" size={16} />}{isPending ? 'Saving…' : isEditing ? 'Update task' : 'Create task'}</Button>
        </div>
      </form>
    </Card>
  );
}

function TaskRow({ task, isPending, onEdit, onToggle }: { task: HouseholdTask; isPending: boolean; onEdit: () => void; onToggle: () => void }) {
  const isDone = task.status === 'Done';

  return (
    <article className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4 transition hover:bg-[#ECEAE4]/60">
      <button aria-label={`${isDone ? 'Reopen' : 'Complete'} ${task.title}`} onClick={onToggle} disabled={isPending} className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border transition ${isDone ? 'border-[#5E9278] bg-[#5E9278] text-white' : 'border-[#B9B9B2] text-transparent hover:border-[#5E9278] hover:text-[#5E9278]'}`}>
        {isPending ? <LoaderCircle className="animate-spin" size={14} /> : <Check size={14} />}
      </button>

      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold ${isDone ? 'text-[#676B68] line-through' : 'text-[var(--ink)]'}`}>{task.title}</p>
        {task.description && <p className="mt-1 text-sm muted">{task.description}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs muted">
          <span>{formatDueDate(task.due_at)}</span>
          {task.assigned_to && <span>Assigned to {task.assigned_to}</span>}
          <span className={`rounded-full px-2 py-0.5 font-semibold ${priorityTone(task.priority)}`}>{task.priority} priority</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <button type="button" aria-label={`Edit ${task.title}`} title={`Edit ${task.title}`} onClick={onEdit} className="grid size-8 place-items-center rounded-full text-[#676B68] transition hover:bg-[#ECEAE4] hover:text-[#284837]">
          <Pencil size={15} />
        </button>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${taskTone(task)}`}>{task.status === 'InProgress' ? 'In progress' : task.status}</span>
      </div>
    </article>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-xl bg-[#ECEAE4] p-4">
      <p className="text-2xl font-bold">{value}</p>
      <p className="mt-1 text-xs muted">{label}</p>
    </div>
  );
}
