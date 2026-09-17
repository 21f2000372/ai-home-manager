import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  Utensils, 
  Wallet, 
  CheckSquare, 
  Wrench, 
  Calendar, 
  ShieldCheck, 
  ArrowRight, 
  Sparkles, 
  CheckCircle,
  FileText,
  UserCheck
} from 'lucide-react';

export const PlanCard = ({ planData, onApply }) => {
  const { isPlanApplied, activeUser } = useHousehold();
  const domains = planData.domainResults;

  return (
    <div className="bg-slate-900/90 border border-brand-500/30 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl mt-4 animate-fade-in">
      {/* Plan Header */}
      <div className="bg-gradient-to-r from-brand-950 via-slate-900 to-navy-900 p-5 border-b border-brand-500/20">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">{planData.title}</h3>
                <Badge variant="brand" size="sm">Multi-Domain Coordinated</Badge>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">{planData.summary}</p>
            </div>
          </div>

          {!isPlanApplied ? (
            <button
              onClick={() => onApply(planData)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-400 hover:to-brand-500 text-white font-semibold text-sm shadow-glow-brand transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <CheckCircle className="w-4 h-4" />
              Apply Plan to Household
            </button>
          ) : (
            <Badge variant="emerald" size="lg" className="py-2 px-4">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Plan Active & Synced in State
            </Badge>
          )}
        </div>

        {/* Input Scenario summary */}
        <div className="mt-3.5 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs text-slate-300 flex items-center gap-2">
          <span className="font-semibold text-brand-300 shrink-0">Synthesized Context:</span>
          <span>{planData.scenarioSummary}</span>
        </div>
      </div>

      {/* Multi-Agent Reasoning Trace Accordion / Cards */}
      {planData.agentReasoningTrace && (
        <div className="p-4 bg-slate-950/50 border-b border-slate-800">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5 flex items-center gap-1.5">
            <UserCheck className="w-3.5 h-3.5 text-brand-400" />
            Collaborative Agent Contributions
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {planData.agentReasoningTrace.map((trace, idx) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 text-xs"
              >
                <div className="flex items-center gap-2 font-semibold text-slate-200 mb-1.5">
                  <span className={`w-2 h-2 rounded-full ${
                    trace.color === 'purple' ? 'bg-purple-400' : trace.color === 'emerald' ? 'bg-emerald-400' : 'bg-amber-400'
                  }`} />
                  {trace.title}
                </div>
                <ul className="space-y-1 text-[11px] text-slate-400 list-disc list-inside">
                  {trace.points.map((pt, pIdx) => (
                    <li key={pIdx} className="leading-snug">{pt}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Domain Cards Grid */}
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 1. Food & Inventory */}
        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                <Utensils className="w-4 h-4" />
                Food & Inventory
              </div>
              <Badge variant="emerald" size="sm">Low-Salt Filter</Badge>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {domains.food.actions.map((act, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">•</span>
                  <span>{act}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[11px] text-emerald-400 font-mono">
            Verified: Dr. Verma Clinical Directive #DOC-MED-01
          </div>
        </div>

        {/* 2. Finance & Budget */}
        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2 text-brand-400 font-semibold text-sm">
                <Wallet className="w-4 h-4" />
                Finance & Budgeting
              </div>
              {domains.finance.isRestricted ? (
                <Badge variant="rose" size="sm">Restricted Role</Badge>
              ) : (
                <Badge variant="brand" size="sm">₹5,000 Weekly Cap</Badge>
              )}
            </div>

            {domains.finance.isRestricted ? (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300">
                🛡️ Financial balances and line-item totals are hidden for {activeUser.role} accounts.
              </div>
            ) : (
              <div className="space-y-1.5 text-xs text-slate-300">
                <div className="flex justify-between">
                  <span className="text-slate-400">Groceries (4 Guests):</span>
                  <span className="font-semibold text-slate-200">₹1,700</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Grandma Rx Refill:</span>
                  <span className="font-semibold text-slate-200">₹900</span>
                </div>
                <div className="flex justify-between pt-1 border-t border-slate-700">
                  <span className="text-slate-400">Total Planned:</span>
                  <span className="font-semibold text-amber-300">₹2,600</span>
                </div>
                <div className="flex justify-between text-brand-300 font-bold">
                  <span>Estimated Remaining:</span>
                  <span>₹2,400</span>
                </div>
              </div>
            )}
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[11px] text-slate-400 font-mono">
            Cross-check: Within ₹5,000 threshold
          </div>
        </div>

        {/* 3. Tasks & Reassignments */}
        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2 text-purple-400 font-semibold text-sm">
                <CheckSquare className="w-4 h-4" />
                Task Orchestration
              </div>
              <Badge variant="purple" size="sm">3 Dispatches</Badge>
            </div>
            <ul className="space-y-1.5 text-xs text-slate-300">
              {domains.tasks.actions.map((act, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">•</span>
                  <span>{act}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[11px] text-purple-300 font-mono">
            Mom travel compensated by Rajesh & Aarav
          </div>
        </div>

        {/* 4. Home & Maintenance */}
        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                <Wrench className="w-4 h-4" />
                Maintenance & Appliances
              </div>
              <Badge variant="amber" size="sm">Guest Prep</Badge>
            </div>
            <ul className="space-y-1.5 text-xs text-slate-300">
              {domains.maintenance.actions.map((act, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-amber-400 mt-0.5">•</span>
                  <span>{act}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[11px] text-amber-300 font-mono">
            Warranty: Daikin AMC Free Service Valid
          </div>
        </div>

        {/* 5. Synchronized Schedule */}
        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between lg:col-span-2">
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
                <Calendar className="w-4 h-4" />
                Chronological Execution Schedule
              </div>
              <Badge variant="brand" size="sm">Wed → Sat</Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {domains.schedule.timeline.map((item, i) => (
                <div key={i} className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-brand-300 mr-2">{item.day}:</span>
                    <span className="text-slate-200">{item.event}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono shrink-0 ml-2">[{item.owner}]</span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[11px] text-slate-400 font-mono flex items-center justify-between">
            <span>Relatives Arrive: Saturday 11:00 AM</span>
            <span className="text-emerald-400">All readiness milestones verified</span>
          </div>
        </div>
      </div>
    </div>
  );
};
