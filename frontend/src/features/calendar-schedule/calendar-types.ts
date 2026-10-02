export type CalendarEvent = {
  event_id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  owner_id: string | null;
};

export type CreateCalendarEventInput = {
  title: string;
  starts_at: string;
  ends_at: string;
};

export type CalendarConflict = {
  title: string;
};

export type CalendarConflicts = {
  has_conflict: boolean;
  calendar_conflicts: CalendarConflict[];
  task_conflicts: CalendarConflict[];
};

export type CalendarCreateResult = {
  event: CalendarEvent;
  conflicts: CalendarConflicts;
};
