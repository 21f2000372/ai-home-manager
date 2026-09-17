import React, { useState, useEffect } from 'react';
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
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'today', label: 'Today', icon: Sun, category: 'Core' },
  { id: 'assistant', label: 'Assistant', icon: MessageSquare, category: 'Core' },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare, category: 'Core' },
  { id: 'pantry', label: 'Pantry', icon: ShoppingBag, category: 'Core' },
  { id: 'finance', label: 'Budget', icon: Wallet, category: 'Household' },
  { id: 'home', label: 'Appliances', icon: Wrench, category: 'Household' },
  { id: 'schedule', label: 'Schedule', icon: Calendar, category: 'Household' },
  { id: 'members', label: 'Family', icon: Users, category: 'Household' },
];

export const Sidebar = () => {
  const { activeTab, setActiveTab, state, activeUser } = useHousehold();

  // Collapsed state persists in localStorage
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('homeops_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('homeops_sidebar_collapsed', isCollapsed);
  }, [isCollapsed]);

  const isRestrictedFinance = !activeUser.permissions.canViewFinances;
  const pendingTasksCount = state.tasks.filter(t => t.status === 'pending').length;

  return (
    <aside
      className={`hidden md:flex flex-col justify-between shrink-0 bg-[#FAF9F6] dark:bg-[#181B18] border-r border-[#D9D8D2] dark:border-[#2D322E] transition-all duration-200 select-none z-30 ${
        isCollapsed ? 'w-14' : 'w-48 lg:w-52'
      }`}
    >
      {/* Navigation List with tightened spacing */}
      <div className="p-2 space-y-3">
        {/* Core Daily Section */}
        <div>
          {!isCollapsed && (
            <div className="px-2 pb-1 text-[9px] font-bold uppercase tracking-wider text-[#676B68] dark:text-[#969D96]">
              Daily Core
            </div>
          )}
          <div className="space-y-0.5">
            {NAV_ITEMS.filter(i => i.category === 'Core').map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              const isTasks = item.id === 'tasks';

              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  className={`w-full h-9 flex items-center gap-2.5 px-2.5 rounded-lg text-xs transition-all duration-150 relative group ${
                    isActive
                      ? 'bg-[#5E9278]/15 dark:bg-[#5E9278]/20 text-[#2f5542] dark:text-[#9BCDB4] font-semibold border-l-2 border-[#5E9278]'
                      : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 font-medium'
                  } ${isCollapsed ? 'justify-center px-0' : 'justify-between'}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#5E9278] dark:text-[#9BCDB4]' : ''}`} />
                    {!isCollapsed && <span className="truncate">{item.label}</span>}
                  </div>

                  {/* Task counter badge */}
                  {!isCollapsed && isTasks && pendingTasksCount > 0 && (
                    <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono shrink-0 ${
                      isActive 
                        ? 'bg-[#5E9278]/25 text-[#2f5542] dark:text-[#9BCDB4]' 
                        : 'bg-black/5 dark:bg-white/10 text-[#676B68] dark:text-[#969D96]'
                    }`}>
                      {pendingTasksCount}
                    </span>
                  )}

                  {/* Collapsed notification dot */}
                  {isCollapsed && isTasks && pendingTasksCount > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-[#D19A4C]" />
                  )}

                  {/* Tooltip for collapsed mode */}
                  {isCollapsed && (
                    <div className="absolute left-full ml-2 px-2.5 py-1 bg-[#171918] dark:bg-[#EFF1EC] text-[#FAF9F6] dark:text-[#171918] text-xs font-medium rounded-md shadow-elevated opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap">
                      {item.label}
                      {isTasks && pendingTasksCount > 0 && ` (${pendingTasksCount})`}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Household Section */}
        <div>
          {!isCollapsed && (
            <div className="px-2 pb-1 text-[9px] font-bold uppercase tracking-wider text-[#676B68] dark:text-[#969D96]">
              Household
            </div>
          )}
          <div className="space-y-0.5">
            {NAV_ITEMS.filter(i => i.category === 'Household' && (i.id !== 'finance' || !isRestrictedFinance)).map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  className={`w-full h-9 flex items-center gap-2.5 px-2.5 rounded-lg text-xs transition-all duration-150 relative group ${
                    isActive
                      ? 'bg-[#5E9278]/15 dark:bg-[#5E9278]/20 text-[#2f5542] dark:text-[#9BCDB4] font-semibold border-l-2 border-[#5E9278]'
                      : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 font-medium'
                  } ${isCollapsed ? 'justify-center px-0' : 'justify-between'}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#5E9278] dark:text-[#9BCDB4]' : ''}`} />
                    {!isCollapsed && <span className="truncate">{item.label}</span>}
                  </div>

                  {/* Tooltip for collapsed mode */}
                  {isCollapsed && (
                    <div className="absolute left-full ml-2 px-2.5 py-1 bg-[#171918] dark:bg-[#EFF1EC] text-[#FAF9F6] dark:text-[#171918] text-xs font-medium rounded-md shadow-elevated opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap">
                      {item.label}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Sidebar Footer: Compact Collapse Toggle */}
      <div className="p-2 border-t border-[#D9D8D2] dark:border-[#2D322E]">
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`w-full h-8 flex items-center gap-2 px-2 rounded-lg text-xs font-medium text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors ${
            isCollapsed ? 'justify-center' : 'justify-start'
          }`}
          title={isCollapsed ? 'Expand sidebar' : 'Minimize sidebar'}
        >
          {isCollapsed ? (
            <PanelLeftOpen className="w-3.5 h-3.5 shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="w-3.5 h-3.5 shrink-0" />
              <span className="text-[11px]">Minimize</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
