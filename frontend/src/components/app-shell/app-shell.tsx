import { Outlet, useParams } from 'react-router-dom';
import { useShellStore } from '@/stores/shell-store';
import { Sidebar } from './sidebar';
import { TopBar } from './top-bar';

export function AppShell() {
  const { tenantId = 'home-lakeview' } = useParams();
  const { isMobileNavOpen, theme, fontScale, toggleMobileNav, closeMobileNav } = useShellStore();
  return <div className="app-root" data-theme={theme} data-font-scale={fontScale}><Sidebar tenantId={tenantId} isOpen={isMobileNavOpen} onClose={closeMobileNav} />{isMobileNavOpen && <button aria-label="Close navigation overlay" className="fixed inset-0 z-20 bg-[#17233d]/50 lg:hidden" onClick={closeMobileNav} />}<main className="lg:pl-72"><TopBar onOpenMenu={toggleMobileNav} /><div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-10 lg:py-9"><Outlet /></div></main></div>;
}