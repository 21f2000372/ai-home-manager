import { create } from 'zustand';

type ShellState = { isMobileNavOpen: boolean; toggleMobileNav: () => void; closeMobileNav: () => void };

export const useShellStore = create<ShellState>((set) => ({
  isMobileNavOpen: false,
  toggleMobileNav: () => set((state) => ({ isMobileNavOpen: !state.isMobileNavOpen })),
  closeMobileNav: () => set({ isMobileNavOpen: false }),
}));