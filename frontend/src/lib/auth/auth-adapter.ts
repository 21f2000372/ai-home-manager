export type AuthAdapter = {
  getAccessToken: () => Promise<string | null>;
};

const accessTokenKey = 'homeops.access-token';

export const cookieSessionAuth: AuthAdapter = {
  async getAccessToken() {
    return window.sessionStorage.getItem(accessTokenKey);
  },
};

export function setAccessToken(token: string) {
  window.sessionStorage.setItem(accessTokenKey, token);
}

export function clearAccessToken() {
  window.sessionStorage.removeItem(accessTokenKey);
}

export function hasAccessToken() {
  return Boolean(window.sessionStorage.getItem(accessTokenKey));
}
