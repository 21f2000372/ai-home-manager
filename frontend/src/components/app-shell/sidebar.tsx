import { Brand } from './brand';
import { PrimaryNavigation } from './primary-navigation';
import { SidebarFooter } from './sidebar-footer';
import { TenantSwitcher } from './tenant-switcher';

export function Sidebar({ tenantId, isOpen, onClose }: { tenantId: string; isOpen: boolean; onClose: () => void }) {
  return <aside className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col bg-[#102a43] px-5 py-6 text-slate-200 transition-transform lg:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}><Brand onClose={onClose} /><TenantSwitcher /><PrimaryNavigation tenantId={tenantId} onNavigate={onClose} /><SidebarFooter /></aside>;
}