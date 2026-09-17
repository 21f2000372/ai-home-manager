import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  Sparkles, 
  X, 
  ArrowRight, 
  ArrowLeft, 
  ShieldCheck, 
  Brain, 
  CheckCircle2, 
  Workflow, 
  Lock,
  Layers,
  FileCheck2
} from 'lucide-react';

const DEMO_SLIDES = [
  {
    step: 1,
    badge: 'Core Paradigm',
    title: 'Welcome to HomeOps: Multi-Agent Household Intelligence',
    description: 'HomeOps maintains a shared, permission-aware household state and uses specialized AI agents to turn natural language updates into coordinated cross-domain actions.',
    highlightBox: {
      type: 'concept',
      title: 'Not Just Another Grocery or Task App',
      text: 'HomeOps does not treat chores, grocery lists, appliance servicing, or budgets as isolated silos. It coordinates all domains around unified household context and family rules.'
    },
    actionLabel: 'Explore Agent Architecture'
  },
  {
    step: 2,
    badge: 'Agent Architecture',
    title: 'Specialized 3-Agent Collaborative Network',
    description: 'A central Orchestrator delegates tasks to three domain-specialist agents who operate concurrently over the Shared Household State.',
    agents: [
      { name: 'Context Agent', role: 'Maintains member availability, travel schedules, roles & preferences', icon: '👥', color: 'purple' },
      { name: 'Document Agent', role: 'Indexes verified prescriptions, clinical dietary rules & warranties', icon: '📄', color: 'emerald' },
      { name: 'Operations Agent', role: 'Calculates inventory deficits, reassigns tasks, books maintenance & balances budget', icon: '⚡', color: 'amber' }
    ],
    actionLabel: 'View the Main Scenario'
  },
  {
    step: 3,
    badge: 'Primary Scenario',
    title: 'The Multi-Constraint Benchmark Scenario',
    description: 'Test how HomeOps handles realistic, multi-layered household dynamics in a single natural language update:',
    scenarioText: '"Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma\'s medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."',
    expectedOutcomes: [
      'Food: Procure groceries scaled for 4 guests + enforce low-sodium rule.',
      'Finance: Groceries (₹1,700) + Medicine (₹900) = ₹2,400 remaining balance of ₹5,000.',
      'Tasks: Mom\'s tasks reassigned; guest room prep assigned to Aarav (post-4 PM).',
      'Maintenance: Daikin AC service booked for Friday 10:00 AM before guests arrive.'
    ],
    actionLabel: 'Understand Privacy & RBAC'
  },
  {
    step: 4,
    badge: 'Privacy & Governance',
    title: 'Role-Based Access Control (RBAC) Built-In',
    description: 'Family data requires strict boundaries. HomeOps enforces privacy policies at both the API and agent reasoning levels.',
    testCases: [
      {
        role: 'Parent (Rajesh / Priya)',
        query: '"How much budget is remaining?"',
        result: 'Full visibility: "₹2,400 estimated remaining of ₹5,000 weekly budget with line items."'
      },
      {
        role: 'Teenager (Aarav)',
        query: '"How much budget is remaining?"',
        result: '🛡️ Redacted: "Financial information is restricted for your account."'
      }
    ],
    actionLabel: 'Launch Demo Now'
  }
];

export const DemoModal = () => {
  const { 
    isGuidedDemoOpen, 
    setIsGuidedDemoOpen, 
    sendAgentMessage, 
    setActiveTab, 
    switchUser 
  } = useHousehold();
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  if (!isGuidedDemoOpen) return null;

  const currentSlide = DEMO_SLIDES[currentSlideIndex];
  const isLast = currentSlideIndex === DEMO_SLIDES.length - 1;

  const handleNext = () => {
    if (isLast) {
      setIsGuidedDemoOpen(false);
      setActiveTab('ai_assistant');
      switchUser('rajesh');
      sendAgentMessage(
        "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."
      );
    } else {
      setCurrentSlideIndex(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    setCurrentSlideIndex(prev => Math.max(0, prev - 1));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-xl animate-fade-in">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 bg-gradient-to-r from-brand-950 via-slate-900 to-indigo-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
                Interactive Presentation Walkthrough
              </span>
              <h3 className="text-base font-bold text-white">
                Step {currentSlide.step} of {DEMO_SLIDES.length}: {currentSlide.badge}
              </h3>
            </div>
          </div>

          <button
            onClick={() => setIsGuidedDemoOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Slide Content Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          <h2 className="text-xl font-bold text-white leading-snug">{currentSlide.title}</h2>
          <p className="text-sm text-slate-300 leading-relaxed">{currentSlide.description}</p>

          {/* Slide 1 Highlights */}
          {currentSlide.highlightBox && (
            <div className="p-4 rounded-2xl bg-brand-950/40 border border-brand-500/30">
              <h4 className="font-semibold text-brand-300 text-sm mb-1">{currentSlide.highlightBox.title}</h4>
              <p className="text-xs text-slate-300 leading-relaxed">{currentSlide.highlightBox.text}</p>
            </div>
          )}

          {/* Slide 2 Agents */}
          {currentSlide.agents && (
            <div className="space-y-2.5 pt-1">
              {currentSlide.agents.map((agent, i) => (
                <div key={i} className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-3">
                  <span className="text-2xl mt-0.5">{agent.icon}</span>
                  <div>
                    <h5 className="font-bold text-sm text-slate-200">{agent.name}</h5>
                    <p className="text-xs text-slate-400">{agent.role}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Slide 3 Scenario */}
          {currentSlide.scenarioText && (
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-slate-950/80 border border-brand-500/30 text-xs font-mono text-brand-200 leading-relaxed">
                {currentSlide.scenarioText}
              </div>
              <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 text-xs space-y-1.5">
                <span className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">Expected Synthesis:</span>
                {currentSlide.expectedOutcomes.map((out, i) => (
                  <div key={i} className="flex items-start gap-2 text-slate-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{out}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Slide 4 Privacy */}
          {currentSlide.testCases && (
            <div className="space-y-2.5 pt-1">
              {currentSlide.testCases.map((tc, i) => (
                <div key={i} className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-brand-300">{tc.role} asks:</span>
                    <span className="text-slate-400 font-mono italic">{tc.query}</span>
                  </div>
                  <div className="text-slate-300 bg-slate-900 p-2 rounded-lg border border-slate-800 mt-1">
                    {tc.result}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={handlePrev}
            disabled={currentSlideIndex === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Previous
          </button>

          {/* Indicators */}
          <div className="flex items-center gap-1.5">
            {DEMO_SLIDES.map((_, i) => (
              <span
                key={i}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === currentSlideIndex ? 'w-6 bg-brand-500' : 'bg-slate-700'
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-gradient-to-r from-brand-500 to-indigo-600 hover:from-brand-400 hover:to-indigo-500 text-white text-xs font-semibold shadow-glow-brand transition-all hover:scale-[1.02]"
          >
            <span>{currentSlide.actionLabel}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
