import React from 'react';

type BadgeProps = {
  children: React.ReactNode;
  variant?: string;
  size?: string;
  className?: string;
};

export const Badge = ({ children, variant = 'default', size = 'md', className = '' }: BadgeProps) => {
  const variantStyles = {
    default: 'bg-slate-800 text-slate-300 border-slate-700',
    brand: 'bg-brand-500/15 text-brand-300 border-brand-500/30',
    purple: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    rose: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    outline: 'bg-transparent text-slate-300 border-slate-700',
  };

  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-semibold',
    lg: 'text-sm px-3 py-1 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border transition-colors ${variantStyles[variant] || variantStyles.default} ${sizeStyles[size] || sizeStyles.md} ${className}`}
    >
      {children}
    </span>
  );
};
