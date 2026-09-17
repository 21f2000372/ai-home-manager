import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../ui/Badge';
import { 
  X, 
  Wallet, 
  Wrench, 
  Calendar, 
  Users, 
  Sun, 
  Moon, 
  RotateCcw, 
  Sparkles,
  Lock,
  ChevronRight,
  Home,
  Globe,
  LogOut
} from 'lucide-react';

export const MobileDrawer = ({ isOpen, onClose }) => {
  const { 
    activeTab, 
    setActiveTab, 
    state, 
    activeUser, 
    switchUser, 
    theme, 
    toggleTheme, 
    resetToBaseline,
    sendAgentMessage,
    navigateTo,
    logout
  } = useHousehold();

  if (!isOpen) return null;

  const isRestrictedFinance = !activeUser.permissions.canViewFinances;

  const ALL_REMAINING_ITEMS = [
    { id: 'finance', label: 'Budget & Expenses', icon: Wallet, desc: 'Weekly ₹5,000 envelope progress' },
    { id: 'home', label: 'Appliances & Maintenance', icon: Wrench, desc: 'AC, fridge & purifier warranties' },
    { id: 'schedule', label: 'Schedule & Agenda', icon: Calendar, desc: 'Weekly timeline and guest arrivals' },
    { id: 'members', label: 'Family & Privacy Roles', icon: Users, desc: 'Member profiles and permissions' },
  ];

  const REMAINING_ITEMS = ALL_REMAINING_ITEMS.filter(item => item.id !== 'finance' || !isRestrictedFinance);

  const handleSelectTab = (tabId) => {
    setActiveTab(tabId);
    onClose();
  };

  const handleRunScenario = () => {
    onClose();
    setActiveTab('assistant');
    sendAgentMessage(
      "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."
    );
  };

  return (
    <div className="md:hidden fixed inset-0 z-50 flex animate-fade-in">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity" 
        onClick={onClose} 
      />

      {/* Slide-out Drawer Panel */}
      <div className="relative ml-auto w-full max-w-xs h-full bg-[#FAF9F6] dark:bg-[#181B18] border-l border-[#D9D8D2] dark:border-[#2D322E] p-5 shadow-elevated dark:shadow-elevated-dark flex flex-col justify-between overflow-y-auto z-10 transition-colors">
        <div className="space-y-6">
          {/* Drawer Header */}
          <div className="flex items-center justify-between pb-3 border-b border-[#D9D8D2] dark:border-[#2D322E]">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#5E9278] text-white flex items-center justify-center">
                <Home className="w-4 h-4" />
              </div>
              <span className="font-bold text-sm text-[#171918] dark:text-[#EFF1EC]">
                Household Menu
              </span>
            </div>

            <button
              onClick={onClose}
              className="p-2 min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg text-[#676B68] hover:text-[#171918] dark:text-[#969D96] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Active Profile Snapshot */}
          <div className="p-3 rounded-2xl bg-black/5 dark:bg-white/5 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#676B68] dark:text-[#969D96]">Active Profile</span>
              <Badge variant="primary" size="xs">{activeUser.clearance.split(' ')[0]}</Badge>
            </div>

            <div className="flex items-center gap-2.5">
              <span className="text-2xl">{activeUser.avatar}</span>
              <div>
                <div className="font-semibold text-xs text-[#171918] dark:text-[#EFF1EC]">
                  {activeUser.name}
                </div>
                <div className="text-[10px] text-[#676B68] dark:text-[#969D96]">
                  {activeUser.role}
                </div>
              </div>
            </div>

            {/* Quick Member Switcher */}
            <div className="pt-2 border-t border-[#D9D8D2]/50 dark:border-[#2D322E]/50 flex items-center gap-1.5 overflow-x-auto">
              {state.members.map((m) => (
                <button
                  key={m.id}
                  onClick={() => switchUser(m.id)}
                  className={`min-h-[38px] min-w-[38px] flex items-center justify-center p-1 rounded-lg text-lg transition-transform active:scale-95 ${
                    m.id === activeUser.id ? 'scale-105 bg-[#5E9278]/20 ring-1.5 ring-[#5E9278]' : 'opacity-70 hover:opacity-100'
                  }`}
                  title={m.name}
                >
                  {m.avatar}
                </button>
              ))}
            </div>
          </div>

          {/* Remaining Household Items */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#676B68] dark:text-[#969D96] px-1">
              Household Domains
            </span>

            <div className="space-y-1">
              {REMAINING_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                const isFinance = item.id === 'finance';

                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelectTab(item.id)}
                    className={`w-full min-h-[46px] flex items-center justify-between p-2.5 rounded-xl text-left transition-all active:scale-[0.99] ${
                      isActive
                        ? 'bg-[#5E9278]/12 dark:bg-[#5E9278]/20 border border-[#5E9278] text-[#2F5542] dark:text-[#9BCDB4] font-medium'
                        : 'bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] hover:border-[#5E9278]'
                    }`}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${isActive ? 'text-[#5E9278] dark:text-[#9BCDB4]' : 'text-[#676B68] dark:text-[#969D96]'}`} />
                      <div className="min-w-0">
                        <div className="text-xs font-semibold">{item.label}</div>
                        <div className={`text-[10px] truncate ${isActive ? 'text-[#2F5542]/80 dark:text-[#9BCDB4]/80' : 'text-[#676B68] dark:text-[#969D96]'}`}>
                          {item.desc}
                        </div>
                      </div>
                    </div>

                    {isFinance && isRestrictedFinance ? (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[#B96359]/20 text-[#B96359] font-mono shrink-0">
                        Hidden
                      </span>
                    ) : (
                      <ChevronRight className={`w-3.5 h-3.5 shrink-0 opacity-60 ${isActive ? 'text-[#5E9278] dark:text-[#9BCDB4]' : ''}`} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Quick Action Shortcut */}
          <div className="p-3 rounded-2xl border border-[#5E9278]/30 bg-[#5E9278]/5 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[#5E9278] dark:text-[#9BCDB4]">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Weekend Scenario</span>
            </div>
            <p className="text-[11px] text-[#676B68] dark:text-[#969D96] leading-snug">
              Mom away, Dad low-salt, Grandma Rx, 4 guests Saturday, ₹5,000 budget.
            </p>
            <button
              onClick={handleRunScenario}
              className="w-full min-h-[40px] flex items-center justify-center py-1.5 rounded-lg bg-[#5E9278] hover:bg-[#4D7A64] text-white text-xs font-semibold transition-colors shadow-xs"
            >
              Simulate in Assistant →
            </button>
          </div>

          {/* Landing & Sign Out links */}
          <div className="pt-2 border-t border-[#D9D8D2] dark:border-[#2D322E] space-y-1">
            <button
              onClick={() => {
                onClose();
                navigateTo('landing');
              }}
              className="w-full min-h-[40px] flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <Globe className="w-4 h-4 text-[#5E9278]" />
              <span>Product Overview</span>
            </button>
            <button
              onClick={() => {
                onClose();
                logout();
              }}
              className="w-full min-h-[40px] flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-[#B96359] hover:bg-[#B96359]/10 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out Household</span>
            </button>
          </div>
        </div>

        {/* Drawer Footer (Theme Toggle & Reset) */}
        <div className="pt-4 border-t border-[#D9D8D2] dark:border-[#2D322E] flex items-center justify-between text-xs text-[#676B68] dark:text-[#969D96]">
          <button
            onClick={toggleTheme}
            className="min-h-[44px] flex items-center gap-2 px-2.5 py-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-xs font-medium"
          >
            {theme === 'light' ? (
              <>
                <Moon className="w-4 h-4" />
                <span>Dark Mode</span>
              </>
            ) : (
              <>
                <Sun className="w-4 h-4 text-[#D19A4C]" />
                <span>Light Mode</span>
              </>
            )}
          </button>

          <button
            onClick={() => {
              resetToBaseline();
              onClose();
            }}
            className="min-h-[44px] flex items-center gap-1.5 px-2.5 py-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-xs font-medium text-[#B96359]"
            title="Reset to clean baseline"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
        </div>
      </div>
    </div>
  );
};
