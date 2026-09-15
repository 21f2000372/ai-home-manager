import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

export function TenantSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  return <div className="relative mt-10"><button onClick={() => setIsOpen((open) => !open)} className="flex w-full items-center justify-between rounded-xl bg-white/10 px-3 py-3 text-left hover:bg-white/15"><span><span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Active household</span><span className="mt-1 block font-semibold text-white">Lakeview home</span></span><ChevronDown size={17} /></button>{isOpen && <div className="absolute left-0 right-0 top-16 z-10 rounded-xl border border-slate-200 bg-white p-2 text-sm text-[#102a43] shadow-xl"><button className="w-full rounded-lg px-3 py-2 text-left font-medium hover:bg-slate-100">Lakeview home</button><button className="w-full rounded-lg px-3 py-2 text-left text-slate-500 hover:bg-slate-100">Add household</button></div>}</div>;
}