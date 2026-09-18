import React from 'react';
import { WORKFLOW_STAGES } from '../../services/agentService';
import { Check, Sparkles, Shield, RefreshCw, Cpu, CheckCircle2, Database } from 'lucide-react';

const STAGE_ICONS = {
  CAPTURE: Sparkles,
  UNDERSTAND: Cpu,
  AUTHORIZE: Shield,
  UPDATE: RefreshCw,
  PLAN: Cpu,
  ACT: CheckCircle2,
  REMEMBER: Database,
};

export const WorkflowPipeline = ({ currentStage, isProcessing }) => {
  const currentIndex = WORKFLOW_STAGES.findIndex(s => s.id === currentStage);

  return (
    <div className="w-full bg-slate-900/60 border border-slate-800 rounded-2xl p-4 my-3 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-brand-400 animate-ping" />
          <span className="text-xs font-bold uppercase tracking-wider text-brand-300">
            Standard Agent Coordination Pipeline
          </span>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {isProcessing ? '⚡ Processing Request...' : '✅ Multi-Agent Consensus Ready'}
        </span>
      </div>

      {/* Pipeline Steps Horizontal Scroll/Flex */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
        {WORKFLOW_STAGES.map((stage, idx) => {
          const Icon = STAGE_ICONS[stage.id] || Sparkles;
          const isPassed = currentIndex > idx || (!isProcessing && currentIndex >= 0);
          const isCurrent = currentIndex === idx && isProcessing;
          const isUpcoming = currentIndex < idx && isProcessing;

          return (
            <div
              key={stage.id}
              className={`relative flex flex-col items-center text-center p-2.5 rounded-xl border transition-all duration-300 ${
                isCurrent
                  ? 'bg-brand-500/20 border-brand-500/60 shadow-glow-brand ring-1 ring-brand-400/50 scale-[1.03]'
                  : isPassed
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-950/40 border-slate-800/80 text-slate-500 opacity-60'
              }`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center mb-1.5 transition-colors ${
                  isCurrent
                    ? 'bg-brand-500 text-white animate-bounce'
                    : isPassed
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                {isPassed && !isCurrent ? <Check className="w-3.5 h-3.5" /> : <Icon className="w-3.5 h-3.5" />}
              </div>

              <div className="font-semibold text-xs text-slate-200">{stage.label}</div>
              <div className="text-[10px] text-slate-400 mt-0.5 leading-tight line-clamp-1">{stage.desc}</div>

              {/* Step number pill */}
              <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-slate-800 border border-slate-700 text-[9px] font-mono flex items-center justify-center text-slate-400">
                {idx + 1}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
