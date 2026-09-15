function Activity({ title, meta }: { title: string; meta: string }) {
  return <div className="flex items-center gap-3"><span className="size-2 rounded-full bg-[#ef8354]" /><div><p className="text-sm font-semibold">{title}</p><p className="text-xs text-slate-500">{meta}</p></div></div>;
}

export function TodayActivity() {
  return <div className="rounded-2xl border border-slate-200 bg-white p-7"><div className="flex items-center justify-between"><h2 className="font-display text-lg font-semibold">Today at home</h2><span className="text-xs font-semibold text-slate-400">3 items</span></div><div className="mt-6 space-y-5"><Activity title="School pickup" meta="Today · 3:30 PM" /><Activity title="Replace HVAC filter" meta="Due today" /><Activity title="Weekly grocery run" meta="Today · 6:00 PM" /></div></div>;
}