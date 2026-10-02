import type { ReactNode } from 'react';

type MetricCardProps = { icon: ReactNode; value: string; label: string; tone: 'green' | 'blue' | 'orange' };

export function MetricCard({ icon, value, label, tone }: MetricCardProps) {
  const colors = { green: 'bg-[#dcefeb] text-[#27736d]', blue: 'bg-[#e0ecf4] text-[#346b8e]', orange: 'bg-[#fff0e9] text-[#c2603c]' };
  return <div className="surface flex items-center gap-3 rounded-xl border p-4 shadow-sm"><div className={`grid size-9 place-items-center rounded-lg ${colors[tone]}`}>{icon}</div><div><p className="font-display text-xl font-semibold text-[var(--ink)]">{value}</p><p className="text-xs muted">{label}</p></div></div>;
}
