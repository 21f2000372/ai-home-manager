import { FormEvent, useMemo, useState } from 'react';
import { CalendarDays, Check, LoaderCircle, Plus, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HouseholdChat } from '@/components/ai/household-chat';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { createCalendarEvent, getCalendarEvents } from './calendar-api';
import type { CreateCalendarEventInput } from './calendar-types';
import { formatEventRange } from './calendar-utils';
import { localInputToUtcIso } from '@/lib/date-utils';

const calendarQueryKey = ['household', 'calendar'] as const;

const emptyForm: CreateCalendarEventInput = {
  title: '',
  starts_at: '',
  ends_at: '',
};

export function CalendarWorkspace() {
  const queryClient = useQueryClient();
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [form, setForm] = useState<CreateCalendarEventInput>(emptyForm);
  const [conflicts, setConflicts] = useState<CreateCalendarEventInput['title'][]>([]);

  const eventsQuery = useQuery({ queryKey: calendarQueryKey, queryFn: getCalendarEvents });
  const createMutation = useMutation({
    mutationFn: createCalendarEvent,
    onSuccess: async (result) => {
      setConflicts([...result.conflicts.calendar_conflicts, ...result.conflicts.task_conflicts].map((conflict) => conflict.title));
      await queryClient.invalidateQueries({ queryKey: calendarQueryKey });
      setForm(emptyForm);
      setIsComposerOpen(false);
    },
  });

  const sortedEvents = useMemo(
    () => [...(eventsQuery.data ?? [])].sort((left, right) => left.starts_at.localeCompare(right.starts_at)),
    [eventsQuery.data],
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.title.trim() || !form.starts_at || !form.ends_at) return;

    const startsAtIso = localInputToUtcIso(form.starts_at);
    const endsAtIso = localInputToUtcIso(form.ends_at);

    if (!startsAtIso || !endsAtIso || new Date(endsAtIso) <= new Date(startsAtIso)) return;

    setConflicts([]);
    createMutation.mutate({
      title: form.title.trim(),
      starts_at: startsAtIso,
      ends_at: endsAtIso,
    });
  }

  function closeComposer() {
    setForm(emptyForm);
    setIsComposerOpen(false);
  }

  const error = eventsQuery.error ?? createMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not update the shared calendar.' : null;

  return (
    <section className="space-y-6">
      <div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Schedule & events</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Shared calendar</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 muted">Keep household commitments visible and get a conflict warning before a new event is saved.</p>
        </div>
        <Button onClick={() => isComposerOpen ? closeComposer() : setIsComposerOpen(true)}>{isComposerOpen ? <X size={16} /> : <Plus size={16} />}{isComposerOpen ? 'Close form' : 'Add event'}</Button>
      </div>

      {isComposerOpen && <CalendarComposer form={form} setForm={setForm} isPending={createMutation.isPending} onSubmit={submit} />}
      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
      {conflicts.length > 0 && <ConflictNotice conflicts={conflicts} />}

      <HouseholdChat
        title="Plan an event by chat"
        description="Describe a household commitment, attach context, or dictate a scheduling request."
        onMessageProcessed={() => queryClient.invalidateQueries({ queryKey: calendarQueryKey })}
      />

      <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Upcoming household timeline" detail={eventsQuery.isLoading ? 'Loading events...' : `${sortedEvents.length} shared events`} />
          {eventsQuery.isLoading ? (
            <div className="flex min-h-52 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading calendar</div>
          ) : sortedEvents.length ? (
            <div className="mt-6 space-y-3">
              {sortedEvents.map((event) => <CalendarEventRow key={event.event_id} title={event.title} range={formatEventRange(event)} />)}
            </div>
          ) : (
            <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted"><p className="font-semibold text-[var(--ink)]">No events yet</p><p className="mt-1">Add the first shared event to start the household timeline.</p></div>
          )}
        </Card>

        <Card className="p-5 sm:p-6">
          <SectionHeading title="Schedule controls" detail="Keep planning explicit and reviewable." />
          <div className="mt-6 space-y-3 text-sm muted">
            <div className="flex gap-3 rounded-xl bg-[#E4F0E8] p-4"><Check className="shrink-0 text-[#3D5F4E]" size={18} /><p>New events are checked against existing household commitments.</p></div>
            <div className="flex gap-3 rounded-xl bg-[#ECEAE4] p-4"><CalendarDays className="shrink-0 text-[#5E9278]" size={18} /><p>Calendar data comes directly from the backend shared-event API.</p></div>
          </div>
        </Card>
      </div>
    </section>
  );
}

function CalendarComposer({ form, setForm, isPending, onSubmit }: { form: CreateCalendarEventInput; setForm: (value: CreateCalendarEventInput) => void; isPending: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Card className="p-5 sm:p-6"><form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
    <label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Event title</span><input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="task-input" placeholder="e.g. School parent meeting" /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Starts</span><input required type="datetime-local" value={form.starts_at} onChange={(event) => setForm({ ...form, starts_at: event.target.value })} className="task-input" /></label>
    <label><span className="mb-1.5 block text-sm font-semibold">Ends</span><input required type="datetime-local" value={form.ends_at} onChange={(event) => setForm({ ...form, ends_at: event.target.value })} className="task-input" /></label>
    <div className="md:col-span-2 flex justify-end"><Button type="submit" disabled={isPending}>{isPending && <LoaderCircle className="animate-spin" size={16} />}{isPending ? 'Saving...' : 'Create event'}</Button></div>
  </form></Card>;
}

function CalendarEventRow({ title, range }: { title: string; range: string }) {
  return <article className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4"><div className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#E4F0E8] text-[#3D5F4E]"><CalendarDays size={17} /></div><div className="min-w-0"><p className="text-sm font-semibold text-[var(--ink)]">{title}</p><p className="mt-1 text-xs muted">{range}</p></div></article>;
}

function ConflictNotice({ conflicts }: { conflicts: string[] }) {
  return <div role="status" className="rounded-xl border border-[#D19A4C]/35 bg-[#F6EADB] px-4 py-3 text-sm text-[#8A5D2F]"><p className="font-semibold">Scheduling conflict detected</p><p className="mt-1">This event overlaps: {conflicts.join(', ')}. The event was saved with the warning.</p></div>;
}
