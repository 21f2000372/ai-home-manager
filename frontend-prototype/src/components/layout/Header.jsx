import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../ui/Badge';
import { WeekendPlanModal } from '../modals/WeekendPlanModal';
import { 
  Home, 
  Sun, 
  Moon, 
  ChevronDown, 
  RotateCcw, 
  Lock,
  Sparkles,
  Menu,
  Globe,
  LogOut
} from 'lucide-react';

export const Header = ({ onOpenMobileDrawer }) => {
  const { 
    state, 
    activeUser, 
    switchUser, 
    resetToBaseline, 
    theme, 
    toggleTheme, 
    isPlanApplied,
    sendAgentMessage,
    setActiveTab,
    isProcessing,
    navigateTo,
    logout
  } = useHousehold();

  const [isMemberMenuOpen, setIsMemberMenuOpen] = useState(false);
  const [isWeekendPlanOpen, setIsWeekendPlanOpen] = useState(false);

  const handleRunExample = () => {
    setActiveTab('assistant');
    sendAgentMessage(
      "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week."
    );
  };

  return (
    <header className="sticky top-0 z-40 bg-[#FAF9F6] dark:bg-[#181B18] border-b border-[#D9D8D2] dark:border-[#2D322E] px-3 sm:px-5 py-2.5 transition-colors">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        {/* Left: Simplified Clean Brand & Household Hierarchy */}
        <div 
          onClick={() => setActiveTab('today')}
          className="flex items-center gap-2.5 cursor-pointer group select-none"
        >
          <div className="w-8 h-8 rounded-lg bg-[#5E9278] text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform shrink-0">
            <Home className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm sm:text-base font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              HomeOps
            </span>
            <span className="text-[#676B68] dark:text-[#969D96] text-xs font-normal hidden xs:inline">
              /
            </span>
            <span className="text-xs text-[#676B68] dark:text-[#969D96] font-medium hidden xs:inline truncate max-w-[120px] sm:max-w-none">
              Sharma Residence
            </span>
            {isPlanApplied && (
              <button
                onClick={() => setIsWeekendPlanOpen(true)}
                className="hidden sm:inline-flex items-center gap-1 text-[10px] font-semibold text-[#3d6551] dark:text-[#9BCDB4] bg-[#5E9278]/15 hover:bg-[#5E9278]/25 px-2 py-0.5 rounded-full transition-colors cursor-pointer"
                title="Review multi-agent coordinated plan"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#5E9278] animate-pulse" />
                Active Plan
              </button>
            )}
          </div>
        </div>

        {/* Right: Compact Controls & Profile Switcher */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Product Overview / Landing Page Link */}
          <button
            onClick={() => navigateTo('landing')}
            className="hidden lg:inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 border border-transparent hover:border-[#D9D8D2] dark:hover:border-[#2D322E] transition-colors"
            title="View Product Overview & Architecture"
          >
            <Globe className="w-3.5 h-3.5 text-[#5E9278]" />
            <span>Product</span>
          </button>

          {/* Quick Scenario Runner (Desktop & Mobile) */}
          <button
            onClick={() => setIsWeekendPlanOpen(true)}
            className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium text-[#2f5542] dark:text-[#9BCDB4] bg-[#5E9278]/10 hover:bg-[#5E9278]/20 border border-[#5E9278]/25 transition-colors"
            title="Coordinate or review this weekend's plan with Human-in-the-Loop approvals"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#5E9278] dark:text-[#9BCDB4]" />
            <span className="hidden sm:inline">Weekend Plan</span>
            <span className="sm:hidden">Plan</span>
          </button>

          {/* Theme Toggle (Light / Dark) */}
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            title={theme === 'light' ? 'Switch to Dark mode' : 'Switch to Light mode'}
          >
            {theme === 'light' ? (
              <Moon className="w-3.5 h-3.5" />
            ) : (
              <Sun className="w-3.5 h-3.5 text-[#D19A4C]" />
            )}
          </button>

          {/* Reset Baseline Button */}
          <button
            onClick={resetToBaseline}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            title="Reset to clean baseline"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Member Profile Switcher Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsMemberMenuOpen(!isMemberMenuOpen)}
              className="flex items-center gap-1.5 h-8 pl-1.5 pr-2 rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] hover:border-[#5E9278] transition-all text-left"
            >
              <span className="text-base leading-none">{activeUser.avatar}</span>
              <span className="text-xs font-medium text-[#171918] dark:text-[#EFF1EC] hidden sm:inline truncate max-w-[80px]">
                {activeUser.name.split(' ')[0]}
              </span>
              {!activeUser.permissions.canViewFinances && (
                <Lock className="w-2.5 h-2.5 text-[#B96359]" title="Financial view restricted" />
              )}
              <ChevronDown className="w-3 h-3 text-[#676B68] dark:text-[#969D96]" />
            </button>

            {/* Member Dropdown Menu */}
            {isMemberMenuOpen && (
              <>
                <div 
                  className="fixed inset-0 z-40" 
                  onClick={() => setIsMemberMenuOpen(false)} 
                />
                <div className="absolute right-0 mt-1.5 w-64 bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] rounded-xl shadow-elevated dark:shadow-elevated-dark p-1.5 z-50 animate-fade-in">
                  <div className="px-2.5 py-1.5 border-b border-[#D9D8D2] dark:border-[#2D322E]">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#676B68] dark:text-[#969D96]">
                      Switch Profile
                    </span>
                  </div>

                  <div className="py-1 space-y-0.5 max-h-56 overflow-y-auto">
                    {state.members.map((member) => {
                      const isSelected = member.id === activeUser.id;
                      return (
                        <button
                          key={member.id}
                          onClick={() => {
                            switchUser(member.id);
                            setIsMemberMenuOpen(false);
                          }}
                          className={`w-full flex items-center gap-2 p-1.5 rounded-lg text-left transition-colors ${
                            isSelected
                              ? 'bg-[#5E9278]/15 text-[#171918] dark:text-white font-medium'
                              : 'hover:bg-black/5 dark:hover:bg-white/5 text-[#171918] dark:text-[#EFF1EC]'
                          }`}
                        >
                          <span className="text-lg leading-none">{member.avatar}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between text-xs font-medium">
                              <span className="truncate">{member.name}</span>
                              <span className="text-[9px] text-[#676B68] dark:text-[#969D96] font-mono">
                                {member.clearance.split(' ')[0]}
                              </span>
                            </div>
                            <div className="text-[10px] text-[#676B68] dark:text-[#969D96] truncate">
                              {member.role}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {/* Navigation Links inside Dropdown */}
                  <div className="pt-1.5 mt-1 border-t border-[#D9D8D2] dark:border-[#2D322E] space-y-0.5">
                    <button
                      onClick={() => {
                        setIsMemberMenuOpen(false);
                        navigateTo('landing');
                      }}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <Globe className="w-3.5 h-3.5 text-[#5E9278]" />
                      <span>Product Overview</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsMemberMenuOpen(false);
                        logout();
                      }}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[#B96359] hover:bg-[#B96359]/10 transition-colors"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Mobile Hamburger Menu Drawer Button */}
          <button
            onClick={onOpenMobileDrawer}
            className="md:hidden w-8 h-8 flex items-center justify-center rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] text-[#171918] dark:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            title="Open navigation menu"
          >
            <Menu className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Weekend Plan HITL Approval Modal */}
      <WeekendPlanModal
        isOpen={isWeekendPlanOpen}
        onClose={() => setIsWeekendPlanOpen(false)}
      />
    </header>
  );
};
