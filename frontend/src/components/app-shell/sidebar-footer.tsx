import { Settings } from 'lucide-react';
import { useSessionStore } from '@/stores/session-store';

export function SidebarFooter() {
  const user = useSessionStore((state) => state.user);
  const name = user?.name ?? 'Household member';
  const initials = name.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase();
  return <div className="border-t border-white/10 pt-4"><button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[#D2E6D8] hover:bg-white/10 hover:text-white"><Settings size={18} />Settings</button><div className="mt-4 flex items-center gap-3 px-3"><div className="grid size-9 place-items-center rounded-full bg-[#E4F0E8] font-bold text-[#3D5F4E]">{initials}</div><div><p className="text-sm font-semibold text-white">{name}</p><p className="text-xs text-[#C8DCCF]">{user?.role ?? 'Signed in'}</p></div></div></div>;
}
