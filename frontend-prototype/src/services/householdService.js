import { INITIAL_HOUSEHOLD_DATA } from './mockData';

class HouseholdService {
  constructor() {
    this.listeners = new Set();
    this.activeUserId = 'rajesh'; // Default: Dad (Parent Admin)
    this.state = JSON.parse(JSON.stringify(INITIAL_HOUSEHOLD_DATA));
    this.isPlanApplied = false;
  }

  // Subscribe to state updates
  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    this.listeners.forEach((listener) => listener(this.getState()));
  }

  // Get raw unfiltered state
  getRawState() {
    return this.state;
  }

  // Get active persona
  getActiveUser() {
    return this.state.members.find((m) => m.id === this.activeUserId) || this.state.members[0];
  }

  // Switch active persona
  setActiveUser(userId) {
    const member = this.state.members.find((m) => m.id === userId);
    if (member) {
      this.activeUserId = userId;
      this.notify();
    }
  }

  // Get permission-aware view of state for current user
  getState() {
    const activeUser = this.getActiveUser();
    const raw = this.state;

    // Deep copy to prevent mutations
    const filtered = JSON.parse(JSON.stringify(raw));
    filtered.activeUser = activeUser;
    filtered.isPlanApplied = this.isPlanApplied;

    // Apply Role-Based Access Control (RBAC)
    if (!activeUser.permissions.canViewFinances) {
      filtered.finance = {
        isRestricted: true,
        restrictedMessage: "Financial totals, line-item expenses, and balances are restricted for Teenager and Guest roles under family privacy policy.",
        weeklyBudget: null,
        estimatedRemaining: null,
        plannedExpenses: null,
        breakdown: [],
        recentTransactions: []
      };
    }

    if (!activeUser.permissions.canViewAllTasks) {
      // Teenagers only see their assigned tasks and public/family events
      filtered.tasks = raw.tasks.filter((t) => t.assignedTo === activeUser.id || t.isShared);
    }

    if (!activeUser.permissions.canViewMedicalDocs) {
      // Filter out medical docs for users without medical clearance
      filtered.documents = raw.documents.filter((d) => d.category !== "Medical & Health");
    }

    return filtered;
  }

  // Apply Coordinated Multi-Agent Plan to live state
  applyCoordinatedPlan(planDetails = {}) {
    this.isPlanApplied = true;

    // 1. Update Tasks (Add new cross-domain tasks and reassign Mom's pending task)
    const newTasks = [
      {
        id: "tsk-plan-01",
        title: "Purchase Grandma's BP & Diabetes Rx Refill",
        category: "Health",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Wednesday",
        status: "pending",
        priority: "urgent",
        domain: "Health",
        notes: "Monthly prescription refill (₹900) verified by Apollo Clinic Doc",
        sourcePlan: true,
      },
      {
        id: "tsk-plan-02",
        title: "Procure Groceries & Fresh Produce for 4 Relatives",
        category: "Food",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Thursday",
        status: "pending",
        priority: "high",
        domain: "Food",
        notes: "Include low-sodium items for Dad's restriction; Est: ₹1,700",
        sourcePlan: true,
      },
      {
        id: "tsk-plan-03",
        title: "Guest Bedroom Deep Prep & Fresh Linen Setup",
        category: "Home",
        assignedTo: "aarav",
        assignedToName: "Aarav Sharma",
        dueDate: "Friday (After 4:00 PM)",
        status: "pending",
        priority: "high",
        domain: "Home",
        notes: "Prepare bedding, towels, and welcome kit for 4 visiting relatives",
        sourcePlan: true,
      },
      {
        id: "tsk-plan-04",
        title: "Supervise Daikin AC Service & Filter Replacement",
        category: "Maintenance",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Friday (10:00 AM)",
        status: "pending",
        priority: "high",
        domain: "Home & Maintenance",
        notes: "Daikin Authorized AMC service scheduled under warranty",
        sourcePlan: true,
      },
    ];

    // Reassign Priya's original snack restocking task to Rajesh due to her travel
    const updatedTasks = this.state.tasks.map((t) => {
      if (t.id === "tsk-003") {
        return {
          ...t,
          assignedTo: "rajesh",
          assignedToName: "Rajesh Sharma",
          notes: "Reassigned by Context Agent: Mom away on business trip until Friday evening",
          reassigned: true,
        };
      }
      return t;
    });

    this.state.tasks = [...updatedTasks, ...newTasks];

    // 2. Update Finance
    this.state.finance = {
      ...this.state.finance,
      weeklyBudget: 5000,
      plannedExpenses: 2600, // 1700 + 900
      estimatedRemaining: 2400, // 5000 - 2600
      breakdown: [
        {
          id: "exp-plan-1",
          item: "Hospitality Groceries (4 Guests + Low-Salt Items)",
          category: "Food",
          amount: 1700,
          date: "Thursday Planned",
          status: "planned",
          agentReasoning: "Operations Agent: Scaling produce, dairy, snacks for 4 weekend guests while honoring Dad's verified low-salt constraint."
        },
        {
          id: "exp-plan-2",
          item: "Grandma Monthly Prescription (BP & Diabetes)",
          category: "Healthcare",
          amount: 900,
          date: "Wednesday Planned",
          status: "planned",
          agentReasoning: "Document Agent: Verified Rx Refill cost match from Apollo Clinic health record DOC-MED-02."
        },
      ],
      recentTransactions: this.state.finance.recentTransactions,
    };

    // 3. Update Inventory
    this.state.inventory = this.state.inventory.map((item) => {
      if (item.id === "inv-2") {
        return { ...item, status: "restocking", notes: "3L addition scheduled for Thursday grocery run" };
      }
      if (item.id === "inv-3") {
        return { ...item, status: "restocking", notes: "4kg vegetables scheduled for Thursday" };
      }
      if (item.id === "inv-8") {
        return { ...item, status: "restocking", notes: "Procuring low-salt snacks for 4 relatives" };
      }
      if (item.id === "inv-10") {
        return { ...item, status: "refill_scheduled", notes: "Refill ordered for Wednesday delivery" };
      }
      return item;
    });

    // 4. Update Maintenance (Schedule Daikin AC service)
    this.state.maintenance = this.state.maintenance.map((app) => {
      if (app.id === "app-1") {
        return {
          ...app,
          status: "scheduled",
          statusLabel: "Service Confirmed",
          scheduledDate: "Friday, 10:00 AM",
          issueDescription: "Daikin technician Ramesh Kumar confirmed for complimentary warranty service before guests arrive.",
        };
      }
      return app;
    });

    // 5. Update Schedule / Calendar
    const planScheduleEvents = [
      {
        id: "sch-plan-1",
        title: "Rx Refill Delivery (Grandma's BP Medicine)",
        day: "Wednesday",
        time: "11:30 AM",
        attendees: ["rajesh", "savitri"],
        type: "health",
        domain: "Health & Care",
        location: "Home Delivery",
      },
      {
        id: "sch-plan-2",
        title: "Grocery Procurement for 4 Guests (Low-Salt)",
        day: "Thursday",
        time: "6:30 PM",
        attendees: ["rajesh"],
        type: "shopping",
        domain: "Food & Inventory",
        location: "Reliance Fresh / Supermarket",
      },
      {
        id: "sch-plan-3",
        title: "Daikin AC Technician Visit (Guest Room)",
        day: "Friday",
        time: "10:00 AM - 11:00 AM",
        attendees: ["rajesh"],
        type: "maintenance",
        domain: "Home & Maintenance",
        location: "Guest Bedroom",
      },
      {
        id: "sch-plan-4",
        title: "Guest Bedroom Setup & Linen Preparation",
        day: "Friday",
        time: "4:30 PM - 5:30 PM",
        attendees: ["aarav"],
        type: "chore",
        domain: "Tasks & Schedule",
        location: "Guest Bedroom",
      },
    ];

    this.state.schedule = [...this.state.schedule, ...planScheduleEvents];

    // 6. Add to Activity Log
    this.state.recentActivities.unshift({
      id: `act-${Date.now()}`,
      timestamp: "Just now",
      agent: "Orchestrator",
      message: "Coordinated Household Action Plan successfully applied across 6 domains.",
      category: "Plan Applied"
    });

    this.notify();
    return true;
  }

  // Toggle task completion
  toggleTaskStatus(taskId) {
    this.state.tasks = this.state.tasks.map((t) => {
      if (t.id === taskId) {
        const nextStatus = t.status === "completed" ? "pending" : "completed";
        return { ...t, status: nextStatus };
      }
      return t;
    });
    this.notify();
  }

  // Add a task (with optional recurring rule)
  addTask(taskData) {
    const newTask = {
      id: `tsk-manual-${Date.now()}`,
      title: taskData.title,
      category: taskData.category || "General",
      assignedTo: taskData.assignedTo || "rajesh",
      assignedToName: this.state.members.find(m => m.id === taskData.assignedTo)?.name || "Rajesh Sharma",
      dueDate: taskData.dueDate || "Today",
      status: "pending",
      priority: taskData.priority || "medium",
      domain: taskData.domain || "Home",
      notes: taskData.notes || "",
      recurring: taskData.recurring || "None",
    };
    this.state.tasks.unshift(newTask);
    this.notify();
    return newTask;
  }

  // Add pantry item (manual or parsed)
  addInventoryItem(itemData) {
    const newItem = {
      id: `inv-${Date.now()}`,
      name: itemData.name,
      category: itemData.category || "Produce",
      quantity: `${itemData.quantity} ${itemData.unit || ''}`.trim(),
      status: itemData.status || "available",
      minThreshold: itemData.minThreshold || "1 unit",
      dietaryNote: itemData.dietaryNote || "Standard",
      notes: itemData.notes || "",
    };
    this.state.inventory.unshift(newItem);
    this.notify();
    return newItem;
  }

  // Add multiple pantry items from Document Agent receipt parsing
  addBulkInventoryItems(items = []) {
    items.forEach(item => {
      this.state.inventory.unshift({
        id: `inv-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
        name: item.name,
        category: item.category || "Produce",
        quantity: item.quantity || "1 unit",
        status: "available",
        minThreshold: item.minThreshold || "1 unit",
        dietaryNote: item.dietaryNote || "Added via receipt scan",
      });
    });
    this.notify();
  }

  // Add appliance & warranty document
  addAppliance(appData) {
    const newApp = {
      id: `app-${Date.now()}`,
      name: appData.name,
      category: appData.category || "HVAC",
      location: appData.location || "Living Room",
      status: appData.status || "optimal",
      statusLabel: appData.statusLabel || "Optimal",
      issueDescription: appData.issueDescription || "Installed and operational",
      lastService: appData.lastService || "Newly Added",
      warrantyStatus: appData.warrantyStatus || "Active Warranty",
      warrantyDocId: appData.warrantyDocId || `DOC-WAR-${Date.now().toString().slice(-4)}`,
    };
    this.state.maintenance.unshift(newApp);
    this.notify();
    return newApp;
  }

  // Add schedule event
  addScheduleEvent(evtData) {
    const newEvt = {
      id: `sch-${Date.now()}`,
      title: evtData.title,
      day: evtData.day || "Today",
      time: evtData.time || "10:00 AM",
      attendees: evtData.attendees || ["rajesh"],
      type: evtData.type || "general",
      domain: evtData.domain || "Tasks & Schedule",
      location: evtData.location || "Home",
      recurring: evtData.recurring || "None",
    };
    this.state.schedule.push(newEvt);
    this.notify();
    return newEvt;
  }

  // Add / Invite member
  addMember(memberData) {
    const isParentRole = memberData.role?.includes('Admin') || memberData.role?.includes('Parent');
    const isTeenRole = memberData.role?.includes('Teen');

    const newMember = {
      id: memberData.name.toLowerCase().replace(/\s+/g, '_') + `_${Date.now().toString().slice(-3)}`,
      name: memberData.name,
      relation: memberData.relation || "Family Member",
      role: memberData.role || "Adult / Member",
      avatar: memberData.avatar || "👤",
      color: "emerald",
      clearance: isParentRole ? "Full Admin" : isTeenRole ? "Restricted (Chores Only)" : "Standard Member",
      availability: "Available",
      statusText: memberData.statusText || "Active household member",
      responsibilities: memberData.responsibilities || ["General Household Tasks"],
      dietaryNotes: memberData.dietaryNotes || "No restrictions",
      permissions: {
        canViewFinances: isParentRole,
        canApproveExpenses: isParentRole,
        canViewAllTasks: !isTeenRole,
        canAssignTasks: isParentRole,
        canViewMedicalDocs: !isTeenRole,
        canManageAppliances: isParentRole,
        canExecuteAgentPlan: isParentRole,
      },
    };
    this.state.members.push(newMember);
    this.notify();
    return newMember;
  }

  // Update member role & clearance
  updateMemberRole(memberId, newRole) {
    const isParentRole = newRole.includes('Admin') || newRole.includes('Parent');
    const isTeenRole = newRole.includes('Teen');

    this.state.members = this.state.members.map(m => {
      if (m.id === memberId) {
        return {
          ...m,
          role: newRole,
          clearance: isParentRole ? "Full Admin" : isTeenRole ? "Restricted (Chores Only)" : "Standard Member",
          permissions: {
            ...m.permissions,
            canViewFinances: isParentRole,
            canApproveExpenses: isParentRole,
            canViewAllTasks: !isTeenRole,
            canAssignTasks: isParentRole,
            canViewMedicalDocs: !isTeenRole,
            canManageAppliances: isParentRole,
            canExecuteAgentPlan: isParentRole,
          }
        };
      }
      return m;
    });
    this.notify();
  }

  // Update member status & availability
  updateMemberStatus(memberId, statusText, availability) {
    this.state.members = this.state.members.map(m => {
      if (m.id === memberId) {
        return {
          ...m,
          statusText: statusText || m.statusText,
          availability: availability || m.availability,
        };
      }
      return m;
    });
    this.notify();
  }

  // Add recorded outlay / expense
  addExpense(expenseData) {
    const amount = parseFloat(expenseData.amount) || 0;
    const newTx = {
      id: `tx-${Date.now()}`,
      title: expenseData.title || "Household Outlay",
      amount,
      date: expenseData.date || "Today",
      category: expenseData.category || "General",
      paidBy: expenseData.paidBy || this.getActiveUser().name.split(' ')[0],
      merchant: expenseData.merchant || "",
      notes: expenseData.notes || "",
    };

    this.state.finance.recentTransactions.unshift(newTx);
    this.state.finance.currentExpenses = (this.state.finance.currentExpenses || 0) + amount;
    this.state.finance.estimatedRemaining = Math.max(0, (this.state.finance.estimatedRemaining || 5000) - amount);

    this.notify();
    return newTx;
  }

  // Apply Coordinated Multi-Agent Plan with Granular Human-in-the-Loop Approvals
  applyCoordinatedPlanWithApprovals({ approveMedicine = true, approveAC = true } = {}) {
    this.isPlanApplied = true;

    // 1. Base Tasks (Always safe to coordinate)
    const newTasks = [
      {
        id: "tsk-plan-02",
        title: "Procure Groceries & Fresh Produce for 4 Relatives",
        category: "Food",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Thursday",
        status: "pending",
        priority: "high",
        domain: "Food",
        notes: "Include low-sodium items for Dad's restriction; Est: ₹1,700",
        sourcePlan: true,
      },
      {
        id: "tsk-plan-03",
        title: "Guest Bedroom Deep Prep & Fresh Linen Setup",
        category: "Home",
        assignedTo: "aarav",
        assignedToName: "Aarav Sharma",
        dueDate: "Friday (After 4:00 PM)",
        status: "pending",
        priority: "high",
        domain: "Home",
        notes: "Prepare bedding, towels, and welcome kit for 4 visiting relatives",
        sourcePlan: true,
      },
    ];

    // If Medicine Refill approved by human
    if (approveMedicine) {
      newTasks.unshift({
        id: "tsk-plan-01",
        title: "Purchase Grandma's BP & Diabetes Rx Refill",
        category: "Health",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Wednesday",
        status: "pending",
        priority: "urgent",
        domain: "Health",
        notes: "Monthly prescription refill (₹900) verified by Apollo Clinic Doc",
        sourcePlan: true,
      });
    }

    // If Daikin AC Service approved by human
    if (approveAC) {
      newTasks.push({
        id: "tsk-plan-04",
        title: "Supervise Daikin AC Service & Filter Replacement",
        category: "Maintenance",
        assignedTo: "rajesh",
        assignedToName: "Rajesh Sharma",
        dueDate: "Friday (10:00 AM)",
        status: "pending",
        priority: "high",
        domain: "Home & Maintenance",
        notes: "Daikin Authorized AMC service scheduled under warranty",
        sourcePlan: true,
      });
    }

    // Reassign Priya's snack task to Rajesh
    const updatedTasks = this.state.tasks.map((t) => {
      if (t.id === "tsk-003") {
        return {
          ...t,
          assignedTo: "rajesh",
          assignedToName: "Rajesh Sharma",
          notes: "Reassigned by Context Agent: Mom away on business trip until Friday evening",
          reassigned: true,
        };
      }
      return t;
    });

    this.state.tasks = [...updatedTasks, ...newTasks];

    // 2. Update Finance according to approvals
    const plannedFood = 1700;
    const plannedRx = approveMedicine ? 900 : 0;
    const totalPlanned = plannedFood + plannedRx;

    const breakdownItems = [
      {
        id: "exp-plan-1",
        item: "Hospitality Groceries (4 Guests + Low-Salt Items)",
        category: "Food",
        amount: plannedFood,
        date: "Thursday Planned",
        status: "planned",
        agentReasoning: "Operations Agent: Scaling produce, dairy, snacks for 4 weekend guests honoring low-salt directive."
      }
    ];

    if (approveMedicine) {
      breakdownItems.push({
        id: "exp-plan-2",
        item: "Grandma Monthly Prescription (BP & Diabetes)",
        category: "Healthcare",
        amount: 900,
        date: "Wednesday Planned",
        status: "planned",
        agentReasoning: "Document Agent: Verified Rx Refill cost match from Apollo Clinic health record DOC-MED-02."
      });
    }

    this.state.finance = {
      ...this.state.finance,
      weeklyBudget: 5000,
      plannedExpenses: totalPlanned,
      estimatedRemaining: 5000 - totalPlanned,
      breakdown: breakdownItems,
      recentTransactions: this.state.finance.recentTransactions,
    };

    // 3. Update Inventory
    this.state.inventory = this.state.inventory.map((item) => {
      if (item.id === "inv-2") {
        return { ...item, status: "restocking", notes: "3L addition scheduled for Thursday grocery run" };
      }
      if (item.id === "inv-3") {
        return { ...item, status: "restocking", notes: "4kg vegetables scheduled for Thursday" };
      }
      if (item.id === "inv-8") {
        return { ...item, status: "restocking", notes: "Procuring low-salt snacks for 4 relatives" };
      }
      if (item.id === "inv-10" && approveMedicine) {
        return { ...item, status: "refill_scheduled", notes: "Refill ordered for Wednesday delivery" };
      }
      return item;
    });

    // 4. Update Maintenance if AC approved
    if (approveAC) {
      this.state.maintenance = this.state.maintenance.map((app) => {
        if (app.id === "app-1") {
          return {
            ...app,
            status: "scheduled",
            statusLabel: "Service Confirmed",
            scheduledDate: "Friday, 10:00 AM",
            issueDescription: "Daikin technician Ramesh Kumar confirmed for complimentary warranty service before guests arrive.",
          };
        }
        return app;
      });
    }

    // 5. Update Schedule
    const planScheduleEvents = [
      {
        id: "sch-plan-2",
        title: "Grocery Procurement for 4 Guests (Low-Salt)",
        day: "Thursday",
        time: "6:30 PM",
        attendees: ["rajesh"],
        type: "shopping",
        domain: "Food & Inventory",
        location: "Reliance Fresh / Supermarket",
      },
      {
        id: "sch-plan-4",
        title: "Guest Bedroom Setup & Linen Preparation",
        day: "Friday",
        time: "4:30 PM - 5:30 PM",
        attendees: ["aarav"],
        type: "chore",
        domain: "Tasks & Schedule",
        location: "Guest Bedroom",
      },
    ];

    if (approveMedicine) {
      planScheduleEvents.unshift({
        id: "sch-plan-1",
        title: "Rx Refill Delivery (Grandma's BP Medicine)",
        day: "Wednesday",
        time: "11:30 AM",
        attendees: ["rajesh", "savitri"],
        type: "health",
        domain: "Health & Care",
        location: "Home Delivery",
      });
    }

    if (approveAC) {
      planScheduleEvents.push({
        id: "sch-plan-3",
        title: "Daikin AC Technician Visit (Guest Room)",
        day: "Friday",
        time: "10:00 AM - 11:00 AM",
        attendees: ["rajesh"],
        type: "maintenance",
        domain: "Home & Maintenance",
        location: "Guest Bedroom",
      });
    }

    this.state.schedule = [...this.state.schedule, ...planScheduleEvents];

    // 6. Activity log
    this.state.recentActivities.unshift({
      id: `act-${Date.now()}`,
      timestamp: "Just now",
      agent: "Orchestrator",
      message: `Human-in-the-Loop approval confirmed. Actions executed: ${approveMedicine ? 'Rx refill, ' : ''}${approveAC ? 'Daikin AC service, ' : ''}hospitality groceries, and chore delegations.`,
      category: "Plan Executed"
    });

    this.notify();
    return true;
  }

  // Reset to initial baseline
  resetToBaseline() {
    this.state = JSON.parse(JSON.stringify(INITIAL_HOUSEHOLD_DATA));
    this.isPlanApplied = false;
    this.notify();
  }
}

export const householdService = new HouseholdService();
