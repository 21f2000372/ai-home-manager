import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { householdService } from '../services/householdService';
import { agentService } from '../services/agentService';

const HouseholdContext = createContext(null);

export const HouseholdProvider = ({ children }) => {
  const [state, setState] = useState(householdService.getState());
  // Determine initial view from URL path/hash or localStorage
  const [currentView, setCurrentView] = useState(() => {
    const path = window.location.pathname.toLowerCase();
    const hash = window.location.hash.toLowerCase();
    if (path === '/login' || hash === '#/login' || path === '/register' || hash === '#/register') {
      return 'auth';
    }
    if (path === '/overview' || hash === '#/overview' || path === '/') {
      return 'landing';
    }
    return localStorage.getItem('homeops_view') || 'landing';
  });

  const [authMode, setAuthMode] = useState(() => {
    const path = window.location.pathname.toLowerCase();
    const hash = window.location.hash.toLowerCase();
    if (path === '/register' || hash === '#/register') return 'register';
    return 'login';
  });

  const [activeTab, setActiveTab] = useState('today');
  const [isProcessing, setIsProcessing] = useState(false);
  const [toasts, setToasts] = useState([]);
  
  // Theme state: 'light' (default) or 'dark'
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('homeops_theme') || 'light';
  });

  // Sync current view with localStorage
  useEffect(() => {
    localStorage.setItem('homeops_view', currentView);
  }, [currentView]);

  // Navigation helper supporting ('landing' | 'overview' | 'auth' | 'login' | 'register' | 'app')
  const navigateTo = useCallback((view, subOption) => {
    if (view === 'login' || (view === 'auth' && subOption === 'login')) {
      setAuthMode('login');
      setCurrentView('auth');
      window.history.replaceState(null, '', '#/login');
    } else if (view === 'register' || (view === 'auth' && subOption === 'register')) {
      setAuthMode('register');
      setCurrentView('auth');
      window.history.replaceState(null, '', '#/register');
    } else if (view === 'auth') {
      setCurrentView('auth');
      window.history.replaceState(null, '', '#/login');
    } else if (view === 'app') {
      if (subOption) {
        setActiveTab(subOption);
      }
      setCurrentView('app');
      window.history.replaceState(null, '', '#/app');
    } else {
      setCurrentView('landing');
      window.history.replaceState(null, '', '#/overview');
    }
  }, []);

  // Quick Login As Persona
  const loginAs = useCallback((memberId) => {
    householdService.setActiveUser(memberId);
    const user = householdService.getActiveUser();
    setCurrentView('app');
    setActiveTab('today');
    addToast('Authenticated', `Welcome back, ${user.name} (${user.role})`, 'success');
  }, []);

  // Logout
  const logout = useCallback(() => {
    setCurrentView('landing');
    addToast('Signed Out', 'Household session closed.', 'info');
  }, []);

  // Sync theme with HTML root class
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('homeops_theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  // Chat messages with initial warm household greeting
  const [chatMessages, setChatMessages] = useState<any[]>([
    {
      id: 'msg-welcome',
      sender: 'assistant',
      timestamp: 'Today, 8:30 AM',
      text: "Good morning! I am keeping track of our family schedule, pantry supplies, and budget. Let me know if anything changes or ask what needs to happen.",
    }
  ]);

  // Subscribe to householdService updates
  useEffect(() => {
    const unsubscribe = householdService.subscribe((updatedState) => {
      setState(updatedState);
    });
    return () => unsubscribe();
  }, []);

  // Toast notifications
  const addToast = useCallback((title, message, type = 'info') => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, title, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Switch persona (e.g. Dad vs Teenager)
  const switchUser = useCallback((userId) => {
    householdService.setActiveUser(userId);
    const newActive = householdService.getActiveUser();
    addToast('Profile Switched', `Viewing as ${newActive.name} (${newActive.role})`, 'info');
  }, [addToast]);

  // Toggle Task Completion
  const toggleTask = useCallback((taskId) => {
    householdService.toggleTaskStatus(taskId);
    const task = state.tasks.find(t => t.id === taskId);
    const completed = task?.status === 'pending';
    addToast(
      completed ? 'Task Completed' : 'Task Reopened',
      `"${task?.title}" marked ${completed ? 'done' : 'pending'}.`,
      completed ? 'success' : 'info'
    );
  }, [state.tasks, addToast]);

  // Add Task
  const addTask = useCallback((taskData) => {
    householdService.addTask(taskData);
    addToast('Task Created', `Added "${taskData.title}" to household tasks.`, 'success');
  }, [addToast]);

  // Add Inventory Item (Manual)
  const addInventoryItem = useCallback((itemData) => {
    householdService.addInventoryItem(itemData);
    addToast('Pantry Item Added', `Added ${itemData.quantity} of ${itemData.name}.`, 'success');
  }, [addToast]);

  // Bulk Add Inventory Items (Receipt Parsing / Document Agent)
  const addBulkInventoryItems = useCallback((items) => {
    householdService.addBulkInventoryItems(items);
    addToast('Receipt Processed', `Document Agent parsed and stocked ${items.length} items into pantry.`, 'success');
  }, [addToast]);

  // Add Appliance & Warranty
  const addAppliance = useCallback((appData) => {
    householdService.addAppliance(appData);
    addToast('Appliance Added', `Registered ${appData.name} under warranty.`, 'success');
  }, [addToast]);

  // Add Schedule Event
  const addScheduleEvent = useCallback((evtData) => {
    householdService.addScheduleEvent(evtData);
    addToast('Event Added', `Scheduled "${evtData.title}" for ${evtData.day}.`, 'success');
  }, [addToast]);

  // Add Member
  const addMember = useCallback((memberData) => {
    const m = householdService.addMember(memberData);
    addToast('Member Invited', `Added ${m.name} as ${m.role}.`, 'success');
  }, [addToast]);

  // Update Member Role
  const updateMemberRole = useCallback((memberId, newRole) => {
    householdService.updateMemberRole(memberId, newRole);
    addToast('Clearance Updated', `Role updated to ${newRole}.`, 'info');
  }, [addToast]);

  // Update Member Status
  const updateMemberStatus = useCallback((memberId, statusText, availability) => {
    householdService.updateMemberStatus(memberId, statusText, availability);
    addToast('Status Updated', 'Member context updated.', 'info');
  }, [addToast]);

  // Add Expense / Outlay
  const addExpense = useCallback((expenseData) => {
    const tx = householdService.addExpense(expenseData);
    addToast('Outlay Recorded', `Logged ₹${tx.amount} for ${tx.title}.`, 'success');
  }, [addToast]);

  // Apply Coordinated Plan (Direct or with HITL Approvals)
  const applyPlan = useCallback((plan) => {
    householdService.applyCoordinatedPlan(plan);
    addToast(
      'Household Actions Scheduled',
      'Tasks assigned, groceries scheduled, ₹2,600 expenses allocated, and AC service booked.',
      'success'
    );
  }, [addToast]);

  // Granular HITL Plan Execution
  const applyPlanWithApprovals = useCallback(({ approveMedicine = true, approveAC = true } = {}) => {
    householdService.applyCoordinatedPlanWithApprovals({ approveMedicine, approveAC });
    addToast(
      'Approved Actions Executed',
      `Synchronized household state: ${approveMedicine ? 'Rx refill, ' : ''}${approveAC ? 'Daikin AMC service, ' : ''}hospitality shopping, and tasks.`,
      'success'
    );
  }, [addToast]);

  // Reset to baseline
  const resetToBaseline = useCallback(() => {
    householdService.resetToBaseline();
    addToast('Household Reset', 'Restored initial clean family baseline.', 'info');
  }, [addToast]);

  // Send message to Coordinator Assistant
  const sendAgentMessage = useCallback(async (promptText) => {
    if (!promptText.trim() || isProcessing) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      sender: 'user',
      author: state.activeUser.name,
      avatar: state.activeUser.avatar,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: promptText,
    };

    setChatMessages(prev => [...prev, userMsg]);
    setIsProcessing(true);

    try {
      const response = await agentService.processQuery(promptText, state.activeUser.id);
      
      const assistantMsg = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        data: response,
      };

      setChatMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      addToast('Coordinator Error', 'Could not process request.', 'error');
    } finally {
      setIsProcessing(false);
    }
  }, [isProcessing, state.activeUser, addToast]);

  return (
    <HouseholdContext.Provider
      value={{
        state,
        rawState: householdService.getRawState(),
        activeUser: state.activeUser,
        currentView,
        setCurrentView,
        authMode,
        setAuthMode,
        navigateTo,
        loginAs,
        logout,
        activeTab,
        setActiveTab,
        theme,
        toggleTheme,
        switchUser,
        toggleTask,
        addTask,
        addInventoryItem,
        addBulkInventoryItems,
        addAppliance,
        addScheduleEvent,
        addMember,
        updateMemberRole,
        updateMemberStatus,
        addExpense,
        applyPlan,
        applyPlanWithApprovals,
        resetToBaseline,
        isProcessing,
        chatMessages,
        sendAgentMessage,
        toasts,
        addToast,
        removeToast,
      }}
    >
      {children}
    </HouseholdContext.Provider>
  );
};

export const useHousehold = () => {
  const context = useContext(HouseholdContext);
  if (!context) {
    throw new Error('useHousehold must be used within HouseholdProvider');
  }
  return context;
};
