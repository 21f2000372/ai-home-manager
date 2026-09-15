import { ArrowUpRight } from 'lucide-react';

type WorkspaceHeaderProps = { label: string; eyebrow: string; onAction?: () => void };

export function WorkspaceHeader({ label, eyebrow, onAction }: WorkspaceHeaderProps) {
  return <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#ef8354]">{eyebrow}</p><h1 className="mt-2 text-4xl font-semibold tracking-tight text-[#102a43]">{label}</h1><p className="mt-2 max-w-xl text-slate-500">Keep {label.toLowerCase()} organized with one shared source of truth.</p></div><button onClick={onAction} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#102a43] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#163b5c]">Add {label}<ArrowUpRight size={16} /></button></div>;
}