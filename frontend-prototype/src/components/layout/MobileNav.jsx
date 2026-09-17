import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { 
  Sun, 
  MessageSquare, 
  CheckSquare, 
  ShoppingBag, 
  Grid
} from 'lucide-react';

export const MobileNav = ({ onOpenDrawer }) => {
  const { activeTab, setActiveTab, state } = useHousehold();

  const pendingTasksCount = state.tasks.filter(t => t.status === 'pending').length;

  const CORE_MOBILE_TABS = [
    { id: 'today', label: 'Today', icon: Sun },
    { id: 'assistant', label: 'Assistant', icon: MessageSquare },
    { id: 'tasks', label: 'Tasks', icon: CheckSquare },
    { id: 'pantry', label: 'Pantry', icon: ShoppingBag },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#FAF9F6]/95 dark:bg-[#181B18]/95 backdrop-blur-md border-t border-[#D9D8D2] dark:border-[#2D322E] px-2 py-1 transition-colors pb-[max(0.375rem,env(safe-area-inset-bottom))]">
      <div className="flex items-center justify-around">
        {CORE_MOBILE_TABS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          const isTasks = item.id === 'tasks';

          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`min-h-[46px] min-w-[52px] flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all relative active:scale-95 ${
                isActive
                  ? 'text-[#2F5542] dark:text-[#9BCDB4] bg-[#5E9278]/12 dark:bg-[#5E9278]/20 font-semibold'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC]'
              }`}
            >
              <div className="relative">
                <Icon className="w-4.5 h-4.5" />
                {isTasks && pendingTasksCount > 0 && (
                  <span className="absolute -top-1 -right-2.5 w-4 h-4 rounded-full bg-[#D19A4C] text-white text-[9px] font-mono flex items-center justify-center font-bold">
                    {pendingTasksCount}
                  </span>
                )}
              </div>
              <span className="text-[10px] mt-0.5 tracking-tight">{item.label}</span>
              <span className={`w-1 h-1 rounded-full mt-0.5 transition-opacity ${
                isActive ? 'bg-[#5E9278] dark:bg-[#9BCDB4] opacity-100' : 'opacity-0'
              }`} />
            </button>
          );
        })}

        {/* 5th Tab: "More" opens the mobile drawer for the remaining items */}
        <button
          onClick={onOpenDrawer}
          className="min-h-[46px] min-w-[52px] flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] active:scale-95"
        >
          <Grid className="w-4.5 h-4.5" />
          <span className="text-[10px] mt-0.5 tracking-tight">More</span>
          <span className="w-1 h-1 mt-0.5 opacity-0" />
        </button>
      </div>
    </nav>
  );
};
