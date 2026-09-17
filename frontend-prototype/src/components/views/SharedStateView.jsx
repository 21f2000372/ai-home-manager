import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  Database, 
  Code, 
  Layers, 
  Share2, 
  Users, 
  CheckSquare, 
  UtensilsCrossed, 
  Wallet, 
  Wrench, 
  FileText, 
  Calendar,
  CheckCircle2,
  RefreshCw,
  Copy,
  Check
} from 'lucide-react';

export const SharedStateView = () => {
  const { rawState, state, activeUser, isPlanApplied } = useHousehold();
  const [viewMode, setViewMode] = useState('visual'); // 'visual' or 'json'
  const [copied, setCopied] = useState(false);

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(rawState, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-sky-950 via-slate-900 to-navy-900 border border-sky-500/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant="brand" size="sm">
                <Database className="w-3.5 h-3.5" />
                Unified Household State
              </Badge>
              <Badge variant="emerald" size="sm">
                Reactive Pub/Sub Synced
              </Badge>
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              Shared Household Knowledge & Domain Graph
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              The single source of truth queried and updated by Context, Document, and Operations agents. 
              Enforces privacy boundaries before presenting state to individual users.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('visual')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                viewMode === 'visual'
                  ? 'bg-brand-600 text-white shadow-glow-brand'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Domain Visualizer
            </button>
            <button
              onClick={() => setViewMode('json')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                viewMode === 'json'
                  ? 'bg-purple-600 text-white shadow-glow-purple'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              Raw State JSON
            </button>
          </div>
        </div>
      </div>

      {viewMode === 'visual' ? (
        <div className="space-y-6">
          {/* Central Hub Graph Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* 1. People & Roles */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-purple-400 font-bold text-xs">
                  <Users className="w-4 h-4" />
                  People & Availability ({rawState.members.length})
                </div>
                <Badge variant="purple" size="sm">Context Agent</Badge>
              </div>
              <div className="space-y-2">
                {rawState.members.map((m) => (
                  <div key={m.id} className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span>{m.avatar}</span>
                      <div>
                        <div className="font-semibold text-slate-200">{m.name}</div>
                        <div className="text-[10px] text-slate-400">{m.availability}</div>
                      </div>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 font-mono">
                      {m.role.split('/')[0]}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 2. Tasks & Schedule */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-brand-400 font-bold text-xs">
                  <CheckSquare className="w-4 h-4" />
                  Tasks & Assignments ({rawState.tasks.length})
                </div>
                <Badge variant="brand" size="sm">Operations Agent</Badge>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {rawState.tasks.map((t) => (
                  <div key={t.id} className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start justify-between text-xs">
                    <div>
                      <div className="font-semibold text-slate-200">{t.title}</div>
                      <div className="text-[10px] text-slate-400">Assigned: {t.assignedToName} ({t.dueDate})</div>
                    </div>
                    <Badge variant={t.status === 'completed' ? 'emerald' : 'default'} size="sm">
                      {t.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>

            {/* 3. Food & Inventory */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                  <UtensilsCrossed className="w-4 h-4" />
                  Food & Inventory ({rawState.inventory.length})
                </div>
                <Badge variant="emerald" size="sm">Operations Agent</Badge>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {rawState.inventory.map((inv) => (
                  <div key={inv.id} className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-semibold text-slate-200">{inv.name}</div>
                      <div className="text-[10px] text-slate-400">{inv.dietaryNote}</div>
                    </div>
                    <Badge variant={inv.status === 'available' ? 'emerald' : inv.status === 'low' ? 'amber' : 'rose'} size="sm">
                      {inv.quantity}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>

            {/* 4. Finance & Budget */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-amber-400 font-bold text-xs">
                  <Wallet className="w-4 h-4" />
                  Finance & Budgeting
                </div>
                <Badge variant="amber" size="sm">₹5,000 Cap</Badge>
              </div>
              <div className="space-y-2 text-xs">
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Weekly Budget:</span>
                    <span className="font-bold text-white">₹{rawState.finance.weeklyBudget.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Planned Expenses:</span>
                    <span className="font-bold text-amber-300">₹{rawState.finance.plannedExpenses.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between pt-1 border-t border-slate-800 text-brand-300 font-bold">
                    <span>Est. Remaining:</span>
                    <span>₹{rawState.finance.estimatedRemaining.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 5. Home & Maintenance */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-sky-400 font-bold text-xs">
                  <Wrench className="w-4 h-4" />
                  Appliances & Maintenance ({rawState.maintenance.length})
                </div>
                <Badge variant="brand" size="sm">Operations Agent</Badge>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {rawState.maintenance.map((m) => (
                  <div key={m.id} className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{m.name}</span>
                      <Badge variant={m.status === 'optimal' ? 'emerald' : m.status === 'scheduled' ? 'brand' : 'amber'} size="sm">
                        {m.statusLabel}
                      </Badge>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">{m.issueDescription}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 6. Documents & Knowledge */}
            <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                  <FileText className="w-4 h-4" />
                  Verified Documents & Rules ({rawState.documents.length})
                </div>
                <Badge variant="emerald" size="sm">Document Agent</Badge>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {rawState.documents.map((d) => (
                  <div key={d.id} className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200 truncate pr-2">{d.title}</span>
                      <Badge variant="emerald" size="sm">Verified</Badge>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1 truncate">{d.summary}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Raw JSON State Inspector */
        <div className="p-5 rounded-3xl bg-slate-950 border border-slate-800 relative">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
            <span className="text-xs font-mono text-slate-400">
              // Reactive Shared State Tree (Raw Snapshot)
            </span>
            <button
              onClick={handleCopyJson}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied JSON' : 'Copy State'}
            </button>
          </div>
          <pre className="text-xs font-mono text-emerald-400 overflow-x-auto max-h-[550px] p-2 leading-relaxed selection:bg-brand-500 selection:text-white">
            {JSON.stringify(rawState, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
