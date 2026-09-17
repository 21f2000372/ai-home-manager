import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { AGENT_TYPES, WORKFLOW_STAGES } from '../../services/agentService';
import { Badge } from '../common/Badge';
import { 
  Network, 
  Cpu, 
  Database, 
  ShieldCheck, 
  Layers, 
  Activity, 
  ArrowDown, 
  ArrowRight,
  Sparkles,
  Bot,
  Zap,
  CheckCircle2,
  Clock
} from 'lucide-react';

export const AgentActivityView = () => {
  const { isProcessingAgent, agentSteps, isPlanApplied, state } = useHousehold();

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Banner */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-purple-950 via-slate-900 to-navy-900 border border-purple-500/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant="purple" size="sm">
                <Network className="w-3.5 h-3.5" />
                Multi-Agent Orchestration Graph
              </Badge>
              <Badge variant="emerald" size="sm">
                <ShieldCheck className="w-3.5 h-3.5" />
                Local Privacy Isolated
              </Badge>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              Agent Collaboration & Reasoning Network
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              HomeOps uses a centralized Orchestrator delegating to specialized Context, Document, and Operations agents operating around a reactive shared state.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="p-3 rounded-2xl bg-slate-950/80 border border-slate-800 text-center">
              <div className="text-[10px] text-slate-400 uppercase font-mono">Consensus State</div>
              <div className="text-sm font-bold text-emerald-400">
                {isProcessingAgent ? 'Synthesizing...' : isPlanApplied ? 'Plan Synchronized' : 'Idle / Ready'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Visual Multi-Agent Architecture Topology Graph */}
      <div className="p-6 rounded-3xl bg-slate-900/80 border border-slate-800 backdrop-blur-md">
        <h3 className="text-sm font-bold text-white mb-6 flex items-center gap-2">
          <Layers className="w-4 h-4 text-brand-400" />
          Execution Topology & Data Flow
        </h3>

        <div className="flex flex-col items-center space-y-6 max-w-3xl mx-auto">
          {/* Level 1: User Request */}
          <div className="w-64 p-3 rounded-2xl bg-slate-950 border border-slate-700 text-center shadow-lg">
            <span className="text-[10px] uppercase tracking-wider font-mono text-slate-400 block mb-1">Input Trigger</span>
            <div className="text-xs font-bold text-white flex items-center justify-center gap-1.5">
              <span>👤</span> Natural Language Update / Query
            </div>
          </div>

          <ArrowDown className="w-5 h-5 text-brand-400 animate-bounce" />

          {/* Level 2: Central Orchestrator */}
          <div className="w-80 p-4 rounded-2xl bg-gradient-to-r from-brand-950 to-indigo-950 border-2 border-brand-500/60 text-center shadow-glow-brand">
            <div className="flex items-center justify-center gap-2 mb-1">
              <span className="text-xl">🧠</span>
              <span className="font-bold text-white text-sm">Central Orchestrator</span>
            </div>
            <p className="text-[11px] text-brand-200">
              Intent Routing • Privacy Authorization • Plan Synthesis
            </p>
            <div className="mt-2 inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              {isProcessingAgent ? 'Active Coordination' : 'Standing By'}
            </div>
          </div>

          {/* Level 3: Three Concurrent Specialized Agents */}
          <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Context Agent */}
            <div className="p-4 rounded-2xl bg-purple-950/40 border border-purple-500/40 text-center">
              <div className="text-2xl mb-1">👥</div>
              <h4 className="font-bold text-white text-xs">Context Agent</h4>
              <p className="text-[11px] text-purple-200 mt-0.5">
                Members • Roles • Availability • Context Memory
              </p>
              <div className="mt-2 text-[10px] font-mono text-purple-300 bg-purple-950/60 p-1 rounded-lg border border-purple-800/60">
                Priya: Away till Fri • Rajesh: Active
              </div>
            </div>

            {/* Document Agent */}
            <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/40 text-center">
              <div className="text-2xl mb-1">📄</div>
              <h4 className="font-bold text-white text-xs">Document Agent</h4>
              <p className="text-[11px] text-emerald-200 mt-0.5">
                Verified RAG • Low-Salt Directive • Rx Schedule
              </p>
              <div className="mt-2 text-[10px] font-mono text-emerald-300 bg-emerald-950/60 p-1 rounded-lg border border-emerald-800/60">
                DOC-MED-01: Low-Salt Verified
              </div>
            </div>

            {/* Operations Agent */}
            <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-center">
              <div className="text-2xl mb-1">⚡</div>
              <h4 className="font-bold text-white text-xs">Operations Agent</h4>
              <p className="text-[11px] text-amber-200 mt-0.5">
                Food Scaling • Budget (₹5k) • Tasks • Maintenance
              </p>
              <div className="mt-2 text-[10px] font-mono text-amber-300 bg-amber-950/60 p-1 rounded-lg border border-amber-800/60">
                ₹1,700 Food + ₹900 Rx = ₹2,400 Rem
              </div>
            </div>
          </div>

          <ArrowDown className="w-5 h-5 text-purple-400" />

          {/* Level 4: Shared Household State Hub */}
          <div className="w-full p-4 rounded-2xl bg-slate-950 border border-slate-700 text-center shadow-xl">
            <div className="flex items-center justify-center gap-2 text-sky-300 font-bold text-xs mb-1">
              <Database className="w-4 h-4" />
              <span>Shared Household State Hub (Reactive Pub/Sub)</span>
            </div>
            <div className="flex flex-wrap justify-center gap-2 text-[10px] text-slate-400 font-mono mt-2">
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">People (4)</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">Tasks ({state.tasks.length})</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">Inventory (10)</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">Budget (₹5,000)</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">Appliances (5)</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">Documents (5)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Deep Dive Specification Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(AGENT_TYPES).map(([key, agent]) => (
          <div
            key={key}
            className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{agent.avatar}</span>
                <Badge variant={agent.color === 'brand' ? 'brand' : agent.color === 'purple' ? 'purple' : agent.color === 'emerald' ? 'emerald' : 'amber'} size="sm">
                  {agent.badge}
                </Badge>
              </div>
              <h4 className="font-bold text-white text-xs">{agent.name}</h4>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{agent.role}</p>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">{agent.description}</p>
            </div>

            <div className="mt-4 pt-2.5 border-t border-slate-800 text-[10px] font-mono text-slate-400 flex items-center justify-between">
              <span>Status:</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Operational
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Live / Recent Trace Logs */}
      <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
        <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-brand-400" />
          Recent Multi-Agent Event & Reasoning Audit Stream
        </h3>

        <div className="space-y-2 font-mono text-xs">
          {state.recentActivities.map((act) => (
            <div
              key={act.id}
              className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start justify-between gap-3 text-slate-300"
            >
              <div className="flex items-start gap-2.5">
                <span className="text-brand-400 font-semibold shrink-0">[{act.agent}]:</span>
                <span>{act.message}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0 text-[10px] text-slate-500">
                <span>{act.category}</span>
                <span>•</span>
                <span>{act.timestamp}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
