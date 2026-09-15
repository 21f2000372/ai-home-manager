import { Outlet, useParams } from 'react-router-dom';
import { useShellStore } from '@/stores/shell-store';
import { Sidebar } from './sidebar';
import { TopBar } from './top-bar';

export function AppShell() {
  const { tenantId = 'home-lakeview' } = useParams();
  const { isMobileNavOpen, toggleMobileNav, closeMobileNav } = useShellStore();
  return <div className="min-h-screen bg-[#f4f7f9] text-[#102a43]"><Sidebar tenantId={tenantId} isOpen={isMobileNavOpen} onClose={closeMobileNav} />{isMobileNavOpen && <button aria-label="Close navigation overlay" className="fixed inset-0 z-20 bg-[#102a43]/40 lg:hidden" onClick={closeMobileNav} />}<main className="lg:pl-72"><TopBar onOpenMenu={toggleMobileNav} /><div className="mx-auto max-w-7xl px-5 py-8 lg:px-10"><Outlet /></div></main></div>;
}