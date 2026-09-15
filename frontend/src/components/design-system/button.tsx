import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/styles/cn';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: 'accent' | 'neutral' | 'danger';
};

const toneClasses = {
  accent: 'bg-[#ef8354] text-white hover:bg-[#df7042]',
  neutral: 'border border-slate-200 bg-white text-[#102a43] hover:bg-slate-50',
  danger: 'bg-red-600 text-white hover:bg-red-700',
};

export function Button({ className, tone = 'accent', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ef8354] disabled:cursor-not-allowed disabled:opacity-50',
        toneClasses[tone],
        className,
      )}
      type={type}
      {...props}
    />
  );
}