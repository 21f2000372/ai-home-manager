export type AuthAdapter = {
  getAccessToken: () => Promise<string | null>;
};

export type StoredSessionUser = {
  id: string;
  email: string;
  name?: string;
  role: 'Admin' | 'Adult' | 'Child' | 'Guest';
};

const accessTokenKey = 'homeops.access-token';
const sessionUserKey = 'homeops.session-user';
const householdRoles: StoredSessionUser['role'][] = ['Admin', 'Adult', 'Child', 'Guest'];

export const cookieSessionAuth: AuthAdapter = {
  async getAccessToken() {
    return window.sessionStorage.getItem(accessTokenKey);
  },
};

export function setAccessToken(token: string) {
  window.sessionStorage.setItem(accessTokenKey, token);
}

export function getStoredSessionUser(): StoredSessionUser | null {
  const rawUser = window.sessionStorage.getItem(sessionUserKey);
  if (!rawUser) return null;

  try {
    const user = JSON.parse(rawUser) as Partial<StoredSessionUser>;
    if (typeof user.id !== 'string' || typeof user.email !== 'string' || !householdRoles.includes(user.role as StoredSessionUser['role'])) return null;
    return { id: user.id, email: user.email, name: typeof user.name === 'string' ? user.name : undefined, role: user.role as StoredSessionUser['role'] };
  } catch {
    return null;
  }
}

export function setStoredSessionUser(user: StoredSessionUser) {
  window.sessionStorage.setItem(sessionUserKey, JSON.stringify(user));
}

export function clearAccessToken() {
  window.sessionStorage.removeItem(accessTokenKey);
  window.sessionStorage.removeItem(sessionUserKey);
}

export function hasAccessToken() {
  return Boolean(window.sessionStorage.getItem(accessTokenKey));
}

export function hasAuthenticatedSession() {
  return hasAccessToken() && Boolean(getStoredSessionUser());
}
