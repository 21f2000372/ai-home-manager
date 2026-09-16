export function Progress({ value, label }: { value: number; label: string }) {
  return <div aria-label={`${label}: ${value}%`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><div className="flex items-center justify-between text-xs"><span className="muted">{label}</span><span className="font-semibold text-[var(--ink)]">{value}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-muted)]"><div className="h-full rounded-full bg-[#27736d] transition-[width]" style={{ width: `${value}%` }} /></div></div>;
}
