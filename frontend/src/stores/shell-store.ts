import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark';
type FontScale = 'compact' | 'default' | 'large';

type ShellState = {
  isMobileNavOpen: boolean;
  theme: Theme;
  fontScale: FontScale;
  toggleMobileNav: () => void;
  closeMobileNav: () => void;
  toggleTheme: () => void;
  cycleFontScale: () => void;
};

export const useShellStore = create<ShellState>()(persist((set) => ({
  isMobileNavOpen: false,
  theme: 'light',
  fontScale: 'default',
  toggleMobileNav: () => set((state) => ({ isMobileNavOpen: !state.isMobileNavOpen })),
  closeMobileNav: () => set({ isMobileNavOpen: false }),
  toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
  cycleFontScale: () => set((state) => ({
    fontScale: state.fontScale === 'compact' ? 'default' : state.fontScale === 'default' ? 'large' : 'compact',
  })),
}), { name: 'homeops-shell' }));