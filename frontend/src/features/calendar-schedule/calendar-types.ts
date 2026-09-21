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

export type CalendarCreateResult = {
  event: CalendarEvent;
  conflicts: CalendarEvent[];
  has_conflict: boolean;
};
