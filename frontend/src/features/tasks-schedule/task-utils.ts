import type { HouseholdTask, TaskStatus, TaskSummary } from './task-types';
import {
  formatLocalDateTime,
  toDateTimeLocalValue,
  parseServerDate,
} from '@/lib/date-utils';

export { toDateTimeLocalValue, parseServerDate };

export function formatDueDate(value: string | null | undefined): string {
  return formatLocalDateTime(value);
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