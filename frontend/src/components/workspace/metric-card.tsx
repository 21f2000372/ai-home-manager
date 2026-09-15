import type { ReactNode } from 'react';

type MetricCardProps = { icon: ReactNode; value: string; label: string; tone: 'green' | 'blue' | 'orange' };

export function MetricCard({ icon, value, label, tone }: MetricCardProps) {
  const colors = { green: 'bg-[#dcefeb] text-[#27736d]', blue: 'bg-[#e0ecf4] text-[#346b8e]', orange: 'bg-[#fff0e9] text-[#c2603c]' };
  return <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5"><div className={`grid size-11 place-items-center rounded-xl ${colors[tone]}`}>{icon}</div><div><p className="font-display text-2xl font-semibold">{value}</p><p className="text-sm text-slate-500">{label}</p></div></div>;
}