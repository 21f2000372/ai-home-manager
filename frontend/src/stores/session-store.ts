import { create } from 'zustand';

type SessionState = {
  userId: string | null;
  status: 'unknown' | 'authenticated' | 'unauthenticated' | 'refreshing';
  setAuthenticated: (userId: string) => void;
  clear: () => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  userId: 'demo-user',
  status: 'authenticated',
  setAuthenticated: (userId) => set({ userId, status: 'authenticated' }),
  clear: () => set({ userId: null, status: 'unauthenticated' }),
}));