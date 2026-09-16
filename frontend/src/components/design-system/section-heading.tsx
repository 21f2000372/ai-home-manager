import type { ReactNode } from 'react';

export function SectionHeading({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="flex items-start justify-between gap-4"><div><h2 className="font-display text-lg font-semibold text-[var(--ink)]">{title}</h2>{detail && <p className="mt-1 text-xs muted">{detail}</p>}</div>{action}</div>;
}
