import React from 'react';
import type { LucideIcon } from 'lucide-react';

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: LucideIcon;
  error?: React.ReactNode;
};

/**
 * Reusable Input component matching the architectural surface styling
 */
export const Input = ({
  className = '',
  icon: Icon,
  error,
  ...props
}: InputProps) => {
  return (
    <div className="relative w-full">
      {Icon && (
        <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#676B68] dark:text-[#969D96] pointer-events-none">
          <Icon className="w-4 h-4" />
        </div>
      )}
      <input
        className={`w-full rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border text-[#171918] dark:text-[#EFF1EC] placeholder-[#676B68]/70 dark:placeholder-[#969D96]/60 text-xs sm:text-sm transition-colors outline-none focus:ring-2 focus:ring-[#5E9278]/40 focus:border-[#5E9278] min-h-[40px] ${
          Icon ? 'pl-10 pr-4 py-2' : 'px-3.5 py-2'
        } ${
          error
            ? 'border-[#B96359] focus:border-[#B96359] focus:ring-[#B96359]/30'
            : 'border-[#D9D8D2] dark:border-[#2D322E]'
        } ${className}`}
        {...props}
      />
      {error && <p className="text-[11px] text-[#B96359] mt-1">{error}</p>}
    </div>
  );
};
