import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireSession } from '@/app/require-session';
import { AppShell } from '@/components/app-shell/app-shell';
import { WorkspacePage } from '@/components/workspace/workspace-page';
import { AuthScreen } from '@/features/auth/auth-screen';
import { JoinHouseholdScreen } from '@/features/auth/join-household-screen';

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

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<AuthScreen />} />
      <Route path="/join" element={<JoinHouseholdScreen />} />
      <Route element={<RequireSession />}>
        <Route path="/t/:tenantId" element={<AppShell />}>
          <Route index element={<Navigate to="overview" replace />} />
          {workspaceRoutes.map((route) => (
            <Route key={route.path} path={route.path} element={<WorkspacePage {...route} />} />
          ))}
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
