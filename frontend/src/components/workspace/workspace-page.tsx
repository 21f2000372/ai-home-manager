import { OverviewDashboard } from './overview-dashboard';
import { WorkspaceHeader } from './workspace-header';
import { DomainWorkspace } from './domain-workspace';

type WorkspacePageProps = { label: string; eyebrow: string };

export function WorkspacePage({ label, eyebrow }: WorkspacePageProps) {
  const isOverview = label === 'Overview';
  if (isOverview) return <section className="space-y-5"><WorkspaceHeader label={label} eyebrow={eyebrow} compact /><OverviewDashboard /></section>;
  return <DomainWorkspace kind={label.toLowerCase().replace('ai assistant', 'chat') as 'people' | 'plan' | 'inventory' | 'grocery' | 'finance' | 'maintenance' | 'documents' | 'chat'} />;
}
