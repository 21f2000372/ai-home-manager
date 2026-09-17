import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export const ToastContainer = () => {
  const { toasts, removeToast } = useHousehold();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4 sm:px-0">
      {toasts.map((toast) => {
        const isSuccess = toast.type === 'success';
        const isError = toast.type === 'error';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-2xl border shadow-elevated dark:shadow-elevated-dark backdrop-blur-md animate-fade-in bg-[#FAF9F6] dark:bg-[#181B18] ${
              isSuccess
                ? 'border-[#5E9278]/50'
                : isError
                ? 'border-[#B96359]/50'
                : 'border-[#D9D8D2] dark:border-[#2D322E]'
            }`}
          >
            <div className="mt-0.5 shrink-0">
              {isSuccess && <CheckCircle2 className="w-4 h-4 text-[#5E9278]" />}
              {isError && <AlertCircle className="w-4 h-4 text-[#B96359]" />}
              {!isSuccess && !isError && <Info className="w-4 h-4 text-[#6E96AD]" />}
            </div>

            <div className="flex-1 min-w-0">
              {toast.title && (
                <h4 className="font-semibold text-xs text-[#171918] dark:text-[#EFF1EC]">
                  {toast.title}
                </h4>
              )}
              <p className="text-xs text-[#676B68] dark:text-[#969D96] mt-0.5 leading-snug">
                {toast.message}
              </p>
            </div>

            <button
              onClick={() => removeToast(toast.id)}
              className="text-[#676B68] hover:text-[#171918] dark:text-[#969D96] dark:hover:text-[#EFF1EC] p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
