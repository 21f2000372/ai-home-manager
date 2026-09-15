import { NavLink } from 'react-router-dom';
import { navigationItems } from './navigation';

export function PrimaryNavigation({ tenantId, onNavigate }: { tenantId: string; onNavigate: () => void }) {
  return <nav className="mt-8 flex-1 space-y-1">{navigationItems.map(({ to, label, icon: Icon }) => <NavLink key={to} to={`/t/${tenantId}/${to}`} onClick={onNavigate} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-[#ef8354] text-white' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}><Icon size={18} strokeWidth={1.8} />{label}</NavLink>)}</nav>;
}