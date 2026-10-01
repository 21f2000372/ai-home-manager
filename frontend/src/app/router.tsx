import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { RequireSession } from '@/app/require-session';
import { AppShell } from '@/components/app-shell/app-shell';
import { WorkspacePage } from '@/components/workspace/workspace-page';
import { AuthScreen } from '@/features/auth/auth-screen';
import { JoinHouseholdScreen } from '@/features/auth/join-household-screen';
import { GuestDashboardWorkspace } from '@/features/guest-dashboard';
import { useSessionStore } from '@/stores/session-store';

const workspaceRoutes = [
  { path: 'overview', label: 'Overview', eyebrow: 'Household pulse' },
  { path: 'people', label: 'People', eyebrow: 'People & permissions' },
  { path: 'plan', label: 'Plan', eyebrow: 'Tasks & schedule' },
  { path: 'tasks', label: 'Plan', eyebrow: 'Tasks & schedule' },
  { path: 'calendar', label: 'Plan', eyebrow: 'Tasks & schedule' },
  { path: 'inventory', label: 'Inventory', eyebrow: 'Food & inventory' },
  { path: 'grocery', label: 'Grocery', eyebrow: 'Food & inventory' },
  { path: 'finance', label: 'Finance', eyebrow: 'Finance & budget' },
  { path: 'maintenance', label: 'Maintenance', eyebrow: 'Home maintenance' },
  { path: 'documents', label: 'Documents', eyebrow: 'Household records' },
  { path: 'chat', label: 'AI assistant', eyebrow: 'Conversation workspace' },
];

/** Landing route inside a tenant: guests go to their dashboard, others to overview. */
function TenantIndexRedirect() {
  const role = useSessionStore((state) => state.user?.role);
  return <Navigate to={role === 'Guest' ? 'dashboard' : 'overview'} replace />;
}

/** Blocks Guests from non-dashboard workspace routes. */
function GuestGuardedRoute({ children }: { children: ReactNode }) {
  const role = useSessionStore((state) => state.user?.role);
  const { tenantId } = useParams();
  if (role === 'Guest') return <Navigate to={`/t/${tenantId}/dashboard`} replace />;
  return <>{children}</>;
}

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<AuthScreen />} />
      <Route path="/join" element={<JoinHouseholdScreen />} />
      <Route element={<RequireSession />}>
        <Route path="/t/:tenantId" element={<AppShell />}>
          <Route index element={<TenantIndexRedirect />} />
          <Route path="dashboard" element={<GuestDashboardWorkspace />} />
          {workspaceRoutes.map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={<GuestGuardedRoute><WorkspacePage {...route} /></GuestGuardedRoute>}
            />
          ))}
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
