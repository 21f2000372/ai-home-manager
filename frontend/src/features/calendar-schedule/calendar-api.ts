import { request } from '@/lib/api/request';
import type { CalendarCreateResult, CalendarEvent, CreateCalendarEventInput } from './calendar-types';

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function getCalendarEvents() {
  return request<CalendarEvent[]>('/api/calendar', {}, requestContext());
}

export function createCalendarEvent(input: CreateCalendarEventInput) {
  return request<CalendarCreateResult>('/api/calendar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}
