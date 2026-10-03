// src/features/tasks-schedule/task-types.ts
export type TaskStatus = 'Open' | 'InProgress' | 'Done' | 'Cancelled';
export type TaskPriority = 'Low' | 'Normal' | 'High';

export type HouseholdTask = {
  task_id: string;
  title: string;
  description: string | null;
  assigned_to: string | null;
  due_at: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  created_at?: string;
};

export type CreateTaskInput = {
  title: string;
  description?: string;
  assigned_to?: string | null;
  due_at?: string;
  priority: TaskPriority;
  force?: boolean;
};

export type CalendarConflictItem = {
  event_id?: string;
  title: string;
  starts_at?: string;
  ends_at?: string;
};

export type TaskConflictItem = {
  task_id?: string;
  title: string;
  due_at?: string;
  priority?: string;
  assigned_to?: string;
  person_name?: string;
};

export type ScheduleConflict = {
  has_conflict: boolean;
  calendar_conflicts: CalendarConflictItem[];
  task_conflicts: TaskConflictItem[];
};

export type TaskCreateResult = {
  task: HouseholdTask;
  conflicts: ScheduleConflict;
};

export type HouseholdMember = {
  user_id: string;
  name: string;
  role: 'Admin' | 'Adult' | 'Child' | 'Guest';
};

export type TaskQueryParams = {
  assigned_to?: string;
  status?: TaskStatus | 'All';
};

export type TaskSummary = {
  open: number;
  inProgress: number;
  done: number;
  total: number;
};