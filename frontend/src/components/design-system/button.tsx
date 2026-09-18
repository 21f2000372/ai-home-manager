import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/styles/cn';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: 'accent' | 'neutral' | 'danger';
};

const toneClasses = {
  accent: 'bg-[#5E9278] text-white hover:bg-[#4D7A64]',
  neutral: 'border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-muted)]',
  danger: 'bg-red-600 text-white hover:bg-red-700',
};

export function Button({ className, tone = 'accent', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5E9278] disabled:cursor-not-allowed disabled:opacity-50',
        toneClasses[tone],
        className,
      )}
      type={type}
      {...props}
    />
  );
}
