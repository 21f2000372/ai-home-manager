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
};

export type CreateTaskInput = {
  title: string;
  description?: string;
  assigned_to?: string | null;
  due_at?: string;
  priority: TaskPriority;
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
