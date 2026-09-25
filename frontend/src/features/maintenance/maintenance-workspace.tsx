import { FormEvent, useMemo, useState } from 'react';
import { ChevronDown, LoaderCircle, Pencil, Plus, Trash2, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { HouseholdChat } from '@/components/ai/household-chat';
import { ApiError } from '@/lib/api/request';
import { useSessionStore } from '@/stores/session-store';
import {
  createAppliance,
  deleteAppliance,
  deleteIssue,
  deleteRepair,
  getAppliances,
  getExpiringWarranties,
  getHouseholdMembers,
  getIssues,
  getRepairs,
  logRepair,
  reportIssue,
  updateAppliance,
  updateIssue,
  type Appliance,
  type CreateApplianceInput,
  type CreateIssueInput,
  type HouseholdMember,
  type IssueStatus,
  type LogRepairInput,
  type MaintenanceIssue,
  type MaintenancePriority,
  type Repair,
} from './maintenance-api';
import {
  buildMaintenanceSummary,
  costMajorToMinor,
  formatCost,
  formatWarrantyDate,
  getNextIssueStatus,
  toDateInputValue,
  warrantyTone,
} from './maintenance-utils';

const appliancesKey = ['household', 'maintenance', 'appliances'] as const;
const expiringKey = (days: number) => ['household', 'maintenance', 'expiring', days] as const;
const issuesKey = (status: string, applianceId: string) => ['household', 'maintenance', 'issues', status, applianceId] as const;
const repairsKey = (applianceId: string) => ['household', 'maintenance', 'repairs', applianceId] as const;
const membersKey = ['household', 'members'] as const;

const ISSUE_STATUSES: IssueStatus[] = ['Open', 'InProgress', 'Resolved', 'Closed'];
const PRIORITIES: MaintenancePriority[] = ['Low', 'Normal', 'High'];

function issueTone(status: IssueStatus) {
  if (status === 'Open') return 'bg-[#F6EADB] text-[#8A5D2F]';
  if (status === 'InProgress') return 'bg-[#E3EDF8] text-[#346B8E]';
  if (status === 'Resolved') return 'bg-[#E4F0E8] text-[#3D5F4E]';
  return 'bg-[#ECEAE4] text-[#676B68]';
}

function priorityTone(priority: MaintenancePriority) {
  if (priority === 'High') return 'bg-[#F6EADB] text-[#8A5D2F]';
  if (priority === 'Low') return 'bg-[#E4F0E8] text-[#3D5F4E]';
  return 'bg-[#ECEAE4] text-[#676B68]';
}

function expiryTone(daysRemaining: number) {
  const tone = warrantyTone(daysRemaining);
  if (tone === 'urgent') return 'bg-[#B96359]/15 text-[#8B3F36]';
  if (tone === 'watch') return 'bg-[#F6EADB] text-[#8A5D2F]';
  return 'bg-[#E4F0E8] text-[#3D5F4E]';
}

const emptyApplianceForm: CreateApplianceInput = { name: '', brand: '', model: '', purchased_at: '', warranty_ends_at: '' };
const emptyIssueForm = { description: '', priority: 'Normal' as MaintenancePriority, appliance_id: '', accountable_to: '' };
const emptyRepairForm = { serviced_at: '', appliance_id: '', provider: '', costMajor: '', currency: 'USD', notes: '' };

export function MaintenanceWorkspace() {
  const queryClient = useQueryClient();
  const role = useSessionStore((state) => state.user?.role);
  const canManageAppliances = role === 'Adult' || role === 'Admin';
  const canWriteIssues = role === 'Adult' || role === 'Admin' || role === 'Child';
  const canViewRepairs = role === 'Adult' || role === 'Admin';

  const [expiringDays, setExpiringDays] = useState(30);
  const [issueStatus, setIssueStatus] = useState<IssueStatus | 'All'>('All');
  const [issueAppliance, setIssueAppliance] = useState('');
  const [repairAppliance, setRepairAppliance] = useState('');

  const [applianceComposerOpen, setApplianceComposerOpen] = useState(false);
  const [editingApplianceId, setEditingApplianceId] = useState<string | null>(null);
  const [applianceForm, setApplianceForm] = useState<CreateApplianceInput>(emptyApplianceForm);

  const [issueComposerOpen, setIssueComposerOpen] = useState(false);
  const [editingIssueId, setEditingIssueId] = useState<string | null>(null);
  const [editingIssueStatus, setEditingIssueStatus] = useState<IssueStatus>('Open');
  const [issueForm, setIssueForm] = useState(emptyIssueForm);

  const [repairComposerOpen, setRepairComposerOpen] = useState(false);
  const [repairForm, setRepairForm] = useState(emptyRepairForm);

  const appliancesQuery = useQuery({ queryKey: appliancesKey, queryFn: getAppliances });
  const expiringQuery = useQuery({ queryKey: expiringKey(expiringDays), queryFn: () => getExpiringWarranties(expiringDays) });
  const issuesQuery = useQuery({
    queryKey: issuesKey(issueStatus, issueAppliance),
    queryFn: () => getIssues({ status: issueStatus, appliance_id: issueAppliance || undefined }),
  });
  const repairsQuery = useQuery({
    queryKey: repairsKey(repairAppliance),
    queryFn: () => getRepairs(repairAppliance || undefined),
    enabled: canViewRepairs,
  });
  const membersQuery = useQuery({ queryKey: membersKey, queryFn: getHouseholdMembers });

  const appliances = useMemo(() => appliancesQuery.data ?? [], [appliancesQuery.data]);
  const applianceName = useMemo(() => {
    const lookup = new Map(appliances.map((item) => [item.appliance_id, item.name]));
    return (id: string | null) => (id ? (lookup.get(id) ?? 'Unknown appliance') : null);
  }, [appliances]);

  async function invalidateMaintenance() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['household', 'maintenance'] }),
    ]);
  }

  const createApplianceMutation = useMutation({
    mutationFn: createAppliance,
    onSuccess: async () => {
      await invalidateMaintenance();
      setApplianceForm(emptyApplianceForm);
      setApplianceComposerOpen(false);
    },
  });
  const updateApplianceMutation = useMutation({
    mutationFn: ({ applianceId, input }: { applianceId: string; input: CreateApplianceInput }) => updateAppliance(applianceId, input),
    onSuccess: async () => {
      await invalidateMaintenance();
      setApplianceForm(emptyApplianceForm);
      setEditingApplianceId(null);
      setApplianceComposerOpen(false);
    },
  });
  const deleteApplianceMutation = useMutation({
    mutationFn: deleteAppliance,
    onSuccess: async () => {
      await invalidateMaintenance();
    },
  });

  const reportIssueMutation = useMutation({
    mutationFn: (input: CreateIssueInput) => reportIssue(input),
    onSuccess: async () => {
      await invalidateMaintenance();
      setIssueForm(emptyIssueForm);
      setIssueComposerOpen(false);
    },
  });
  const updateIssueMutation = useMutation({
    mutationFn: ({ issueId, status, description, priority, accountableTo }: { issueId: string; status?: IssueStatus; description?: string; priority?: MaintenancePriority; accountableTo?: string | null }) =>
      updateIssue(issueId, { status, description, priority, accountable_to: accountableTo }),
    onSuccess: async () => {
      await invalidateMaintenance();
      setIssueForm(emptyIssueForm);
      setEditingIssueId(null);
      setIssueComposerOpen(false);
    },
  });
  const deleteIssueMutation = useMutation({
    mutationFn: deleteIssue,
    onSuccess: async () => {
      await invalidateMaintenance();
    },
  });

  const logRepairMutation = useMutation({
    mutationFn: (input: LogRepairInput) => logRepair(input),
    onSuccess: async () => {
      await invalidateMaintenance();
      setRepairForm(emptyRepairForm);
      setRepairComposerOpen(false);
    },
  });
  const deleteRepairMutation = useMutation({
    mutationFn: deleteRepair,
    onSuccess: async () => {
      await invalidateMaintenance();
    },
  });

  const summary = useMemo(
    () => buildMaintenanceSummary(appliances, issuesQuery.data ?? [], expiringQuery.data ?? [], repairsQuery.data ?? []),
    [appliances, issuesQuery, expiringQuery, repairsQuery],
  );

  function submitAppliance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applianceForm.name.trim()) return;
    if (editingApplianceId) {
      updateApplianceMutation.mutate({ applianceId: editingApplianceId, input: applianceForm });
    } else {
      createApplianceMutation.mutate(applianceForm);
    }
  }

  function beginEditAppliance(item: Appliance) {
    setApplianceForm({
      name: item.name,
      brand: item.brand ?? '',
      model: item.model ?? '',
      purchased_at: toDateInputValue(item.purchased_at),
      warranty_ends_at: toDateInputValue(item.warranty_ends_at),
    });
    setEditingApplianceId(item.appliance_id);
    setApplianceComposerOpen(true);
  }

  function submitIssue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!issueForm.description.trim() && !editingIssueId) return;
    if (editingIssueId) {
      updateIssueMutation.mutate({
        issueId: editingIssueId,
        status: editingIssueStatus,
        description: issueForm.description.trim() || undefined,
        priority: issueForm.priority,
        accountableTo: issueForm.accountable_to || null,
      });
    } else {
      reportIssueMutation.mutate({
        description: issueForm.description,
        priority: issueForm.priority,
        appliance_id: issueForm.appliance_id || undefined,
        accountable_to: issueForm.accountable_to || undefined,
      });
    }
  }

  function beginEditIssue(issue: MaintenanceIssue) {
    setIssueForm({
      description: issue.description,
      priority: issue.priority,
      appliance_id: issue.appliance_id ?? '',
      accountable_to: issue.accountable_to ?? '',
    });
    setEditingIssueStatus(issue.status);
    setEditingIssueId(issue.issue_id);
    setIssueComposerOpen(true);
  }

  function submitRepair(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!repairForm.serviced_at) return;
    const costMinor = costMajorToMinor(repairForm.costMajor);
    if (repairForm.costMajor.trim() && costMinor === null) return;
    logRepairMutation.mutate({
      serviced_at: repairForm.serviced_at,
      appliance_id: repairForm.appliance_id || undefined,
      provider: repairForm.provider || undefined,
      cost_minor: costMinor,
      currency: repairForm.currency || 'USD',
      notes: repairForm.notes || undefined,
    });
  }

  const error =
    appliancesQuery.error ??
    expiringQuery.error ??
    issuesQuery.error ??
    repairsQuery.error ??
    membersQuery.error ??
    createApplianceMutation.error ??
    updateApplianceMutation.error ??
    deleteApplianceMutation.error ??
    reportIssueMutation.error ??
    updateIssueMutation.error ??
    deleteIssueMutation.error ??
    logRepairMutation.error ??
    deleteRepairMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not update maintenance. Please try again.' : null;

  const members = membersQuery.data ?? [];

  return (
    <section className="space-y-6">
      <div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Home maintenance</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Maintenance</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 muted">
            Track appliances and warranties, report household issues, and keep a repair history — live from the backend.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canManageAppliances && (
            <Button
              tone="neutral"
              onClick={() => {
                setApplianceComposerOpen((open) => !open);
                setEditingApplianceId(null);
                setApplianceForm(emptyApplianceForm);
              }}
            >
              {applianceComposerOpen ? <X size={16} /> : <Plus size={16} />}
              {applianceComposerOpen ? 'Close' : 'Add appliance'}
            </Button>
          )}
          {canWriteIssues && (
            <Button
              tone="neutral"
              onClick={() => {
                setIssueComposerOpen((open) => !open);
                setEditingIssueId(null);
                setIssueForm(emptyIssueForm);
              }}
            >
              {issueComposerOpen ? <X size={16} /> : <Plus size={16} />}
              {issueComposerOpen ? 'Close' : 'Report issue'}
            </Button>
          )}
          {canViewRepairs && (
            <Button
              onClick={() => {
                setRepairComposerOpen((open) => !open);
                setRepairForm(emptyRepairForm);
              }}
            >
              {repairComposerOpen ? <X size={16} /> : <Plus size={16} />}
              {repairComposerOpen ? 'Close' : 'Log repair'}
            </Button>
          )}
        </div>
      </div>

      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
      {!canWriteIssues && !canManageAppliances && (
        <p className="rounded-xl bg-[#ECEAE4] px-4 py-3 text-sm muted">Guest accounts have read-only access to maintenance.</p>
      )}

      <HouseholdChat
        title="Ask about maintenance"
        description="Ask about warranties, issues, or service history. The assistant will respond through the household agent."
        initialMessage="Ask about your home — for example, “Which warranties expire soon?”"
        onMessageProcessed={() => invalidateMaintenance()}
      />

      <div className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]">
        <div className="space-y-5">
          <AppliancesSection
            appliances={appliances}
            expiring={expiringQuery.data ?? []}
            expiringDays={expiringDays}
            onExpiringDaysChange={setExpiringDays}
            isLoading={appliancesQuery.isLoading || expiringQuery.isLoading}
            composerOpen={applianceComposerOpen && canManageAppliances}
            form={applianceForm}
            setForm={setApplianceForm}
            isEditing={Boolean(editingApplianceId)}
            isPending={createApplianceMutation.isPending || updateApplianceMutation.isPending}
            onSubmit={submitAppliance}
            onEdit={beginEditAppliance}
            onDelete={(id) => deleteApplianceMutation.mutate(id)}
            canManage={canManageAppliances}
          />

          <IssuesSection
            issues={issuesQuery.data ?? []}
            appliances={appliances}
            applianceName={applianceName}
            statusFilter={issueStatus}
            onStatusFilterChange={setIssueStatus}
            applianceFilter={issueAppliance}
            onApplianceFilterChange={setIssueAppliance}
            isLoading={issuesQuery.isLoading}
            composerOpen={issueComposerOpen && canWriteIssues}
            form={issueForm}
            setForm={setIssueForm}
            members={members}
            editingStatus={editingIssueStatus}
            onEditingStatusChange={setEditingIssueStatus}
            isEditing={Boolean(editingIssueId)}
            isPending={reportIssueMutation.isPending || updateIssueMutation.isPending}
            onSubmit={submitIssue}
            onEdit={beginEditIssue}
            onAdvance={(issue) => updateIssueMutation.mutate({ issueId: issue.issue_id, status: getNextIssueStatus(issue.status) })}
            onDelete={(id) => deleteIssueMutation.mutate(id)}
            canWrite={canWriteIssues}
            canDelete={canManageAppliances}
          />

          {canViewRepairs ? (
            <RepairsSection
              repairs={repairsQuery.data ?? []}
              appliances={appliances}
              applianceName={applianceName}
              applianceFilter={repairAppliance}
              onApplianceFilterChange={setRepairAppliance}
              isLoading={repairsQuery.isLoading}
              composerOpen={repairComposerOpen}
              form={repairForm}
              setForm={setRepairForm}
              isPending={logRepairMutation.isPending}
              onSubmit={submitRepair}
              onDelete={(id) => deleteRepairMutation.mutate(id)}
            />
          ) : (
            <Card className="p-5 sm:p-6">
              <SectionHeading title="Repair history" detail="Service records and costs" />
              <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted">
                <p className="font-semibold text-[var(--ink)]">Restricted</p>
                <p className="mt-1">Repair history and costs are visible to Adult and Admin members only.</p>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-5">
          <Card className="p-6">
            <SectionHeading title="Maintenance rhythm" detail="A quiet view of home health" />
            <div className="mt-6 grid grid-cols-2 gap-3">
              <Metric value={summary.appliances} label="Appliances" />
              <Metric value={summary.openIssues} label="Open issues" />
              <Metric value={summary.expiringSoon} label={`Expiring ≤ ${expiringDays}d`} />
              <Metric value={formatCost(summary.repairSpendMinor, summary.repairCurrency)} label="Repair spend" wide />
            </div>
          </Card>

          <Card className="bg-[#284837] p-6 text-white">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">HomeOps tip</p>
            <p className="mt-3 text-lg font-bold leading-snug">Log repairs while covered by warranty.</p>
            <p className="mt-2 text-sm leading-6 text-[#D2E6D8]">Expiring warranties are checked live — report issues before coverage ends.</p>
          </Card>
        </div>
      </div>
    </section>
  );
}

