import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/styles/cn';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-2xl border border-[var(--line)] bg-[var(--surface)] shadow-sm shadow-[#171918]/[0.03]', className)} {...props} />;
}
