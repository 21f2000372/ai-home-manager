import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { 
  Sun, 
  MessageSquare, 
  CheckSquare, 
  ShoppingBag, 
  Wallet, 
  Wrench, 
  Calendar, 
  Users,
  Sparkles
} from 'lucide-react';

export const NAV_ITEMS = [
  { id: 'today', label: 'Today', icon: Sun },
  { id: 'assistant', label: 'Assistant', icon: MessageSquare, highlight: true },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },
  { id: 'pantry', label: 'Pantry', icon: ShoppingBag },
  { id: 'finance', label: 'Budget', icon: Wallet },
  { id: 'home', label: 'Appliances', icon: Wrench },
  { id: 'schedule', label: 'Schedule', icon: Calendar },
  { id: 'members', label: 'Family', icon: Users },
];

export const Navigation = () => {
  const { activeTab, setActiveTab, state, activeUser } = useHousehold();

  const isRestrictedFinance = !activeUser.permissions.canViewFinances;
  const pendingTasksCount = state.tasks.filter(t => t.status === 'pending').length;

  return (
    <nav className="w-full bg-[#FAF9F6] dark:bg-[#181B18] border-b border-[#D9D8D2] dark:border-[#2D322E] px-4 sm:px-6 transition-colors">
      <div className="max-w-7xl mx-auto flex items-center gap-1 sm:gap-2 overflow-x-auto py-2 scrollbar-none">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          const isFinance = item.id === 'finance';
          const isTasks = item.id === 'tasks';

          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex items-center gap-2 px-3 py-1.5 sm:px-3.5 sm:py-2 rounded-xl text-xs sm:text-sm font-medium whitespace-nowrap transition-all duration-150 ${
                isActive
                  ? 'bg-[#5E9278] text-white shadow-sm font-semibold'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>

              {isTasks && pendingTasksCount > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  isActive ? 'bg-white/20 text-white' : 'bg-black/5 dark:bg-white/10 text-[#676B68] dark:text-[#969D96]'
                }`}>
                  {pendingTasksCount}
                </span>
              )}

              {isFinance && isRestrictedFinance && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[#B96359]/15 text-[#B96359] font-mono">
                  Hidden
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
