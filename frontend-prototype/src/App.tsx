import React, { useState } from 'react';
import { useHousehold, HouseholdProvider } from './context/HouseholdContext';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { MobileNav } from './components/layout/MobileNav';
import { MobileDrawer } from './components/layout/MobileDrawer';
import { ToastContainer } from './components/common/ToastContainer';

// Clean Minimal Household Views
import { TodayView } from './components/views/TodayView';
import { ChatView } from './components/views/ChatView';
import { TasksView } from './components/views/TasksView';
import { PantryView } from './components/views/PantryView';
import { FinanceView } from './components/views/FinanceView';
import { HomeView } from './components/views/HomeView';
import { ScheduleView } from './components/views/ScheduleView';
import { MembersView } from './components/views/MembersView';
import { LandingPageView } from './components/views/LandingPageView';
import { AuthView } from './components/views/AuthView';

const MainLayout = () => {
  const { activeTab } = useHousehold();
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  const renderActiveView = () => {
    switch (activeTab) {
      case 'today':
        return <TodayView />;
      case 'assistant':
        return <ChatView />;
      case 'tasks':
        return <TasksView />;
      case 'pantry':
        return <PantryView />;
      case 'finance':
        return <FinanceView />;
      case 'home':
        return <HomeView />;
      case 'schedule':
        return <ScheduleView />;
      case 'members':
        return <MembersView />;
      default:
        return <TodayView />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F3F1EB] dark:bg-[#101210] text-[#171918] dark:text-[#EFF1EC] flex flex-col transition-colors">
      {/* Top Bar with Brand, Theme Toggle, Profile Switcher & Mobile Hamburger */}
      <Header onOpenMobileDrawer={() => setIsMobileDrawerOpen(true)} />

      {/* Center Layout: Collapsible Desktop Left Sidebar + Responsive Main Content */}
      <div className="flex-1 flex w-full">
        {/* Desktop Viewports: Collapsible Left Sidebar that minimizes to save space */}
        <Sidebar />

        {/* Primary Page Content */}
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-6xl w-full mx-auto pb-24 md:pb-8 overflow-y-auto">
          {renderActiveView()}
        </main>
      </div>

      {/* Mobile Viewports: Bottom Navigation Bar for core daily tabs */}
      <MobileNav onOpenDrawer={() => setIsMobileDrawerOpen(true)} />

      {/* Mobile Viewports: Slide-out Hamburger Drawer for remaining tabs & settings */}
      <MobileDrawer 
        isOpen={isMobileDrawerOpen} 
        onClose={() => setIsMobileDrawerOpen(false)} 
      />

      {/* Global Toast Notifications */}
      <ToastContainer />
    </div>
  );
};

const AppContent = () => {
  const { currentView } = useHousehold();

  if (currentView === 'landing') {
    return (
      <>
        <LandingPageView />
        <ToastContainer />
      </>
    );
  }

  if (currentView === 'auth') {
    return (
      <>
        <AuthView />
        <ToastContainer />
      </>
    );
  }

  return <MainLayout />;
};

export default function App() {
  return (
    <HouseholdProvider>
      <AppContent />
    </HouseholdProvider>
  );
}

