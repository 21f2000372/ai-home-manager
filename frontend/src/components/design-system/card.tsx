import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/styles/cn';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-2xl border border-slate-200 bg-white', className)} {...props} />;
}