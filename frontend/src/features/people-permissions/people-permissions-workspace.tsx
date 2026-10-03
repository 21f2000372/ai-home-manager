import { useState } from 'react';
import { Check, Clipboard, Copy, Crown, LoaderCircle, ShieldCheck, UserPlus, UsersRound } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge } from '@/components/design-system/badge';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { useSessionStore, type SessionUser } from '@/stores/session-store';
import {
  approveMember,
  changeMemberRole,
  createInvite,
  getActiveMembers,
  getPendingMembers,
  transferAdmin,
  type ActiveMember,
  type HouseholdRole,
  type PendingMember,
} from './people-api';

const pendingKey = ['household', 'members', 'pending'] as const;
const membersKey = ['household', 'members'] as const;
type AssignableRole = Exclude<HouseholdRole, 'Admin'>;
type PendingAction =
  | { kind: 'approve'; member: PendingMember; role: AssignableRole }
  | { kind: 'role'; member: ActiveMember; role: AssignableRole }
  | { kind: 'transfer'; member: ActiveMember };

const roleDetails: Record<HouseholdRole, string> = {
  Admin: 'Manage invitations, approvals, roles, and all household domains.',
  Adult: 'Coordinate shared household work and private adult domains.',
  Child: 'Use assigned tasks and approved shared spaces.',
  Guest: 'Read only the household information explicitly shared with them.',
};

export function PeoplePermissionsWorkspace() {
  const queryClient = useQueryClient();
  const user = useSessionStore((state) => state.user);
  const setAuthenticated = useSessionStore((state) => state.setAuthenticated);
  const isAdmin = user?.role === 'Admin';
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pendingRoles, setPendingRoles] = useState<Record<string, AssignableRole>>({});
  const [activeRoles, setActiveRoles] = useState<Record<string, AssignableRole>>({});
  const [action, setAction] = useState<PendingAction | null>(null);

  const pendingQuery = useQuery({ queryKey: pendingKey, queryFn: getPendingMembers, enabled: isAdmin });
  const membersQuery = useQuery({ queryKey: membersKey, queryFn: getActiveMembers, enabled: isAdmin });
  const refreshPeople = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: pendingKey }),
    queryClient.invalidateQueries({ queryKey: membersKey }),
  ]);

  const inviteMutation = useMutation({
    mutationFn: createInvite,
    onSuccess: ({ invite_code }) => {
      setInviteCode(invite_code);
      setCopied(false);
    },
  });
  const approveMutation = useMutation({
    mutationFn: ({ member, role }: Extract<PendingAction, { kind: 'approve' }>) => approveMember(member.user_id, role),
    onSuccess: refreshPeople,
  });
  const roleMutation = useMutation({
    mutationFn: ({ member, role }: Extract<PendingAction, { kind: 'role' }>) => changeMemberRole(member.user_id, role),
    onSuccess: refreshPeople,
  });
  const transferMutation = useMutation({
    mutationFn: ({ member }: Extract<PendingAction, { kind: 'transfer' }>) => transferAdmin(member.user_id),
    onSuccess: async () => {
      await refreshPeople();
      if (user) setAuthenticated({ ...user, role: 'Adult' });
    },
  });

  const errors = [pendingQuery.error, membersQuery.error, inviteMutation.error, approveMutation.error, roleMutation.error, transferMutation.error];
  const firstError = errors.find(Boolean);
  const errorMessage = firstError instanceof ApiError
    ? firstError.message
    : firstError ? 'HomeOps could not update household access. Please try again.' : null;
  const isMutating = inviteMutation.isPending || approveMutation.isPending || roleMutation.isPending || transferMutation.isPending;
  const inviteLink = inviteCode ? `${window.location.origin}/join?code=${encodeURIComponent(inviteCode)}` : null;

  async function copyInvite() {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  function roleForPending(member: PendingMember): AssignableRole {
    return pendingRoles[member.user_id] ?? 'Adult';
  }

  function roleForMember(member: ActiveMember): AssignableRole {
    return activeRoles[member.user_id] ?? (member.role === 'Admin' ? 'Adult' : member.role);
  }

  async function confirmAction() {
    if (!action) return;
    try {
      if (action.kind === 'approve') await approveMutation.mutateAsync(action);
      if (action.kind === 'role') await roleMutation.mutateAsync(action);
      if (action.kind === 'transfer') await transferMutation.mutateAsync(action);
      setAction(null);
    } catch {
      // The API error is displayed above the workspace.
    }
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#5E9278]"><UsersRound size={14} />People & permissions</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl">Household access</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 muted">Invite members, review join requests, and keep household access accurate.</p>
        </div>
        {isAdmin && <Button onClick={() => inviteMutation.mutate()} disabled={inviteMutation.isPending}><UserPlus size={16} />{inviteMutation.isPending ? 'Creating invite…' : 'Create invite link'}</Button>}
      </header>

      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-5">
          <CurrentAccess user={user} />
          {isAdmin && <>
            <PendingMembers
              members={pendingQuery.data ?? []}
              loading={pendingQuery.isLoading}
              selectedRole={roleForPending}
              setRole={(id, role) => setPendingRoles((current) => ({ ...current, [id]: role }))}
              onApprove={(member, role) => setAction({ kind: 'approve', member, role })}
            />
            <ActiveMembers
              members={membersQuery.data ?? []}
              loading={membersQuery.isLoading}
              currentUserId={user?.id}
              selectedRole={roleForMember}
              setRole={(id, role) => setActiveRoles((current) => ({ ...current, [id]: role }))}
              onRole={(member, role) => setAction({ kind: 'role', member, role })}
              onTransfer={(member) => setAction({ kind: 'transfer', member })}
            />
          </>}
        </div>
        <aside className="space-y-5">
          {isAdmin ? <InvitePanel inviteLink={inviteLink} copied={copied} onCopy={copyInvite} /> : <RoleGuide />}
        </aside>
      </div>

      {action && <ConfirmationCard action={action} isSubmitting={isMutating} onCancel={() => setAction(null)} onConfirm={() => void confirmAction()} />}
    </section>
  );
}

