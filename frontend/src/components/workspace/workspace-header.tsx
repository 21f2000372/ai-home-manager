import { ArrowUpRight } from 'lucide-react';

type WorkspaceHeaderProps = { label: string; eyebrow: string; onAction?: () => void; compact?: boolean };

export function WorkspaceHeader({ label, eyebrow, onAction, compact = false }: WorkspaceHeaderProps) {
  return <div className={`flex flex-col justify-between border-b border-[var(--line)] ${compact ? 'gap-2 pb-4 sm:flex-row sm:items-center' : 'gap-5 pb-6 sm:flex-row sm:items-end'}`}><div>{!compact && <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#D19A4C]">{eyebrow}</p>}<h1 className={`${compact ? 'text-2xl sm:text-3xl' : 'mt-2 text-3xl sm:text-4xl'} font-bold tracking-tight text-[var(--ink)]`}>{label}</h1>{!compact && <p className="mt-2 max-w-xl text-sm leading-6 muted">Keep {label.toLowerCase()} organized with one shared source of truth.</p>}</div>{compact && <p className="text-sm muted">Your household at a glance</p>}{onAction && <button onClick={onAction} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5E9278] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#4D7A64]">Add {label}<ArrowUpRight size={16} /></button>}</div>;
}
