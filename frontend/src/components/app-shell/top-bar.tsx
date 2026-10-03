import { LogOut, Menu, Moon, Sun, Type } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useShellStore } from '@/stores/shell-store';
import { useSessionStore } from '@/stores/session-store';
import { NotificationMenu } from './notification-menu';

export function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { theme, toggleTheme, cycleFontScale } = useShellStore();
  const user = useSessionStore((state) => state.user);
  const clearSession = useSessionStore((state) => state.clear);
  const navigate = useNavigate();
  const initials = (user?.name ?? 'HomeOps').split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase();

  function signOut() {
    clearSession();
    navigate('/', { replace: true });
  }

  return (
    <header className="flex min-h-20 items-center justify-between border-b border-[var(--line)] bg-[var(--surface)]/85 px-4 backdrop-blur sm:px-6 lg:px-10">
      <button
        className="rounded-xl p-2 text-[var(--ink)] hover:bg-[var(--surface-muted)] lg:hidden"
        aria-label="Open navigation"
        onClick={onOpenMenu}
      >
        <Menu size={22} />
      </button>
      <div className="hidden lg:block">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#D19A4C]">Household dashboard</p>
        <p className="mt-1 font-display text-lg font-semibold text-[var(--ink)]">
          Good morning{user?.name ? `, ${user.name}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-1 sm:gap-2">
        <button
          className="rounded-xl p-2 text-[var(--muted)] hover:bg-[var(--surface-muted)]"
          aria-label="Adjust text size"
          title="Adjust text size"
          onClick={cycleFontScale}
        >
          <Type size={18} />
        </button>
        <button
          className="rounded-xl p-2 text-[var(--muted)] hover:bg-[var(--surface-muted)]"
          aria-label={theme === 'light' ? 'Use dark theme' : 'Use light theme'}
          title="Toggle theme"
          onClick={toggleTheme}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        {/* Dynamic Notification Bell with Dropdown */}
        <NotificationMenu />

        <button
          className="hidden rounded-xl p-2 text-[var(--muted)] hover:bg-[var(--surface-muted)] sm:inline-flex"
          aria-label="Sign out"
          title="Sign out"
          onClick={signOut}
        >
          <LogOut size={18} />
        </button>
        <div title={user?.role} className="grid size-9 place-items-center rounded-full bg-[#E4F0E8] text-sm font-bold text-[#3D5F4E]">
          {initials}
        </div>
      </div>
    </header>
  );
}