function CurrentAccess({ user }: { user: SessionUser | null }) {
  const role = user?.role;
  return <Card className="p-5 sm:p-6"><SectionHeading title="Your household access" detail="Your current role controls the actions and data available to you." action={role ? <Badge tone="verified">{role}</Badge> : <Badge>Session unavailable</Badge>} /><div className="mt-6 flex items-start gap-3 rounded-2xl bg-[#E4F0E8] p-4"><div className="grid size-10 shrink-0 place-items-center rounded-full bg-[#5E9278] text-sm font-bold text-white">{initials(user?.name ?? user?.email ?? 'H')}</div><div><p className="text-sm font-semibold text-[var(--ink)]">{user?.name ?? 'Signed-in household member'}</p><p className="mt-1 text-xs muted">{user?.email ?? 'Sign in again to load your account details.'}</p>{role && <p className="mt-3 text-sm leading-6 text-[#3D5F4E]">{roleDetails[role]}</p>}</div></div></Card>;
}

function PendingMembers({ members, loading, selectedRole, setRole, onApprove }: { members: PendingMember[]; loading: boolean; selectedRole: (member: PendingMember) => AssignableRole; setRole: (id: string, role: AssignableRole) => void; onApprove: (member: PendingMember, role: AssignableRole) => void }) {
  return <Card className="p-5 sm:p-6"><SectionHeading title="Pending join requests" detail="Review each request, choose an access level, then confirm the decision." action={<Badge tone="planned">Admin only</Badge>} />{loading ? <Loading /> : members.length ? <div className="mt-6 space-y-3">{members.map((member) => <article key={member.user_id} className="rounded-2xl border border-[var(--line)] p-4"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-[var(--ink)]">{member.name}</p><p className="mt-1 text-xs muted">{member.email}{ageLabel(member.date_of_birth) ? ` · ${ageLabel(member.date_of_birth)}` : ''}</p></div><div className="flex flex-wrap items-center gap-2"><RoleSelect value={selectedRole(member)} onChange={(role) => setRole(member.user_id, role)} /><Button onClick={() => onApprove(member, selectedRole(member))}><Check size={16} />Approve</Button></div></div></article>)}</div> : <Empty text="No pending requests. New join requests will appear here." />}</Card>;
}

function ActiveMembers({ members, loading, currentUserId, selectedRole, setRole, onRole, onTransfer }: { members: ActiveMember[]; loading: boolean; currentUserId?: string; selectedRole: (member: ActiveMember) => AssignableRole; setRole: (id: string, role: AssignableRole) => void; onRole: (member: ActiveMember, role: AssignableRole) => void; onTransfer: (member: ActiveMember) => void }) {
  return <Card className="p-5 sm:p-6"><SectionHeading title="Active household members" detail="Change non-Admin roles or transfer household administration to an Adult." action={<Badge tone="verified">{members.length} active</Badge>} />{loading ? <Loading /> : <div className="mt-6 space-y-3">{members.map((member) => <article key={member.user_id} className="rounded-2xl border border-[var(--line)] p-4"><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div><p className="text-sm font-semibold text-[var(--ink)]">{member.name}{member.user_id === currentUserId ? ' (you)' : ''}</p><p className="mt-1 text-xs muted">{member.role} household access</p></div>{member.role === 'Admin' ? <Badge tone="verified">Admin</Badge> : <div className="flex flex-wrap items-center gap-2"><RoleSelect value={selectedRole(member)} onChange={(role) => setRole(member.user_id, role)} /><Button tone="neutral" onClick={() => onRole(member, selectedRole(member))}>Save role</Button>{member.role === 'Adult' && <Button tone="neutral" onClick={() => onTransfer(member)}><Crown size={16} />Transfer Admin</Button>}</div>}</div></article>)}</div>}</Card>;
}

function InvitePanel({ inviteLink, copied, onCopy }: { inviteLink: string | null; copied: boolean; onCopy: () => void }) {
  return <Card className="p-5 sm:p-6"><SectionHeading title="Invite a household member" detail="Create a link, then share it only with the intended household member." />{inviteLink ? <div className="mt-6 rounded-2xl bg-[#284837] p-5 text-white"><p className="text-xs font-bold uppercase tracking-[0.14em] text-[#D19A4C]">Share this invite link</p><code className="mt-3 block break-all rounded-xl bg-black/15 px-3 py-3 text-xs font-semibold text-[#E4F0E8]">{inviteLink}</code><Button className="mt-4 w-full bg-white text-[#284837] hover:bg-[#E4F0E8]" onClick={onCopy}>{copied ? <Clipboard size={16} /> : <Copy size={16} />}{copied ? 'Copied' : 'Copy invite link'}</Button></div> : <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-5 text-sm leading-6 muted">Create an invite link to share with the person joining your household.</div>}</Card>;
}

function RoleGuide() {
  return <Card className="p-5 sm:p-6"><SectionHeading title="Role boundaries" detail="The backend enforces these permissions even if someone opens a protected URL directly." /><div className="mt-5 space-y-4">{(Object.keys(roleDetails) as HouseholdRole[]).map((role) => <div key={role} className="flex gap-3"><ShieldCheck className="mt-0.5 shrink-0 text-[#5E9278]" size={18} /><div><p className="text-sm font-semibold text-[var(--ink)]">{role}</p><p className="mt-1 text-xs leading-5 muted">{roleDetails[role]}</p></div></div>)}</div></Card>;
}

function ConfirmationCard({ action, isSubmitting, onCancel, onConfirm }: { action: PendingAction; isSubmitting: boolean; onCancel: () => void; onConfirm: () => void }) {
  const copy = action.kind === 'approve'
    ? `Approve ${action.member.name} as ${action.role}? They will immediately be able to sign in.`
    : action.kind === 'role'
      ? `Change ${action.member.name}'s role to ${action.role}?`
      : `Transfer Admin responsibility to ${action.member.name}? You will become an Adult.`;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"><Card className="w-full max-w-md p-6 shadow-xl"><h2 className="text-lg font-semibold text-[var(--ink)]">Confirm household change</h2><p className="mt-3 text-sm leading-6 muted">{copy}</p><div className="mt-6 flex justify-end gap-3"><Button tone="neutral" onClick={onCancel} disabled={isSubmitting}>Cancel</Button><Button onClick={onConfirm} disabled={isSubmitting}>{isSubmitting && <LoaderCircle className="animate-spin" size={16} />}Continue</Button></div></Card></div>;
}

function RoleSelect({ value, onChange }: { value: AssignableRole; onChange: (role: AssignableRole) => void }) {
  return <select aria-label="Member role" value={value} onChange={(event) => onChange(event.target.value as AssignableRole)} className="task-input min-h-10 w-auto py-2"><option value="Adult">Adult</option><option value="Child">Child</option><option value="Guest">Guest</option></select>;
}

function Loading() {
  return <div className="flex min-h-24 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading</div>;
}

function Empty({ text }: { text: string }) {
  return <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-5 text-sm leading-6 muted">{text}</div>;
}

function initials(value: string) {
  return value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function ageLabel(value: string | null) {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;

  const birthYear = Number(match[1]);
  const birthMonth = Number(match[2]) - 1;
  const birthDay = Number(match[3]);

  const today = new Date();
  let age = today.getFullYear() - birthYear;
  if (
    today.getMonth() < birthMonth ||
    (today.getMonth() === birthMonth && today.getDate() < birthDay)
  ) {
    age -= 1;
  }
  return `Age ${age}`;
}
