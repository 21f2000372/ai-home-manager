export type AuthAdapter = {
  getAccessToken: () => Promise<string | null>;
};

export const cookieSessionAuth: AuthAdapter = {
  async getAccessToken() {
    return null;
  },
};