import type { CalendarEvent } from './calendar-types';
import {
  formatCalendarDate,
  toDateTimeLocalValue,
} from '@/lib/date-utils';

export { formatCalendarDate, toDateTimeLocalValue };

export function formatEventRange(event: CalendarEvent): string {
  return `${formatCalendarDate(event.starts_at)} — ${formatCalendarDate(event.ends_at)}`;
}