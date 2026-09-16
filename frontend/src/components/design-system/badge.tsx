import type { ReactNode } from 'react';
import { cn } from '@/lib/styles/cn';

export type BadgeTone = 'ready' | 'attention' | 'verified' | 'planned' | 'neutral';

const toneClasses: Record<BadgeTone, string> = {
  ready: 'bg-[#e1f1eb] text-[#27736d]',
  attention: 'bg-[#fff0e9] text-[#c2603c]',
  verified: 'bg-[#e3edf8] text-[#346b8e]',
  planned: 'bg-[#f0edf8] text-[#65508e]',
  neutral: 'bg-[var(--surface-muted)] text-[var(--muted)]',
};

export function Badge({ tone = 'neutral', children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold', toneClasses[tone], className)}>{children}</span>;
}
