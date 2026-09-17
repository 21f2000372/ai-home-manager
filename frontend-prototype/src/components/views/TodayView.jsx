import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { WeekendPlanModal } from '../modals/WeekendPlanModal';
import { 
  Sun, 
  CheckCircle2, 
  ArrowRight, 
  Wallet, 
  ShoppingBag, 
  Wrench, 
  Calendar, 
  Lock, 
  Send,
  Sparkles
} from 'lucide-react';

export const TodayView = () => {
  const { 
    state, 
    activeUser, 
    toggleTask, 
    setActiveTab, 
    sendAgentMessage, 
    isPlanApplied 
  } = useHousehold();

  const [quickInput, setQuickInput] = useState('');
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);

  const handleQuickSubmit = (e) => {
    e.preventDefault();
    if (!quickInput.trim()) return;
    setActiveTab('assistant');
    sendAgentMessage(quickInput);
    setQuickInput('');
  };

  const isRestrictedFinance = !activeUser.permissions.canViewFinances;
  const pendingTasks = state.tasks.filter(t => t.status === 'pending');
  const lowStock = state.inventory.filter(i => i.status === 'low' || i.status === 'out_of_stock');

  return (
    <div className="space-y-4 sm:space-y-5 max-w-5xl mx-auto animate-fade-in pb-8">
      {/* Daily Briefing Card - Compact & Clean */}
      <Card className="p-4 sm:p-5 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1 max-w-2xl">
            <div className="flex items-center gap-2">
              {isPlanApplied ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#3d6551] dark:text-[#9BCDB4] bg-[#5E9278]/15 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#5E9278] animate-pulse" />
                  Active Coordination
                </span>
              ) : (
                <span className="text-[10px] font-medium text-[#676B68] dark:text-[#969D96] uppercase tracking-wider">
                  Morning Briefing
                </span>
              )}
              <span className="text-xs text-[#676B68] dark:text-[#969D96]">
                • {activeUser.name.split(' ')[0]}'s Profile
              </span>
            </div>

            <h2 className="text-base sm:text-lg font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              {isPlanApplied ? "Weekend plan coordinated and active." : "4 items require attention before the weekend."}
            </h2>

            <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-relaxed">
              {isPlanApplied ? (
                "Priya's travel tasks reassigned to Rajesh. Thursday grocery procurement scheduled with Dad's low-salt items. Daikin AC service booked for Friday 10 AM."
              ) : (
                "Mom travels until Friday evening, 4 relatives arrive Saturday, Dad's low-salt diet is active, and Grandma's prescription is due."
              )}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsPlanModalOpen(true)}
              className="h-8 text-xs font-semibold"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#5E9278]" />
              <span>{isPlanApplied ? "Review Approvals" : "Coordinate Plan"}</span>
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={() => setActiveTab('assistant')}
              className="h-8 text-xs font-semibold"
            >
              <span>Ask Assistant</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>

        {/* Compact Quick Natural Language Input */}
        <form onSubmit={handleQuickSubmit} className="mt-3.5 pt-3 border-t border-[#D9D8D2]/60 dark:border-[#2D322E]/60 flex items-center gap-2">
          <input
            type="text"
            value={quickInput}
            onChange={(e) => setQuickInput(e.target.value)}
            placeholder={`Tell HomeOps what changed or ask what to do (e.g. "Plan for this weekend")...`}
            className="flex-1 bg-black/5 dark:bg-white/5 border border-[#D9D8D2] dark:border-[#2D322E] rounded-lg px-3 py-1.5 text-xs text-[#171918] dark:text-[#EFF1EC] placeholder-[#676B68] outline-none focus:border-[#5E9278] h-9"
          />
          <Button type="submit" variant="primary" size="sm" disabled={!quickInput.trim()} className="h-9 px-3">
            <Send className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Ask</span>
          </Button>
        </form>
      </Card>

      {/* Summary Cards: 2x2 Grid on Mobile, 4-col Grid on Desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5">
        {/* Card 1: Budget for Parents, or My Responsibilities for Teens/Guests */}
        <Card 
          onClick={() => setActiveTab(isRestrictedFinance ? 'tasks' : 'finance')}
          className="p-3 sm:p-3.5 flex flex-col justify-between group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#676B68] dark:text-[#969D96] mb-1">
            <span className="text-[11px] font-medium">
              {isRestrictedFinance ? "My Responsibilities" : "Weekly Budget"}
            </span>
            {isRestrictedFinance ? (
              <CheckCircle2 className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100 text-[#5E9278]" />
            ) : (
              <Wallet className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100" />
            )}
          </div>
          {isRestrictedFinance ? (
            <div>
              <div className="text-base sm:text-lg font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
                {state.tasks.filter(t => t.assignedTo === activeUser.id && t.status === 'pending').length} tasks
              </div>
              <p className="text-[10px] text-[#676B68] dark:text-[#969D96] mt-0.5 truncate">
                Assigned to {activeUser.name.split(' ')[0]}
              </p>
            </div>
          ) : (
            <div>
              <div className="text-base sm:text-lg font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
                ₹{state.finance.estimatedRemaining?.toLocaleString()}
              </div>
              <p className="text-[10px] text-[#676B68] dark:text-[#969D96] mt-0.5 truncate">
                {isPlanApplied ? "₹2,400 uncommitted buffer" : "of ₹5,000 allocated"}
              </p>
            </div>
          )}
        </Card>

        {/* Card 2: Tasks */}
        <Card 
          onClick={() => setActiveTab('tasks')}
          className="p-3 sm:p-3.5 flex flex-col justify-between group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#676B68] dark:text-[#969D96] mb-1">
            <span className="text-[11px] font-medium">Pending Chores</span>
            <CheckCircle2 className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100" />
          </div>
          <div>
            <div className="text-base sm:text-lg font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              {pendingTasks.length} tasks
            </div>
            <p className="text-[10px] text-[#676B68] dark:text-[#969D96] mt-0.5 truncate">
              {isPlanApplied ? "Distributed to available family" : "Routine household chores"}
            </p>
          </div>
        </Card>

        {/* Card 3: Pantry Low Stock */}
        <Card 
          onClick={() => setActiveTab('pantry')}
          className="p-3 sm:p-3.5 flex flex-col justify-between group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#676B68] dark:text-[#969D96] mb-1">
            <span className="text-[11px] font-medium">Pantry Restock</span>
            <ShoppingBag className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100" />
          </div>
          <div>
            <div className="text-base sm:text-lg font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              {lowStock.length} items
            </div>
            <p className="text-[10px] text-[#676B68] dark:text-[#969D96] mt-0.5 truncate">
              {isPlanApplied ? "Thursday restock scheduled" : "Milk, veggies & snacks low"}
            </p>
          </div>
        </Card>

        {/* Card 4: Maintenance */}
        <Card 
          onClick={() => setActiveTab('home')}
          className="p-3 sm:p-3.5 flex flex-col justify-between group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#676B68] dark:text-[#969D96] mb-1">
            <span className="text-[11px] font-medium">Guest Room AC</span>
            <Wrench className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100" />
          </div>
          <div>
            <div className="text-xs sm:text-sm font-bold tracking-tight truncate text-[#171918] dark:text-[#EFF1EC]">
              {isPlanApplied ? "Service: Fri 10 AM" : "Service Needed"}
            </div>
            <p className="text-[10px] text-[#676B68] dark:text-[#969D96] mt-0.5 truncate">
              {isPlanApplied ? "Daikin AMC confirmed" : "Filter tune-up before guests"}
            </p>
          </div>
        </Card>
      </div>

      {/* Main Grid: Stack vertically on mobile, 2:1 column on desktop */}
      <div className="flex flex-col lg:grid lg:grid-cols-3 gap-4 sm:gap-5">
        {/* Left: Immediate Tasks (2 cols on lg) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC]">
              Immediate Household Tasks
            </h3>
            <button
              onClick={() => setActiveTab('tasks')}
              className="text-xs font-medium text-[#5E9278] dark:text-[#9BCDB4] hover:underline"
            >
              View all tasks →
            </button>
          </div>

          <div className="space-y-2">
            {state.tasks.slice(0, 4).map((task) => {
              const isCompleted = task.status === 'completed';
              return (
                <Card
                  key={task.id}
                  className={`p-3 flex items-start justify-between gap-3 transition-all ${
                    isCompleted ? 'opacity-60 bg-black/5 dark:bg-white/5' : ''
                  }`}
                >
                  <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    {/* 44px touch target button for task checkbox */}
                    <button
                      onClick={() => toggleTask(task.id)}
                      aria-label={isCompleted ? "Mark pending" : "Mark done"}
                      className="p-2 -m-2 min-h-[44px] min-w-[44px] flex items-center justify-center shrink-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] rounded-lg"
                    >
                      <span className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                        isCompleted
                          ? 'bg-[#5E9278] border-[#5E9278] text-white'
                          : 'border-[#D9D8D2] dark:border-[#2D322E] hover:border-[#5E9278]'
                      }`}>
                        {isCompleted && <CheckCircle2 className="w-3 h-3" />}
                      </span>
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className={`text-xs font-semibold truncate ${isCompleted ? 'line-through text-[#676B68]' : 'text-[#171918] dark:text-[#EFF1EC]'}`}>
                        {task.title}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-[#676B68] dark:text-[#969D96]">
                        <span className="font-medium text-[#171918] dark:text-[#EFF1EC] truncate max-w-[100px] sm:max-w-none">
                          {task.assignedToName}
                        </span>
                        <span>•</span>
                        <span>{task.dueDate}</span>
                        {task.reassigned && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-[#D19A4C]/15 text-[#8f5e1b] dark:text-[#f0be78] font-medium shrink-0">
                            Reassigned
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                    task.priority === 'urgent'
                      ? 'bg-[#B96359]/15 text-[#B96359]'
                      : task.priority === 'high'
                      ? 'bg-[#D19A4C]/15 text-[#D19A4C]'
                      : 'bg-black/5 dark:bg-white/5 text-[#676B68] dark:text-[#969D96]'
                  }`}>
                    {task.priority}
                  </span>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Right: Upcoming Timeline & Dietary Note */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC]">
              Upcoming This Week
            </h3>
            <button
              onClick={() => setActiveTab('schedule')}
              className="text-xs font-medium text-[#5E9278] dark:text-[#9BCDB4] hover:underline"
            >
              Agenda →
            </button>
          </div>

          <Card className="p-3 sm:p-3.5 space-y-2.5">
            {state.schedule.slice(0, 3).map((evt) => (
              <div key={evt.id} className="pb-2 border-b border-[#D9D8D2]/60 dark:border-[#2D322E]/60 last:border-0 last:pb-0">
                <div className="flex items-center justify-between text-[11px] mb-0.5">
                  <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{evt.day}</span>
                  <span className="text-[#676B68] dark:text-[#969D96] font-mono text-[10px]">{evt.time}</span>
                </div>
                <div className="text-xs text-[#676B68] dark:text-[#969D96] truncate">
                  {evt.title}
                </div>
              </div>
            ))}
          </Card>

          {/* Active Family Constraint Note - Clean Minimal Card */}
          <Card className="p-3 sm:p-3.5 bg-black/5 dark:bg-white/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#676B68] dark:text-[#969D96] block mb-1">
              Active Household Rule
            </span>
            <p className="text-xs text-[#171918] dark:text-[#EFF1EC] leading-relaxed">
              Dad's verified low-salt diet directive (Dr. Verma) is automatically enforced on all grocery orders and meal plans.
            </p>
          </Card>
        </div>
      </div>

      {/* Dedicated Weekend Plan HITL Modal */}
      <WeekendPlanModal
        isOpen={isPlanModalOpen}
        onClose={() => setIsPlanModalOpen(false)}
      />
    </div>
  );
};
