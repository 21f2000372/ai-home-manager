import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  Users, 
  ShieldCheck, 
  Lock, 
  Check, 
  X, 
  UserCheck, 
  AlertCircle, 
  Sparkles,
  ArrowRight
} from 'lucide-react';

export const PeoplePermissionsView = () => {
  const { state, rawState, activeUser, switchUser, setActiveTab, sendAgentMessage } = useHousehold();

  const PERMISSION_COLUMNS = [
    { key: 'canViewFinances', label: 'View Finances' },
    { key: 'canApproveExpenses', label: 'Approve Expenses' },
    { key: 'canViewAllTasks', label: 'View All Tasks' },
    { key: 'canAssignTasks', label: 'Assign Tasks' },
    { key: 'canViewMedicalDocs', label: 'Medical Documents' },
    { key: 'canManageAppliances', label: 'Manage Appliances' },
    { key: 'canExecuteAgentPlan', label: 'Execute Agent Plan' },
  ];

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-purple-950 via-slate-900 to-navy-900 border border-purple-500/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="purple" size="sm">
                <ShieldCheck className="w-3.5 h-3.5" />
                Family Governance & RBAC
              </Badge>
              <Badge variant="brand" size="sm">Context Agent</Badge>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              People, Roles & Permission Boundaries
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              Every household member has explicit access clearance. Context Agent enforces privacy rules across conversational queries and state rendering.
            </p>
          </div>
        </div>
      </div>

      {/* Member Profiles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {rawState.members.map((member) => {
          const isActive = member.id === activeUser.id;

          return (
            <div
              key={member.id}
              className={`p-5 rounded-3xl border transition-all flex flex-col justify-between ${
                isActive
                  ? 'bg-slate-900/90 border-brand-500/60 ring-2 ring-brand-500/20 shadow-glow-brand'
                  : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-3xl">{member.avatar}</span>
                  <Badge
                    variant={
                      member.clearance.includes('Full')
                        ? 'brand'
                        : member.clearance.includes('Restricted')
                        ? 'rose'
                        : 'amber'
                    }
                    size="sm"
                  >
                    {member.clearance}
                  </Badge>
                </div>

                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  {member.name}
                  {isActive && (
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" title="Active Persona" />
                  )}
                </h3>
                <div className="text-xs text-brand-300 font-medium">{member.role}</div>
                <div className="text-[11px] text-slate-400 mt-0.5">{member.relation}</div>

                <div className="mt-3 p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/80 text-[11px] text-slate-300">
                  <span className="font-semibold text-slate-200 block mb-0.5">Availability Context:</span>
                  {member.statusText}
                </div>

                <div className="mt-2.5 space-y-1 text-[11px] text-slate-400">
                  <span className="font-semibold text-slate-300">Assigned Domains:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {member.responsibilities.map((r, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-[10px]">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800">
                {isActive ? (
                  <div className="w-full py-1.5 rounded-xl bg-emerald-500/20 text-emerald-300 text-xs font-semibold text-center border border-emerald-500/30">
                    Active Persona
                  </div>
                ) : (
                  <button
                    onClick={() => switchUser(member.id)}
                    className="w-full py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
                  >
                    Switch to {member.name.split(' ')[0]}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* RBAC Permission Matrix Table */}
      <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 overflow-x-auto">
        <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
          <Lock className="w-4 h-4 text-brand-400" />
          Household Role-Based Access Control (RBAC) Matrix
        </h3>

        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-mono">
              <th className="pb-3 font-semibold">Household Member</th>
              <th className="pb-3 font-semibold">Role Type</th>
              {PERMISSION_COLUMNS.map((col) => (
                <th key={col.key} className="pb-3 font-semibold text-center">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {rawState.members.map((member) => (
              <tr key={member.id} className="hover:bg-slate-800/40">
                <td className="py-3 font-semibold text-white flex items-center gap-2">
                  <span>{member.avatar}</span>
                  <span>{member.name}</span>
                </td>
                <td className="py-3 text-slate-400">{member.role}</td>
                {PERMISSION_COLUMNS.map((col) => {
                  const hasPerm = member.permissions[col.key];
                  return (
                    <td key={col.key} className="py-3 text-center">
                      {hasPerm ? (
                        <span className="inline-flex p-1 rounded-full bg-emerald-500/20 text-emerald-400">
                          <Check className="w-3.5 h-3.5" />
                        </span>
                      ) : (
                        <span className="inline-flex p-1 rounded-full bg-rose-500/15 text-rose-400">
                          <X className="w-3.5 h-3.5" />
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Interactive Privacy Sandbox Test Card */}
      <div className="p-5 rounded-3xl bg-slate-900/90 border border-brand-500/30">
        <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-brand-400" />
          Live Permission Sandbox Demonstrator
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed max-w-3xl mb-4">
          Try asking the budget question under different personas to see the system's privacy governance in action:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Test Case A */}
          <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-emerald-400">Parent Persona (Rajesh):</span>
              <button
                onClick={() => {
                  switchUser('rajesh');
                  setActiveTab('ai_assistant');
                  sendAgentMessage("How much household budget is remaining this week?");
                }}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-emerald-600/30 text-emerald-300 hover:bg-emerald-600/50 font-semibold"
              >
                Test in AI Chat →
              </button>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900 text-slate-300 font-mono text-[11px]">
              Prompt: "How much household budget is remaining?"<br/>
              Result: <strong className="text-emerald-300">₹2,400 remaining of ₹5,000 budget with itemized breakdown.</strong>
            </div>
          </div>

          {/* Test Case B */}
          <div className="p-4 rounded-2xl bg-slate-950/70 border border-rose-500/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-rose-400">Teenager Persona (Aarav):</span>
              <button
                onClick={() => {
                  switchUser('aarav');
                  setActiveTab('ai_assistant');
                  sendAgentMessage("How much household budget is remaining this week?");
                }}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-rose-600/30 text-rose-300 hover:bg-rose-600/50 font-semibold"
              >
                Test in AI Chat →
              </button>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900 text-slate-300 font-mono text-[11px]">
              Prompt: "How much household budget is remaining?"<br/>
              Result: <strong className="text-rose-300">🛡️ Access Denied: Financial information is restricted for Teenager role.</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
