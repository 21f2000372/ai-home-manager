import { OverviewDashboard } from './overview-dashboard';
import { WorkspaceHeader } from './workspace-header';

type WorkspacePageProps = { label: string; eyebrow: string };

export function WorkspacePage({ label, eyebrow }: WorkspacePageProps) {
  const isOverview = label === 'Overview';
  return <section className="space-y-8"><WorkspaceHeader label={label} eyebrow={eyebrow} />{isOverview ? <OverviewDashboard /> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">{label} workspace is ready for its feature module.</div>}</section>;
}