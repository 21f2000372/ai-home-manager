import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  CheckSquare, 
  Wallet, 
  UtensilsCrossed, 
  Calendar, 
  Wrench, 
  Sparkles, 
  ArrowRight, 
  ShieldCheck, 
  Clock, 
  AlertTriangle,
  FileText,
  UserCheck,
  CheckCircle2,
  Lock
} from 'lucide-react';

export const DashboardView = () => {
  const { 
    state, 
    activeUser, 
    setActiveTab, 
    toggleTask, 
    isPlanApplied,
    sendAgentMessage 
  } = useHousehold();

  const isRestrictedFinance = !activeUser.permissions.canViewFinances;
  const pendingTasks = state.tasks.filter(t => t.status === 'pending');
  const lowStockItems = state.inventory.filter(i => i.status === 'low' || i.status === 'out_of_stock');
  const pendingMaintenance = state.maintenance.filter(m => m.status === 'service_required' || m.status === 'scheduled');

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Banner: Household Status & AI Welcome */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-brand-950 via-slate-900 to-navy-900 border border-brand-500/30 p-6 shadow-2xl">
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 rounded-full bg-brand-500/10 blur-3xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Badge variant="brand" size="sm">
                <Sparkles className="w-3 h-3 text-brand-400" />
                Active Household Coordinator
              </Badge>
              {isPlanApplied ? (
                <Badge variant="emerald" size="sm">Coordinated Plan Synced</Badge>
              ) : (
                <Badge variant="amber" size="sm">Awaiting Weekend Plan</Badge>
              )}
            </div>
            <h2 className="text-2xl lg:text-3xl font-black text-white tracking-tight">
              {state.household.name}
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Viewing as <strong className="text-white">{activeUser.name}</strong> ({activeUser.role}). 
              System is actively monitoring 4 members, 6 household domains, and verified medical/governance rules.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('ai_assistant')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-400 hover:to-brand-500 text-white text-xs font-semibold shadow-glow-brand transition-all hover:scale-105"
            >
              <span>Ask HomeOps Assistant</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Live Scenario Alert Banner if plan not yet applied */}
        {!isPlanApplied && (
          <div className="mt-4 p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5 text-amber-200">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Upcoming Challenge Detected:</strong> Mom travels until Friday, 4 guests arrive Saturday, Dad low-salt constraint verified, Grandma Rx low.
              </span>
            </div>
            <button
              onClick={() => {
                setActiveTab('ai_assistant');
                sendAgentMessage(
                  "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."
                );
              }}
              className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs shrink-0 transition-colors"
            >
              Coordinate Now
            </button>
          </div>
        )}
      </div>

      {/* Metrics Row (Connected Domains) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Budget Card */}
        <div 
          onClick={() => setActiveTab('finance')}
          className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-brand-500/40 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold">Weekly Budget</span>
            <div className="p-2 rounded-xl bg-brand-500/10 text-brand-400 group-hover:scale-110 transition-transform">
              <Wallet className="w-4 h-4" />
            </div>
          </div>
          {isRestrictedFinance ? (
            <div>
              <div className="text-base font-bold text-rose-400 flex items-center gap-1">
                <Lock className="w-4 h-4" /> Restricted
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Hidden for {activeUser.role}</p>
            </div>
          ) : (
            <div>
              <div className="text-2xl font-black text-white">
                ₹{state.finance.estimatedRemaining.toLocaleString()}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                <span>Total: ₹{state.finance.weeklyBudget.toLocaleString()}</span>
                <span className="text-brand-400 font-semibold">
                  Planned: ₹{state.finance.plannedExpenses.toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 2. Tasks Metric */}
        <div 
          onClick={() => setActiveTab('tasks')}
          className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-purple-500/40 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold">Pending Tasks</span>
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 group-hover:scale-110 transition-transform">
              <CheckSquare className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {pendingTasks.length}
          </div>
          <div className="text-[11px] text-purple-300 mt-1">
            {isPlanApplied ? '✨ Multi-agent coordinated' : 'Baseline routine chores'}
          </div>
        </div>

        {/* 3. Inventory Metric */}
        <div 
          onClick={() => setActiveTab('inventory')}
          className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-emerald-500/40 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold">Inventory Shortfall</span>
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 group-hover:scale-110 transition-transform">
              <UtensilsCrossed className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {lowStockItems.length} items
          </div>
          <div className="text-[11px] text-emerald-300 mt-1">
            {isPlanApplied ? '🛒 Restock scheduled for Thu' : 'Milk, Produce & Snacks low'}
          </div>
        </div>

        {/* 4. Maintenance Metric */}
        <div 
          onClick={() => setActiveTab('maintenance')}
          className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-amber-500/40 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold">Appliance Status</span>
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 group-hover:scale-110 transition-transform">
              <Wrench className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">
            {pendingMaintenance.length > 0 ? (
              isPlanApplied ? '1 Service Scheduled' : '1 Service Needed'
            ) : 'All Optimal'}
          </div>
          <div className="text-[11px] text-amber-300 mt-1">
            {isPlanApplied ? 'Fri 10 AM (Daikin AMC)' : 'Guest Room AC filter dirty'}
          </div>
        </div>
      </div>

      {/* Main Grid: Tasks & Schedule vs Inventory & Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Tasks & Assignments (2 Cols on lg) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Priority Task Dispatch */}
          <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <CheckSquare className="w-4 h-4 text-brand-400" />
                  Active Household Tasks
                </h3>
                <p className="text-xs text-slate-400">
                  Tasks assigned across family members based on availability
                </p>
              </div>
              <button
                onClick={() => setActiveTab('tasks')}
                className="text-xs text-brand-400 hover:text-brand-300 font-semibold flex items-center gap-1"
              >
                View All <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-2.5">
              {state.tasks.slice(0, 5).map((task) => {
                const isCompleted = task.status === 'completed';
                return (
                  <div
                    key={task.id}
                    className={`p-3 rounded-2xl border transition-all flex items-start justify-between gap-3 ${
                      isCompleted
                        ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                        : task.priority === 'urgent'
                        ? 'bg-rose-950/20 border-rose-500/30'
                        : 'bg-slate-950/60 border-slate-800'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <button
                        onClick={() => toggleTask(task.id)}
                        className={`mt-0.5 w-5 h-5 rounded-lg border flex items-center justify-center transition-colors ${
                          isCompleted
                            ? 'bg-emerald-500 border-emerald-500 text-white'
                            : 'border-slate-700 hover:border-brand-400 bg-slate-900'
                        }`}
                      >
                        {isCompleted && <CheckCircle2 className="w-3.5 h-3.5" />}
                      </button>
                      <div>
                        <h4 className={`text-xs font-semibold ${isCompleted ? 'line-through text-slate-400' : 'text-slate-200'}`}>
                          {task.title}
                        </h4>
                        <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-slate-400">
                          <span className="font-medium text-brand-300">{task.assignedToName}</span>
                          <span>•</span>
                          <span>{task.dueDate}</span>
                          {task.reassigned && (
                            <Badge variant="purple" size="sm">Reassigned from Priya</Badge>
                          )}
                          {task.sourcePlan && (
                            <Badge variant="brand" size="sm">From Agent Plan</Badge>
                          )}
                        </div>
                      </div>
                    </div>

                    <Badge
                      variant={
                        task.priority === 'urgent'
                          ? 'rose'
                          : task.priority === 'high'
                          ? 'amber'
                          : 'default'
                      }
                      size="sm"
                    >
                      {task.priority}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Upcoming Schedule Timeline */}
          <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-sky-400" />
                  Upcoming Household Timeline
                </h3>
                <p className="text-xs text-slate-400">
                  Chronological sequence of family events and planned operations
                </p>
              </div>
              <button
                onClick={() => setActiveTab('schedule')}
                className="text-xs text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-1"
              >
                Full Calendar <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {state.schedule.map((evt) => (
                <div
                  key={evt.id}
                  className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold text-sky-300">{evt.day}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{evt.time}</span>
                    </div>
                    <h4 className="text-xs font-semibold text-slate-200">{evt.title}</h4>
                  </div>
                  <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                    <span>{evt.location}</span>
                    <Badge variant="outline" size="sm">{evt.type}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: AI Insights & Quick Status */}
        <div className="space-y-6">
          {/* AI Household Insights */}
          <div className="p-5 rounded-3xl bg-gradient-to-b from-slate-900 via-navy-900 to-slate-900 border border-purple-500/30 backdrop-blur-md">
            <div className="flex items-center gap-2 text-purple-400 font-bold text-sm mb-3">
              <Sparkles className="w-4 h-4" />
              AI Household Insights
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-2xl bg-purple-950/30 border border-purple-500/20 text-xs text-slate-300">
                <span className="font-bold text-purple-200 block mb-1">Dietary Constraint Guard:</span>
                Dad's low-salt diet directive (DOC-MED-01) is strictly enforced on all upcoming grocery procurement lists.
              </div>

              <div className="p-3 rounded-2xl bg-brand-950/30 border border-brand-500/20 text-xs text-slate-300">
                <span className="font-bold text-brand-200 block mb-1">Mom Travel Balancing:</span>
                Mom's tasks have been distributed to Rajesh and Aarav to keep the household running smoothly.
              </div>

              <div className="p-3 rounded-2xl bg-emerald-950/30 border border-emerald-500/20 text-xs text-slate-300">
                <span className="font-bold text-emerald-200 block mb-1">Financial Buffer:</span>
                {isRestrictedFinance ? (
                  "Budget buffer calculations are verified by Parent Administrators."
                ) : (
                  `₹2,400 remaining balance safely covers unexpected contingencies for the weekend.`
                )}
              </div>
            </div>
          </div>

          {/* Low Stock Pantry Alerts */}
          <div className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 backdrop-blur-md">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <UtensilsCrossed className="w-4 h-4 text-emerald-400" />
                Pantry Restock Alerts
              </h3>
              <button
                onClick={() => setActiveTab('inventory')}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold"
              >
                Pantry
              </button>
            </div>

            <div className="space-y-2">
              {lowStockItems.slice(0, 4).map((item) => (
                <div
                  key={item.id}
                  className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-semibold text-slate-200">{item.name}</span>
                    <p className="text-[10px] text-slate-400">{item.dietaryNote}</p>
                  </div>
                  <Badge
                    variant={item.status === 'out_of_stock' ? 'rose' : 'amber'}
                    size="sm"
                  >
                    {item.quantity}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
