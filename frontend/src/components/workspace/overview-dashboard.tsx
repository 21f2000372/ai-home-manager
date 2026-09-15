import { CheckCircle2, CircleAlert, Clock3 } from 'lucide-react';
import { MetricCard } from './metric-card';
import { TodayActivity } from './today-activity';

export function OverviewDashboard() {
  return <div className="space-y-8"><div className="grid gap-4 md:grid-cols-3"><MetricCard icon={<CheckCircle2 />} value="12" label="Tasks on track" tone="green" /><MetricCard icon={<Clock3 />} value="4" label="Due today" tone="blue" /><MetricCard icon={<CircleAlert />} value="2" label="Need attention" tone="orange" /></div><div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]"><div className="rounded-2xl bg-[#dcefeb] p-7"><p className="text-sm font-semibold text-[#27736d]">Hearthwise insight</p><h2 className="mt-3 max-w-md text-2xl font-semibold leading-tight text-[#102a43]">Your week is looking balanced. The pantry is the only thing running low.</h2><p className="mt-3 max-w-md text-sm leading-6 text-[#37615e]">Two staples are below their household threshold. Add them to the next grocery run?</p><button className="mt-6 rounded-lg bg-[#27736d] px-4 py-2.5 text-sm font-semibold text-white">Review grocery list</button></div><TodayActivity /></div></div>;
}