import { Navigate, Outlet } from 'react-router-dom';
import { hasAuthenticatedSession } from '@/lib/auth/auth-adapter';

export function RequireSession() {
  return hasAuthenticatedSession() ? <Outlet /> : <Navigate to="/" replace />;
}
