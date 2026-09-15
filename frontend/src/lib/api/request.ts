import { cookieSessionAuth, type AuthAdapter } from '@/lib/auth/auth-adapter';

export type RequestContext = {
  tenantId?: string;
  correlationId: string;
  idempotencyKey?: string;
  auth?: AuthAdapter;
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(path: string, init: RequestInit = {}, context: RequestContext): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  headers.set('X-Correlation-Id', context.correlationId);
  if (context.tenantId) headers.set('X-Tenant-Id', context.tenantId);
  if (context.idempotencyKey) headers.set('Idempotency-Key', context.idempotencyKey);
  const accessToken = await (context.auth ?? cookieSessionAuth).getAccessToken();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) throw new ApiError(response.status, `Request failed with status ${response.status}`);
  return response.json() as Promise<T>;
}