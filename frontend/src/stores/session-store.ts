import { create } from 'zustand';
import { clearAccessToken, getStoredSessionUser, hasAuthenticatedSession, setStoredSessionUser, type StoredSessionUser } from '@/lib/auth/auth-adapter';

export type SessionUser = StoredSessionUser;

type SessionState = {
  user: SessionUser | null;
  status: 'unknown' | 'authenticated' | 'unauthenticated' | 'refreshing';
  setAuthenticated: (user: SessionUser) => void;
  clear: () => void;
};

const restoredUser = getStoredSessionUser();

export const useSessionStore = create<SessionState>((set) => ({
  user: restoredUser,
  status: hasAuthenticatedSession() ? 'authenticated' : 'unauthenticated',
  setAuthenticated: (user) => {
    setStoredSessionUser(user);
    set({ user, status: 'authenticated' });
  },
  clear: () => {
    clearAccessToken();
    set({ user: null, status: 'unauthenticated' });
  },
}));
