// src/features/calendar-schedule/calendar-types.ts
export type EventAttendee = {
  user_id: string;
  name: string;
};

export type CalendarEvent = {
  event_id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  owner_id: string | null;
  attendees?: EventAttendee[];
};

export type CreateCalendarEventInput = {
  title: string;
  starts_at: string;
  ends_at: string;
  attendee_ids?: string[];
  force?: boolean;
};

export type CalendarConflict = {
  event_id?: string;
  title: string;
  starts_at?: string;
  ends_at?: string;
};

export type TaskConflict = {
  task_id?: string;
  title: string;
  due_at?: string;
  priority?: string;
  assigned_to?: string;
  person_name?: string;
};

export type CalendarScheduleConflict = {
  has_conflict: boolean;
  calendar_conflicts: CalendarConflict[];
  task_conflicts: TaskConflict[];
};

// Alias to maintain compatibility across workspaces
export type CalendarConflicts = CalendarScheduleConflict;

export type CalendarCreateResult = {
  event: CalendarEvent;
  conflicts: CalendarScheduleConflict;
};