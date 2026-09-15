import { Settings } from 'lucide-react';

export function SidebarFooter() {
  return <div className="border-t border-white/10 pt-4"><button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:bg-white/10 hover:text-white"><Settings size={18} />Settings</button><div className="mt-4 flex items-center gap-3 px-3"><div className="grid size-9 place-items-center rounded-full bg-[#b8d8d8] font-semibold text-[#102a43]">AM</div><div><p className="text-sm font-semibold text-white">Alex Morgan</p><p className="text-xs text-slate-400">Admin</p></div></div></div>;
}