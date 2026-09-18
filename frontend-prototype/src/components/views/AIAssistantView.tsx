import React, { useState, useRef, useEffect } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { WorkflowPipeline } from '../agents/WorkflowPipeline';
import { PlanCard } from '../agents/PlanCard';
import { Badge } from '../common/Badge';
import { 
  Send, 
  Sparkles, 
  Bot, 
  User, 
  ShieldAlert, 
  CheckCircle2, 
  ArrowRight,
  RotateCcw,
  Zap,
  HelpCircle,
  Clock,
  Layers
} from 'lucide-react';

const QUICK_PROMPTS = [
  {
    label: "Main Demo Scenario",
    icon: "🎯",
    prompt: "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."
  },
  {
    label: "Check Budget (RBAC Test)",
    icon: "💰",
    prompt: "How much household budget is remaining this week?"
  },
  {
    label: "What chores do I have?",
    icon: "📋",
    prompt: "What tasks and chores are pending for me?"
  },
  {
    label: "What groceries to buy?",
    icon: "🛒",
    prompt: "What groceries and pantry items do we need to restock?"
  },
  {
    label: "AC Maintenance Status",
    icon: "🔧",
    prompt: "Check appliance maintenance status and AC warranty."
  }
];

export const AIAssistantView = () => {
  const { 
    chatMessages, 
    sendAgentMessage, 
    isProcessingAgent, 
    agentSteps, 
    activeUser, 
    applyPlan, 
    latestPlan 
  } = useHousehold();

  const [inputVal, setInputVal] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, agentSteps, isProcessingAgent]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim() || isProcessingAgent) return;
    sendAgentMessage(inputVal);
    setInputVal('');
  };

  const handleQuickPrompt = (promptText) => {
    if (isProcessingAgent) return;
    sendAgentMessage(promptText);
  };

  // Determine current active workflow stage from agentSteps
  const latestStep = agentSteps.length > 0 ? agentSteps[agentSteps.length - 1] : null;
  const currentStage = latestStep ? latestStep.stage : (isProcessingAgent ? 'CAPTURE' : null);

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-5xl mx-auto space-y-4 animate-fade-in">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 to-purple-600 flex items-center justify-center text-white shadow-glow-brand">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">HomeOps Multi-Agent Assistant</h2>
              <Badge variant="brand" size="sm">Coordinated Intelligence</Badge>
            </div>
            <p className="text-xs text-slate-400">
              Active Caller: <span className="font-semibold text-slate-200">{activeUser.name}</span> ({activeUser.role})
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Orchestrator • Context • Document • Operations</span>
        </div>
      </div>

      {/* Workflow Pipeline Display during or after agent reasoning */}
      {(isProcessingAgent || agentSteps.length > 0) && (
        <WorkflowPipeline 
          currentStage={currentStage} 
          isProcessing={isProcessingAgent} 
        />
      )}

      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4 rounded-3xl bg-slate-950/60 border border-slate-800/80 backdrop-blur-xl">
        {chatMessages.map((msg) => {
          const isUser = msg.sender === 'user';
          const isSystem = msg.sender === 'system';

          if (isSystem) {
            return (
              <div key={msg.id} className="p-4 rounded-2xl bg-brand-950/30 border border-brand-500/20 text-xs text-slate-300 space-y-2">
                <div className="flex items-center gap-2 text-brand-300 font-bold">
                  <Sparkles className="w-4 h-4" />
                  <span>HomeOps Household System</span>
                </div>
                <div className="text-slate-300 leading-relaxed whitespace-pre-wrap">{msg.text}</div>
              </div>
            );
          }

          if (isUser) {
            return (
              <div key={msg.id} className="flex justify-end gap-3 max-w-2xl ml-auto">
                <div className="space-y-1">
                  <div className="flex items-center justify-end gap-2 text-[11px] text-slate-400">
                    <span className="font-semibold text-slate-300">{msg.author}</span>
                    <span>({msg.role})</span>
                    <span>•</span>
                    <span>{msg.timestamp}</span>
                  </div>
                  <div className="p-4 rounded-2xl rounded-tr-sm bg-brand-600 text-white text-xs leading-relaxed shadow-lg">
                    {msg.text}
                  </div>
                </div>
                <div className="text-2xl mt-4 shrink-0">{msg.avatar || '👤'}</div>
              </div>
            );
          }

          // Agent Response Rendering
          const data = msg.data;
          const isPlan = data?.type === 'coordinated_plan';
          const isRestricted = data?.type === 'restricted';

          return (
            <div key={msg.id} className="flex gap-3 max-w-3xl">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-purple-600 flex items-center justify-center text-white shrink-0 mt-1 shadow-md">
                <Bot className="w-4 h-4" />
              </div>

              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span className="font-bold text-brand-300">HomeOps Orchestrator</span>
                  <span>•</span>
                  <span>{msg.timestamp}</span>
                </div>

                {isRestricted ? (
                  <div className="p-4 rounded-2xl rounded-tl-sm bg-rose-950/40 border border-rose-500/40 text-xs text-rose-200 leading-relaxed shadow-lg">
                    <div className="flex items-center gap-2 font-bold text-rose-300 mb-2">
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                      Family Privacy Governance Policy Enforced
                    </div>
                    <div className="whitespace-pre-wrap text-slate-300">{data.message}</div>
                  </div>
                ) : isPlan ? (
                  <PlanCard 
                    planData={data} 
                    onApply={(plan) => applyPlan(plan)} 
                  />
                ) : (
                  <div className="p-4 rounded-2xl rounded-tl-sm bg-slate-900 border border-slate-700/80 text-xs text-slate-200 leading-relaxed shadow-lg whitespace-pre-wrap">
                    {data?.message}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Real-Time Processing Agent Stream Steps */}
        {isProcessingAgent && (
          <div className="flex gap-3 max-w-3xl animate-fade-in">
            <div className="w-8 h-8 rounded-xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400 shrink-0 mt-1 animate-spin">
              <Zap className="w-4 h-4" />
            </div>

            <div className="flex-1 space-y-2">
              <div className="text-xs font-bold text-brand-300 flex items-center gap-2">
                <span>Multi-Agent Consensus in Progress...</span>
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping" />
              </div>

              <div className="space-y-1.5">
                {agentSteps.map((step, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs font-mono flex items-start gap-2 animate-slide-up"
                  >
                    <span className="text-brand-400 shrink-0">[{step.stage}]</span>
                    <span className="font-semibold text-purple-300 shrink-0">{step.agent}:</span>
                    <span className="text-slate-300">{step.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompt Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 shrink-0">
          Try Example:
        </span>
        {QUICK_PROMPTS.map((qp, idx) => (
          <button
            key={idx}
            onClick={() => handleQuickPrompt(qp.prompt)}
            disabled={isProcessingAgent}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-brand-500/40 text-slate-300 hover:text-white shrink-0 text-xs transition-colors disabled:opacity-40"
          >
            <span>{qp.icon}</span>
            <span>{qp.label}</span>
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSubmit} className="relative">
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder={`Ask HomeOps or announce a change (e.g. "Plan for this weekend" or announce guest arrival)...`}
          disabled={isProcessingAgent}
          className="w-full pl-4 pr-12 py-3.5 rounded-2xl bg-slate-900 border border-slate-700/80 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 text-xs text-white placeholder-slate-500 outline-none transition-all disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!inputVal.trim() || isProcessingAgent}
          className="absolute right-2 top-2 p-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
