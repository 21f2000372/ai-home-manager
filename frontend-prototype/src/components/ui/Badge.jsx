import React from 'react';

/**
 * Reusable Badge component matching HomeOps accents:
 * primary (Sage), agent (Mint), info (Slate Blue), warning (Ochre), critical (Terracotta), neutral
 */
export const Badge = ({
  children,
  variant = 'neutral', // 'primary', 'agent', 'info', 'warning', 'critical', 'neutral'
  size = 'sm',        // 'xs', 'sm', 'md'
  className = '',
  icon: Icon,
  ...props
}) => {
  const sizeStyles = {
    xs: 'text-[10px] px-2 py-0.5 font-medium',
    sm: 'text-xs px-2.5 py-0.5 font-medium',
    md: 'text-xs px-3 py-1 font-semibold',
  };

  const variantStyles = {
    primary: 'bg-[#5E9278]/15 text-[#3d6551] dark:text-[#9BCDB4] border border-[#5E9278]/30',
    agent: 'bg-[#9BCDB4]/20 text-[#2f614b] dark:text-[#9BCDB4] border border-[#9BCDB4]/40',
    info: 'bg-[#6E96AD]/15 text-[#385e75] dark:text-[#a0c5dc] border border-[#6E96AD]/30',
    warning: 'bg-[#D19A4C]/15 text-[#8f5e1b] dark:text-[#f0be78] border border-[#D19A4C]/30',
    critical: 'bg-[#B96359]/15 text-[#8b382e] dark:text-[#e09188] border border-[#B96359]/30',
    neutral: 'bg-black/5 dark:bg-white/5 text-[#676B68] dark:text-[#969D96] border border-[#D9D8D2] dark:border-[#2D322E]',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full whitespace-nowrap select-none shrink-0 ${sizeStyles[size] || sizeStyles.sm} ${variantStyles[variant] || variantStyles.neutral} ${className}`}
      {...props}
    >
      {Icon && <Icon className="w-3 h-3 shrink-0" />}
      {children}
    </span>
  );
};
