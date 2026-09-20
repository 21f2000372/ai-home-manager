import type { HouseholdTask, TaskStatus, TaskSummary } from './task-types';

export function formatDueDate(value: string | null): string {
  if (!value) return 'No due date';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No due date';

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export function toDateTimeLocalValue(value: string | null): string {
  if (!value) return '';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function buildTaskSummary(tasks: HouseholdTask[]): TaskSummary {
  return {
    open: tasks.filter((task) => task.status === 'Open').length,
    inProgress: tasks.filter((task) => task.status === 'InProgress').length,
    done: tasks.filter((task) => task.status === 'Done').length,
    total: tasks.length,
  };
}

export function getNextTaskStatus(status: TaskStatus): TaskStatus {
  return status === 'Done' ? 'Open' : 'Done';
}
