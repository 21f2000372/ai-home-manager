import type { ReactNode } from 'react';

type MetricCardProps = { icon: ReactNode; value: string; label: string; tone: 'green' | 'blue' | 'orange' };

export function MetricCard({ icon, value, label, tone }: MetricCardProps) {
  const colors = { green: 'bg-[#dcefeb] text-[#27736d]', blue: 'bg-[#e0ecf4] text-[#346b8e]', orange: 'bg-[#fff0e9] text-[#c2603c]' };
  return <div className="surface flex items-center gap-4 rounded-xl border p-5 shadow-sm"><div className={`grid size-11 place-items-center rounded-xl ${colors[tone]}`}>{icon}</div><div><p className="font-display text-2xl font-semibold text-[var(--ink)]">{value}</p><p className="text-sm muted">{label}</p></div></div>;
}