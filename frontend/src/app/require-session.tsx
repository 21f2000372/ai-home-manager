import { Navigate, Outlet } from 'react-router-dom';
import { hasAccessToken } from '@/lib/auth/auth-adapter';

export function RequireSession() {
  return hasAccessToken() ? <Outlet /> : <Navigate to="/" replace />;
}
