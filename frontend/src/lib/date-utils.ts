// src/lib/date-utils.ts

/**
 * Safely parses any date or datetime string from the backend into a Date object.
 * - Date-only strings ('YYYY-MM-DD') are parsed as local calendar dates to avoid 1-day shifts.
 * - DateTime strings without timezone ('YYYY-MM-DDTHH:mm:ss' or 'YYYY-MM-DD HH:mm:ss')
 *   are treated as UTC because SQLite/Flask stores naive UTC.
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const clean = value.trim();
  if (!clean) return null;

  // 1. Date-only format: YYYY-MM-DD
  const dateOnlyMatch = clean.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch;
    return new Date(Number(year), Number(month) - 1, Number(day));
  }

  // 2. DateTime format: replace space with T if needed (SQLite format)
  let normalized = clean.replace(' ', 'T');

  // If it has a time component (has 'T') but no timezone indicator (no 'Z' and no +/-offset),
  // append 'Z' so JavaScript treats it as UTC.
  if (
    normalized.includes('T') &&
    !normalized.endsWith('Z') &&
    !/[+-]\d{2}(:\d{2})?$/.test(normalized)
  ) {
    normalized = `${normalized}Z`;
  }

  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Converts a backend ISO/UTC datetime string to <input type="datetime-local" /> format in LOCAL time.
 */
export function toDateTimeLocalValue(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return '';

  const pad = (n: number) => String(n).padStart(2, '0');
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Converts a date-only string or datetime to <input type="date" /> format in LOCAL calendar date.
 */
export function toDateInputValue(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return '';

  const pad = (n: number) => String(n).padStart(2, '0');
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());

  return `${year}-${month}-${day}`;
}

/**
 * Converts a local datetime-local string (e.g. "2026-10-15T18:00") into a UTC ISO string with 'Z'
 * for submitting to the backend.
 */
export function localInputToUtcIso(value: string | null | undefined): string | undefined {
  if (!value || !value.trim()) return undefined;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toISOString();
}

/**
 * Formats a datetime for display (e.g. "Oct 15, 6:00 PM").
 */
export function formatLocalDateTime(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return 'No due date';

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

/**
 * Formats time only (e.g. "6:00 PM").
 */
export function formatLocalTime(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return '';

  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

/**
 * Formats calendar date with weekday (e.g. "Thu, Oct 15, 6:00 PM").
 */
export function formatCalendarDate(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return 'Invalid date';

  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

/**
 * Returns a stable local calendar day key: YYYY-MM-DD.
 */
export function localDayKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * Checks if a server date falls on the target local calendar date.
 */
export function isSameLocalDate(value: string | null | undefined, targetDate: Date): boolean {
  const date = parseServerDate(value);
  if (!date) return false;
  return localDayKey(date) === localDayKey(targetDate);
}