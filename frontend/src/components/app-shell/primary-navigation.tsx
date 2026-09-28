import { NavLink } from 'react-router-dom';
import { navigationItemsForRole } from './navigation';
import { useSessionStore } from '@/stores/session-store';

export function PrimaryNavigation({ tenantId, onNavigate }: { tenantId: string; onNavigate: () => void }) {
  const role = useSessionStore((state) => state.user?.role);
  const items = navigationItemsForRole(role);
  return <nav className="mt-8 flex-1 space-y-1">{items.map(({ to, label, icon: Icon }) => <NavLink key={to} to={`/t/${tenantId}/${to}`} onClick={onNavigate} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-[#5E9278] text-white shadow-sm' : 'text-[#D2E6D8] hover:bg-white/10 hover:text-white'}`}><Icon size={18} strokeWidth={1.8} />{label}</NavLink>)}</nav>;
}