// --- Section 1: Appliances & warranties ---

function AppliancesSection(props: {
  appliances: Appliance[];
  expiring: { appliance_id: string; name: string; brand: string | null; model: string | null; warranty_ends_at: string; days_remaining: number }[];
  expiringDays: number;
  onExpiringDaysChange: (days: number) => void;
  isLoading: boolean;
  composerOpen: boolean;
  form: CreateApplianceInput;
  setForm: (value: CreateApplianceInput) => void;
  isEditing: boolean;
  isPending: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onEdit: (item: Appliance) => void;
  onDelete: (id: string) => void;
  canManage: boolean;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <SectionHeading
        title="Appliances & warranties"
        detail={`${props.appliances.length} tracked · ${props.expiring.length} expiring`}
        action={
          <select
            aria-label="Warranty window"
            value={props.expiringDays}
            onChange={(event) => props.onExpiringDaysChange(Number(event.target.value))}
            className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-1 text-xs font-semibold"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
        }
      />

      {props.expiring.length > 0 && (
        <div className="mt-4 rounded-xl bg-[#F6EADB] p-4">
          <p className="text-sm font-semibold text-[#8A5D2F]">Warranties expiring within {props.expiringDays} days</p>
          <div className="mt-2 space-y-1">
            {props.expiring.map((item) => (
              <p key={item.appliance_id} className="text-xs text-[#8d4b35]">
                {item.name} — {formatWarrantyDate(item.warranty_ends_at)} ({item.days_remaining}d left)
              </p>
            ))}
          </div>
        </div>
      )}

      {props.composerOpen && (
        <form className="mt-4 grid gap-4 rounded-2xl border border-[var(--line)] p-4 md:grid-cols-2" onSubmit={props.onSubmit}>
          <label className="md:col-span-2">
            <span className="mb-1.5 block text-sm font-semibold">Appliance name</span>
            <input required value={props.form.name} onChange={(event) => props.setForm({ ...props.form, name: event.target.value })} className="task-input" placeholder="e.g. Dishwasher" />
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Brand <span className="font-normal muted">(optional)</span></span>
            <input value={props.form.brand ?? ''} onChange={(event) => props.setForm({ ...props.form, brand: event.target.value })} className="task-input" placeholder="e.g. Bosch" />
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Model <span className="font-normal muted">(optional)</span></span>
            <input value={props.form.model ?? ''} onChange={(event) => props.setForm({ ...props.form, model: event.target.value })} className="task-input" placeholder="e.g. SMV4HCX19N" />
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Purchased <span className="font-normal muted">(optional)</span></span>
            <input type="date" value={props.form.purchased_at ?? ''} onChange={(event) => props.setForm({ ...props.form, purchased_at: event.target.value })} className="task-input" />
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Warranty ends <span className="font-normal muted">(optional)</span></span>
            <input type="date" value={props.form.warranty_ends_at ?? ''} onChange={(event) => props.setForm({ ...props.form, warranty_ends_at: event.target.value })} className="task-input" />
          </label>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={props.isPending}>{props.isPending && <LoaderCircle className="animate-spin" size={16} />}{props.isPending ? 'Saving…' : props.isEditing ? 'Update appliance' : 'Add appliance'}</Button>
          </div>
        </form>
      )}

      {props.isLoading ? (
        <div className="flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading appliances</div>
      ) : props.appliances.length ? (
        <div className="mt-4 space-y-3">
          {props.appliances.map((item) => (
            <article key={item.appliance_id} className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4 transition hover:bg-[#ECEAE4]/60">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--ink)]">{item.name}</p>
                <p className="mt-1 text-xs muted">
                  {[item.brand, item.model].filter(Boolean).join(' · ') || 'No brand/model'} · Warranty: {formatWarrantyDate(item.warranty_ends_at)}
                </p>
              </div>
              {props.canManage && (
                <div className="flex shrink-0 items-center gap-1">
                  <button type="button" aria-label={`Edit ${item.name}`} title={`Edit ${item.name}`} onClick={() => props.onEdit(item)} className="grid size-8 place-items-center rounded-full text-[#676B68] transition hover:bg-[#ECEAE4] hover:text-[#284837]">
                    <Pencil size={15} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${item.name}`}
                    title={`Delete ${item.name}`}
                    onClick={() => { if (window.confirm(`Delete ${item.name}? Its service records will also be removed.`)) props.onDelete(item.appliance_id); }}
                    className="grid size-8 place-items-center rounded-full text-[#676B68] transition hover:bg-[#B96359]/10 hover:text-[#8B3F36]"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted">
          <p className="font-semibold text-[var(--ink)]">No appliances yet</p>
          <p className="mt-1">Add the first appliance to start tracking warranties.</p>
        </div>
      )}
    </Card>
  );
}

// --- Section 2: Issues ---

function IssuesSection(props: {
  issues: MaintenanceIssue[];
  appliances: Appliance[];
  applianceName: (id: string | null) => string | null;
  statusFilter: IssueStatus | 'All';
  onStatusFilterChange: (value: IssueStatus | 'All') => void;
  applianceFilter: string;
  onApplianceFilterChange: (value: string) => void;
  isLoading: boolean;
  composerOpen: boolean;
  form: { description: string; priority: MaintenancePriority; appliance_id: string; accountable_to: string };
  setForm: (value: { description: string; priority: MaintenancePriority; appliance_id: string; accountable_to: string }) => void;
  members: HouseholdMember[];
  editingStatus: IssueStatus;
  onEditingStatusChange: (value: IssueStatus) => void;
  isEditing: boolean;
  isPending: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onEdit: (issue: MaintenanceIssue) => void;
  onAdvance: (issue: MaintenanceIssue) => void;
  onDelete: (id: string) => void;
  canWrite: boolean;
  canDelete: boolean;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <SectionHeading title="Maintenance issues" detail={`${props.issues.length} reported`} />
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="relative">
          <select
            aria-label="Filter by status"
            value={props.statusFilter}
            onChange={(event) => props.onStatusFilterChange(event.target.value as IssueStatus | 'All')}
            className="task-input appearance-none !w-auto pr-9 text-xs font-semibold"
          >
            <option value="All">All statuses</option>
            {ISSUE_STATUSES.map((status) => <option key={status} value={status}>{status === 'InProgress' ? 'In progress' : status}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={14} />
        </span>
        <span className="relative">
          <select
            aria-label="Filter by appliance"
            value={props.applianceFilter}
            onChange={(event) => props.onApplianceFilterChange(event.target.value)}
            className="task-input appearance-none !w-auto pr-9 text-xs font-semibold"
          >
            <option value="">All appliances</option>
            {props.appliances.map((item) => <option key={item.appliance_id} value={item.appliance_id}>{item.name}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={14} />
        </span>
      </div>

      {props.composerOpen && (
        <form className="mt-4 grid gap-4 rounded-2xl border border-[var(--line)] p-4 md:grid-cols-2" onSubmit={props.onSubmit}>
          <label className="md:col-span-2">
            <span className="mb-1.5 block text-sm font-semibold">Issue description</span>
            <textarea required={!props.isEditing} value={props.form.description} onChange={(event) => props.setForm({ ...props.form, description: event.target.value })} className="task-input min-h-20 resize-y py-3" placeholder="e.g. The AC is making a rattling noise" />
          </label>
          {props.isEditing && (
            <label>
              <span className="mb-1.5 block text-sm font-semibold">Status</span>
              <select value={props.editingStatus} onChange={(event) => props.onEditingStatusChange(event.target.value as IssueStatus)} className="task-input">
                {ISSUE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </label>
          )}
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Priority</span>
            <select value={props.form.priority} onChange={(event) => props.setForm({ ...props.form, priority: event.target.value as MaintenancePriority })} className="task-input">
              {PRIORITIES.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
            </select>
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Appliance <span className="font-normal muted">(optional)</span></span>
            <select value={props.form.appliance_id} onChange={(event) => props.setForm({ ...props.form, appliance_id: event.target.value })} className="task-input">
              <option value="">None</option>
              {props.appliances.map((item) => <option key={item.appliance_id} value={item.appliance_id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Accountable to <span className="font-normal muted">(optional)</span></span>
            <select value={props.form.accountable_to} onChange={(event) => props.setForm({ ...props.form, accountable_to: event.target.value })} className="task-input">
              <option value="">Unassigned</option>
              {props.members.map((member) => <option key={member.user_id} value={member.user_id}>{member.name} ({member.role})</option>)}
            </select>
          </label>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={props.isPending}>{props.isPending && <LoaderCircle className="animate-spin" size={16} />}{props.isPending ? 'Saving…' : props.isEditing ? 'Update issue' : 'Report issue'}</Button>
          </div>
        </form>
      )}

      {props.isLoading ? (
        <div className="flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading issues</div>
      ) : props.issues.length ? (
        <div className="mt-4 space-y-3">
          {props.issues.map((issue) => {
            const linked = props.applianceName(issue.appliance_id);
            return (
              <article key={issue.issue_id} className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4 transition hover:bg-[#ECEAE4]/60">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--ink)]">{issue.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs muted">
                    <span className={`rounded-full px-2 py-0.5 font-semibold ${issueTone(issue.status)}`}>{issue.status === 'InProgress' ? 'In progress' : issue.status}</span>
                    <span className={`rounded-full px-2 py-0.5 font-semibold ${priorityTone(issue.priority)}`}>{issue.priority} priority</span>
                    {linked && <span>· {linked}</span>}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {props.canWrite && (
                    <button
                      type="button"
                      title={`Advance to ${getNextIssueStatus(issue.status)}`}
                      aria-label={`Advance ${issue.description} to ${getNextIssueStatus(issue.status)}`}
                      onClick={() => props.onAdvance(issue)}
                      className="rounded-full border border-[#B9B9B2] px-2.5 py-1 text-xs font-semibold text-[#676B68] transition hover:border-[#5E9278] hover:text-[#284837]"
                    >
                      → {getNextIssueStatus(issue.status) === 'InProgress' ? 'In progress' : getNextIssueStatus(issue.status)}
                    </button>
                  )}
                  {props.canWrite && (
                    <button type="button" aria-label={`Edit issue`} title="Edit issue" onClick={() => props.onEdit(issue)} className="grid size-8 place-items-center rounded-full text-[#676B68] transition hover:bg-[#ECEAE4] hover:text-[#284837]">
                      <Pencil size={15} />
                    </button>
                  )}
                  {props.canDelete && (
                    <button type="button" aria-label="Delete issue" title="Delete issue" onClick={() => { if (window.confirm('Delete this issue?')) props.onDelete(issue.issue_id); }} className="grid size-8 place-items-center rounded-full text-[#676B68] transition hover:bg-[#B96359]/10 hover:text-[#8B3F36]">
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted">
          <p className="font-semibold text-[var(--ink)]">No issues found</p>
          <p className="mt-1">Report the first maintenance issue so it stays tracked.</p>
        </div>
      )}
    </Card>
  );
}

// --- Section 3: Repairs (create + delete only) ---

function RepairsSection(props: {
  repairs: Repair[];
  appliances: Appliance[];
  applianceName: (id: string | null) => string | null;
  applianceFilter: string;
  onApplianceFilterChange: (value: string) => void;
  isLoading: boolean;
  composerOpen: boolean;
  form: { serviced_at: string; appliance_id: string; provider: string; costMajor: string; currency: string; notes: string };
  setForm: (value: { serviced_at: string; appliance_id: string; provider: string; costMajor: string; currency: string; notes: string }) => void;
  isPending: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDelete: (id: string) => void;
}) {
  const costInvalid = props.form.costMajor.trim() !== '' && costMajorToMinor(props.form.costMajor) === null;
  return (
    <Card className="p-5 sm:p-6">
      <SectionHeading title="Repair history" detail={`${props.repairs.length} records`} />
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="relative">
          <select
            aria-label="Filter repairs by appliance"
            value={props.applianceFilter}
            onChange={(event) => props.onApplianceFilterChange(event.target.value)}
            className="task-input appearance-none !w-auto pr-9 text-xs font-semibold"
          >
            <option value="">All appliances</option>
            {props.appliances.map((item) => <option key={item.appliance_id} value={item.appliance_id}>{item.name}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68]" size={14} />
        </span>
      </div>

      {props.composerOpen && (
        <form className="mt-4 grid gap-4 rounded-2xl border border-[var(--line)] p-4 md:grid-cols-2" onSubmit={props.onSubmit}>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Serviced on</span>
            <input type="date" required value={props.form.serviced_at} onChange={(event) => props.setForm({ ...props.form, serviced_at: event.target.value })} className="task-input" />
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Appliance <span className="font-normal muted">(optional)</span></span>
            <select value={props.form.appliance_id} onChange={(event) => props.setForm({ ...props.form, appliance_id: event.target.value })} className="task-input">
              <option value="">None</option>
              {props.appliances.map((item) => <option key={item.appliance_id} value={item.appliance_id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            <span className="mb-1.5 block text-sm font-semibold">Provider <span className="font-normal muted">(optional)</span></span>
            <input value={props.form.provider} onChange={(event) => props.setForm({ ...props.form, provider: event.target.value })} className="task-input" placeholder="e.g. CoolCare Services" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="mb-1.5 block text-sm font-semibold">Cost <span className="font-normal muted">(optional)</span></span>
              <input
                inputMode="decimal"
                value={props.form.costMajor}
                onChange={(event) => props.setForm({ ...props.form, costMajor: event.target.value })}
                className="task-input"
                placeholder="e.g. 45.00"
                aria-invalid={costInvalid}
              />
            </label>
            <label>
              <span className="mb-1.5 block text-sm font-semibold">Currency</span>
              <input value={props.form.currency} onChange={(event) => props.setForm({ ...props.form, currency: event.target.value.toUpperCase() })} className="task-input" maxLength={3} placeholder="USD" />
            </label>
          </div>
          {costInvalid && <p className="-mt-2 text-xs font-semibold text-[#8B3F36] md:col-span-2">Enter a valid non-negative amount.</p>}
          <label className="md:col-span-2">
            <span className="mb-1.5 block text-sm font-semibold">Notes <span className="font-normal muted">(optional)</span></span>
            <textarea value={props.form.notes} onChange={(event) => props.setForm({ ...props.form, notes: event.target.value })} className="task-input min-h-20 resize-y py-3" placeholder="What was serviced?" />
          </label>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={props.isPending || costInvalid}>{props.isPending && <LoaderCircle className="animate-spin" size={16} />}{props.isPending ? 'Saving…' : 'Log repair'}</Button>
          </div>
        </form>
      )}

      {props.isLoading ? (
        <div className="flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading repairs</div>
      ) : props.repairs.length ? (
        <div className="mt-4 space-y-3">
          {props.repairs.map((repair) => {
            const linked = props.applianceName(repair.appliance_id);
            return (
              <article key={repair.repair_id} className="flex items-start gap-3 rounded-2xl border border-[var(--line)] p-4 transition hover:bg-[#ECEAE4]/60">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--ink)]">
                    {formatWarrantyDate(repair.serviced_at)}{linked ? ` · ${linked}` : ''}
                  </p>
                  {repair.provider && <p className="mt-1 text-xs muted">by {repair.provider}</p>}
                  {repair.notes && <p className="mt-1 text-sm muted">{repair.notes}</p>}
                  <p className="mt-2 text-xs font-semibold text-[var(--ink)]">{formatCost(repair.cost_minor, repair.currency)}</p>
                </div>
                <button type="button" aria-label="Delete repair record" title="Delete repair record" onClick={() => { if (window.confirm('Delete this repair record?')) props.onDelete(repair.repair_id); }} className="grid size-8 shrink-0 place-items-center rounded-full text-[#676B68] transition hover:bg-[#B96359]/10 hover:text-[#8B3F36]">
                  <Trash2 size={15} />
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl bg-[#ECEAE4] p-6 text-sm muted">
          <p className="font-semibold text-[var(--ink)]">No repairs logged</p>
          <p className="mt-1">Log the first service to build a maintenance history.</p>
        </div>
      )}
    </Card>
  );
}

function Metric({ value, label, wide = false }: { value: string | number; label: string; wide?: boolean }) {
  return (
    <div className={`rounded-xl bg-[#ECEAE4] p-4 ${wide ? 'col-span-2' : ''}`}>
      <p className="truncate text-2xl font-bold">{value}</p>
      <p className="mt-1 text-xs muted">{label}</p>
    </div>
  );
}
