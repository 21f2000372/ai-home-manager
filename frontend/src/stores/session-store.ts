import { create } from 'zustand';
import { clearAccessToken, hasAccessToken } from '@/lib/auth/auth-adapter';

export type SessionUser = {
  id: string;
  email: string;
  name?: string;
  role: 'Admin' | 'Adult' | 'Child' | 'Guest';
};

type SessionState = {
  user: SessionUser | null;
  status: 'unknown' | 'authenticated' | 'unauthenticated' | 'refreshing';
  setAuthenticated: (user: SessionUser) => void;
  clear: () => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  status: hasAccessToken() ? 'authenticated' : 'unauthenticated',
  setAuthenticated: (user) => set({ user, status: 'authenticated' }),
  clear: () => {
    clearAccessToken();
    set({ user: null, status: 'unauthenticated' });
  },
}));
