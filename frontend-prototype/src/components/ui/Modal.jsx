import React, { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * Reusable minimal Modal dialog
 */
export const Modal = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  maxWidth = 'max-w-md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'auto';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div 
        className="fixed inset-0" 
        onClick={onClose} 
      />
      <div className={`relative w-full ${maxWidth} bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] rounded-2xl shadow-elevated dark:shadow-elevated-dark overflow-hidden z-10 flex flex-col max-h-[90vh]`}>
        <div className="flex items-start justify-between p-5 border-b border-[#D9D8D2] dark:border-[#2D322E]">
          <div>
            {title && <h3 className="text-base font-semibold text-[#171918] dark:text-[#EFF1EC]">{title}</h3>}
            {subtitle && <p className="text-xs text-[#676B68] dark:text-[#969D96] mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="min-h-[44px] min-w-[44px] -mr-2 -mt-2 flex items-center justify-center rounded-xl text-[#676B68] hover:text-[#171918] dark:text-[#969D96] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5E9278]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
};
