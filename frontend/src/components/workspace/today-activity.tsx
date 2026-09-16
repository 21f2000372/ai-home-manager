import { events } from '@/data/homeops-fixtures';

function Activity({ title, meta }: { title: string; meta: string }) {
  return <div className="flex items-center gap-3"><span className="size-2 rounded-full bg-[#ef8354]" /><div><p className="text-sm font-semibold">{title}</p><p className="text-xs text-slate-500">{meta}</p></div></div>;
}

export function TodayActivity() {
  return <div className="surface rounded-xl border p-6 shadow-sm"><div className="flex items-center justify-between"><h2 className="font-display text-lg font-semibold text-[var(--ink)]">Upcoming household timeline</h2><span className="text-xs font-semibold muted">{events.length} items</span></div><div className="mt-6 space-y-5">{events.map((event) => <Activity key={event.id} title={event.title} meta={`${event.date} · ${event.place}`} />)}</div></div>;
}