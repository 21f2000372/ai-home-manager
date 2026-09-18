import { Sparkles, X } from 'lucide-react';

export function Brand({ onClose }: { onClose: () => void }) {
  return <div className="flex items-center justify-between px-3"><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-xl bg-[#5E9278] text-white shadow-lg shadow-black/20"><Sparkles size={20} /></div><div><p className="font-display text-lg font-semibold text-white">HomeOps</p><p className="text-xs text-[#C8DCCF]">Household coordinator</p></div></div><button className="lg:hidden" aria-label="Close navigation" onClick={onClose}><X size={20} /></button></div>;
}
