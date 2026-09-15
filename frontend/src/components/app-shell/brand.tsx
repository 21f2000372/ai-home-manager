import { Sparkles, X } from 'lucide-react';

export function Brand({ onClose }: { onClose: () => void }) {
  return <div className="flex items-center justify-between px-3"><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-xl bg-[#ef8354] text-white"><Sparkles size={20} /></div><div><p className="font-display text-lg font-semibold text-white">Hearthwise</p><p className="text-xs text-slate-400">Your home, in rhythm</p></div></div><button className="lg:hidden" aria-label="Close navigation" onClick={onClose}><X size={20} /></button></div>;
}