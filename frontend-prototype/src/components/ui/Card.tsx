import React from 'react';

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  elevated?: boolean;
};

/**
 * Reusable Card component matching the HomeOps surface and border system
 */
export const Card = ({
  children,
  className = '',
  elevated = false,
  onClick,
  ...props
}: CardProps) => {
  const isClickable = !!onClick;

  const handleKeyDown = (e) => {
    if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick(e);
    }
  };

  return (
    <div
      onClick={onClick}
      onKeyDown={handleKeyDown}
      tabIndex={isClickable ? 0 : undefined}
      role={isClickable ? 'button' : undefined}
      className={`rounded-2xl border transition-all duration-150 ${
        elevated
          ? 'bg-[#FFFFFF] dark:bg-[#222622] border-[#D9D8D2] dark:border-[#2D322E] shadow-soft dark:shadow-soft-dark'
          : 'bg-[#FAF9F6] dark:bg-[#181B18] border-[#D9D8D2] dark:border-[#2D322E]'
      } ${
        isClickable
          ? 'cursor-pointer hover:border-[#5E9278] hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5E9278]/40 active:scale-[0.99]'
          : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
