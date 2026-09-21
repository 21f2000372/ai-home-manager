import { describe, expect, it } from 'vitest';
import { buildTaskSummary, formatDueDate, getNextTaskStatus } from './task-utils';

describe('task utils', () => {
  it('summarizes open, in progress, and completed tasks', () => {
    const summary = buildTaskSummary([
      { task_id: '1', title: 'Wash dishes', description: null, assigned_to: null, due_at: null, priority: 'Normal', status: 'Open' },
      { task_id: '2', title: 'Vacuum', description: null, assigned_to: null, due_at: null, priority: 'High', status: 'InProgress' },
      { task_id: '3', title: 'Fold laundry', description: null, assigned_to: null, due_at: null, priority: 'Low', status: 'Done' },
      { task_id: '4', title: 'Water plants', description: null, assigned_to: null, due_at: null, priority: 'Normal', status: 'Cancelled' },
    ]);

    expect(summary).toEqual({ open: 1, inProgress: 1, done: 1, total: 4 });
  });

  it('formats a due date for display', () => {
    expect(formatDueDate('2026-09-19T18:30:00Z')).toMatch(/Sep|Sep/);
  });

  it('toggles a completed task back to open', () => {
    expect(getNextTaskStatus('Done')).toBe('Open');
    expect(getNextTaskStatus('Open')).toBe('Done');
  });
});
