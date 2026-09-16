import { ArrowUpRight } from 'lucide-react';

type WorkspaceHeaderProps = { label: string; eyebrow: string; onAction?: () => void };

export function WorkspaceHeader({ label, eyebrow, onAction }: WorkspaceHeaderProps) {
  return <div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#ee7b4b]">{eyebrow}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl">{label}</h1><p className="mt-2 max-w-xl text-sm leading-6 muted">Keep {label.toLowerCase()} organized with one shared source of truth.</p></div><button onClick={onAction} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#27736d] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#205d59]">Add {label}<ArrowUpRight size={16} /></button></div>;
}