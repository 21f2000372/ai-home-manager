import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { 
  Home, 
  ArrowRight, 
  Sun, 
  Moon, 
  CheckSquare, 
  ShoppingBag, 
  Wallet, 
  Users, 
  Sparkles,
  ShieldCheck
} from 'lucide-react';

export const LandingPageView = () => {
  const { 
    navigateTo, 
    theme, 
    toggleTheme 
  } = useHousehold();

  return (
    <div className="min-h-screen bg-[#FAF9F6] dark:bg-[#101210] text-[#171918] dark:text-[#EFF1EC] transition-colors selection:bg-[#5E9278]/25">
      {/* Clean Minimal Header */}
      <header className="sticky top-0 z-50 bg-[#FAF9F6]/90 dark:bg-[#101210]/90 backdrop-blur-md border-b border-[#D9D8D2]/70 dark:border-[#2D322E] px-4 sm:px-8 py-3.5 transition-colors">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
          {/* Brand Logo */}
          <div 
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="flex items-center gap-2.5 cursor-pointer select-none group"
          >
            <div className="w-8 h-8 rounded-xl bg-[#5E9278] text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
              <Home className="w-4 h-4" />
            </div>
            <span className="text-base font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              HomeOps
            </span>
          </div>

          {/* Right Nav Controls */}
          <div className="flex items-center gap-3">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] transition-colors"
              title={theme === 'light' ? 'Switch to Dark mode' : 'Switch to Light mode'}
            >
              {theme === 'light' ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5 text-[#D19A4C]" />}
            </button>

            {/* Sign In Link */}
            <button
              onClick={() => navigateTo('login')}
              className="text-xs font-semibold text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] px-2.5 py-1.5 transition-colors"
            >
              Sign In
            </button>

            {/* Launch Header Button */}
            <button
              onClick={() => navigateTo('app', 'today')}
              className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-lg text-xs font-semibold bg-[#5E9278] hover:bg-[#4D7A64] text-white shadow-xs transition-all active:scale-95"
            >
              <span>Launch</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* HERO SECTION — Minimalist, Consumer-Friendly */}
      <section className="relative pt-16 sm:pt-24 pb-16 px-4 sm:px-8 max-w-4xl mx-auto text-center">
        <div className="space-y-6 animate-fade-in">
          {/* Simple Clean Title */}
          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC] leading-[1.12]">
            HomeOps — The Operating System for the Modern Family
          </h1>

          {/* Concise Subtitle */}
          <p className="text-base sm:text-lg text-[#676B68] dark:text-[#969D96] max-w-2xl mx-auto font-normal leading-relaxed">
            A unified coordinator for household chores, groceries, and budgets.
          </p>

          {/* Single Primary CTA — Centered, Prominent & Large */}
          <div className="pt-4 flex justify-center">
            <button
              onClick={() => navigateTo('app', 'today')}
              className="h-12 sm:h-14 px-8 sm:px-10 rounded-2xl bg-[#5E9278] hover:bg-[#4D7A64] text-white text-sm sm:text-base font-bold shadow-md hover:shadow-lg transition-all active:scale-95 flex items-center gap-2.5"
            >
              <span>Launch</span>
              <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>
        </div>
      </section>

      {/* CONSUMER VALUE HIGHLIGHTS */}
      <section className="py-16 px-4 sm:px-8 border-t border-[#D9D8D2]/70 dark:border-[#2D322E] bg-[#F3F1EB]/40 dark:bg-[#141714]/40">
        <div className="max-w-5xl mx-auto space-y-10">
          <div className="text-center space-y-2 max-w-xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Everything your home needs, in sync.
            </h2>
            <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
              Replace fragmented group chats, shared notes, and paper receipts with one calm, connected view.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Chores & Tasks */}
            <Card className="p-6 space-y-3.5 bg-white dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E]">
              <div className="w-10 h-10 rounded-xl bg-[#5E9278]/15 text-[#5E9278] flex items-center justify-center">
                <CheckSquare className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-[#171918] dark:text-[#EFF1EC]">
                Chores & Daily Tasks
              </h3>
              <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96] leading-relaxed">
                Assign household responsibilities, track recurring chores, and keep everyone accountable without constant reminding.
              </p>
            </Card>

            {/* Pantry & Groceries */}
            <Card className="p-6 space-y-3.5 bg-white dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E]">
              <div className="w-10 h-10 rounded-xl bg-[#6E96AD]/15 text-[#6E96AD] flex items-center justify-center">
                <ShoppingBag className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-[#171918] dark:text-[#EFF1EC]">
                Smart Groceries & Pantry
              </h3>
              <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96] leading-relaxed">
                Maintain accurate inventory of daily staples. Get automatic alerts before essentials run out so you never double-buy.
              </p>
            </Card>

            {/* Budgets & Outlays */}
            <Card className="p-6 space-y-3.5 bg-white dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E]">
              <div className="w-10 h-10 rounded-xl bg-[#D19A4C]/15 text-[#D19A4C] flex items-center justify-center">
                <Wallet className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-[#171918] dark:text-[#EFF1EC]">
                Budgets & Expenses
              </h3>
              <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96] leading-relaxed">
                Track family spending envelopes in real time. Snap receipts, log outlays, and preserve a healthy buffer every week.
              </p>
            </Card>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS — Simple Consumer Steps */}
      <section className="py-16 px-4 sm:px-8 border-t border-[#D9D8D2]/70 dark:border-[#2D322E]">
        <div className="max-w-4xl mx-auto space-y-10">
          <div className="text-center space-y-2 max-w-xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Simple to set up. Effortless to run.
            </h2>
            <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
              Designed to bring peace of mind to family management.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center space-y-2">
              <div className="w-9 h-9 rounded-full bg-[#5E9278] text-white font-bold text-sm flex items-center justify-center mx-auto">
                1
              </div>
              <h4 className="font-bold text-sm text-[#171918] dark:text-[#EFF1EC]">
                Create Your Household
              </h4>
              <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-relaxed">
                Add family members, set your household name, and configure roles in under a minute.
              </p>
            </div>

            <div className="text-center space-y-2">
              <div className="w-9 h-9 rounded-full bg-[#5E9278] text-white font-bold text-sm flex items-center justify-center mx-auto">
                2
              </div>
              <h4 className="font-bold text-sm text-[#171918] dark:text-[#EFF1EC]">
                Track Daily Rhythms
              </h4>
              <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-relaxed">
                Log receipts, schedule appliance services, and assign chores from any phone or browser.
              </p>
            </div>

            <div className="text-center space-y-2">
              <div className="w-9 h-9 rounded-full bg-[#5E9278] text-white font-bold text-sm flex items-center justify-center mx-auto">
                3
              </div>
              <h4 className="font-bold text-sm text-[#171918] dark:text-[#EFF1EC]">
                Stay Ahead of Needs
              </h4>
              <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-relaxed">
                HomeOps coordinates priorities automatically so your home runs smoothly on autopilot.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FINAL CALL TO ACTION */}
      <section className="py-16 px-4 sm:px-8 border-t border-[#D9D8D2]/70 dark:border-[#2D322E] bg-white dark:bg-[#181B18]">
        <div className="max-w-2xl mx-auto text-center space-y-5">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
            Ready to simplify your home?
          </h2>

          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96] max-w-md mx-auto">
            Experience the unified household coordinator today.
          </p>

          <div className="pt-2 flex justify-center">
            <button
              onClick={() => navigateTo('app', 'today')}
              className="h-12 px-8 rounded-xl bg-[#5E9278] hover:bg-[#4D7A64] text-white text-sm font-bold shadow-xs transition-all active:scale-95 flex items-center gap-2"
            >
              <span>Launch HomeOps</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Minimal Modern Footer */}
      <footer className="py-8 px-4 sm:px-8 border-t border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#101210] text-xs text-[#676B68] dark:text-[#969D96]">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#171918] dark:text-[#EFF1EC]">HomeOps</span>
            <span>•</span>
            <span>The Operating System for the Modern Family</span>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium">
            <button onClick={() => navigateTo('login')} className="hover:text-[#171918] dark:hover:text-[#EFF1EC]">
              Sign In
            </button>
            <button onClick={() => navigateTo('register')} className="hover:text-[#171918] dark:hover:text-[#EFF1EC]">
              Create Household
            </button>
            <button onClick={() => navigateTo('app', 'today')} className="text-[#5E9278] font-semibold hover:underline">
              Launch →
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
};
