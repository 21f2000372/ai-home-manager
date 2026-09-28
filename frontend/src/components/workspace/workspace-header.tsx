import { ArrowUpRight } from 'lucide-react';

type WorkspaceHeaderProps = { label: string; eyebrow: string; onAction?: () => void };

export function WorkspaceHeader({ label, eyebrow, onAction }: WorkspaceHeaderProps) {
  return <div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#D19A4C]">{eyebrow}</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--ink)] sm:text-4xl">{label}</h1><p className="mt-2 max-w-xl text-sm leading-6 muted">Keep {label.toLowerCase()} organized with one shared source of truth.</p></div>{onAction && <button onClick={onAction} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5E9278] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#4D7A64]">Add {label}<ArrowUpRight size={16} /></button>}</div>;
}
