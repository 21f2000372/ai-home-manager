import React from 'react';

/**
 * Reusable Button component styled with HomeOps palette tokens
 */
export const Button = ({
  children,
  variant = 'primary', // 'primary', 'secondary', 'ghost', 'danger', 'subtle'
  size = 'md',        // 'sm', 'md', 'lg'
  className = '',
  disabled = false,
  onClick,
  type = 'button',
  icon: Icon,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5E9278]/50 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-[#101210] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none select-none';

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 min-h-[36px]',
    md: 'text-xs sm:text-sm px-4 py-2 min-h-[40px]',
    lg: 'text-sm px-5 py-2.5 min-h-[44px]',
  };

  const variantStyles = {
    primary: 'bg-[#5E9278] hover:bg-[#4D7A64] text-white shadow-xs focus-visible:ring-[#5E9278]',
    secondary: 'bg-[#FAF9F6] dark:bg-[#181B18] text-[#171918] dark:text-[#EFF1EC] border border-[#D9D8D2] dark:border-[#2D322E] hover:bg-[#EBE8E1] dark:hover:bg-[#222723] hover:border-[#5E9278]/60 focus-visible:ring-[#5E9278]',
    ghost: 'bg-transparent text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5',
    subtle: 'bg-[#5E9278]/10 text-[#3d6551] hover:bg-[#5E9278]/20 dark:text-[#9BCDB4] dark:bg-[#9BCDB4]/15 dark:hover:bg-[#9BCDB4]/25',
    danger: 'bg-[#B96359] hover:bg-[#a35249] text-white focus-visible:ring-[#B96359]',
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${baseStyles} ${sizeStyles[size] || sizeStyles.md} ${variantStyles[variant] || variantStyles.primary} ${className}`}
      {...props}
    >
      {Icon && <Icon className="w-4 h-4 shrink-0" />}
      {children}
    </button>
  );
};
