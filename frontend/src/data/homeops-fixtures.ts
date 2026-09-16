export type Priority = 'low' | 'medium' | 'high';
export type Status = 'ready' | 'attention' | 'verified' | 'planned';

export type HouseholdTask = { id: string; title: string; owner: string; cadence: string; priority: Priority; status: Status };
export type HouseholdEvent = { id: string; title: string; date: string; place: string; kind: 'school' | 'travel' | 'guest' };
export type InventoryAlert = { id: string; title: string; detail: string; quantity: string; status: Status };
export type HouseholdMember = { id: string; name: string; role: string; access: string; initials: string; status: Status };
export type Expense = { id: string; title: string; category: string; amount: string; date: string; status: Status };
export type MaintenanceIssue = { id: string; title: string; location: string; due: string; status: Status };
export type HouseholdDocument = { id: string; title: string; type: string; updated: string; status: Status };
export type AgentStep = { id: string; title: string; detail: string; status: 'complete' | 'active' | 'planned' };

export const household = {
  name: 'The Sharma Family',
  activeUser: 'Rajesh Sharma',
  activeRole: 'Parent / Administrator',
  memberCount: 4,
  domainCount: 6,
  syncedAgents: 3,
  planState: 'Baseline',
};

export const tasks: HouseholdTask[] = [
  { id: 'task-1', title: 'Water balcony plants & garden', owner: 'Aarav Sharma', cadence: 'Daily · 5:00 PM', priority: 'medium', status: 'ready' },
  { id: 'task-2', title: 'Review monthly broadband utility invoice', owner: 'Rajesh Sharma', cadence: 'Thursday', priority: 'low', status: 'planned' },
  { id: 'task-3', title: 'Restock weekly pantry snacks', owner: 'Priya Sharma', cadence: 'Wednesday', priority: 'medium', status: 'attention' },
  { id: 'task-4', title: 'Replace guest room AC filter', owner: 'Rajesh Sharma', cadence: 'Due today', priority: 'high', status: 'attention' },
];

export const events: HouseholdEvent[] = [
  { id: 'event-1', title: 'Aarav inter-school football match', date: 'Thursday · 4:30 PM – 6:00 PM', place: 'School Sports Complex', kind: 'school' },
  { id: 'event-2', title: 'Priya returning from work trip', date: 'Friday · 7:00 PM', place: "Kempegowda Int'l Airport (BLR)", kind: 'travel' },
  { id: 'event-3', title: '4 relatives arrive for weekend stay', date: 'Saturday · 11:00 AM', place: 'Home · Green Meadows', kind: 'guest' },
];

export const inventoryAlerts: InventoryAlert[] = [
  { id: 'inventory-1', title: 'Fresh cow milk', detail: 'Need +3L for 4 guests', quantity: '0.5L', status: 'attention' },
  { id: 'inventory-2', title: 'Vegetables', detail: 'Tomatoes, onions, paneer', quantity: '1.2kg', status: 'attention' },
  { id: 'inventory-3', title: 'Guest refreshments', detail: 'Snacks & dry fruits', quantity: '0g', status: 'attention' },
  { id: 'inventory-4', title: "Grandma's BP/Diabetes Rx", detail: 'Urgent monthly refill', quantity: '2 days', status: 'attention' },
];

export const members: HouseholdMember[] = [
  { id: 'member-1', name: 'Rajesh Sharma', role: 'Parent / Administrator', access: 'All household domains', initials: 'RS', status: 'verified' },
  { id: 'member-2', name: 'Priya Sharma', role: 'Adult Member', access: 'Tasks, inventory, calendar', initials: 'PS', status: 'ready' },
  { id: 'member-3', name: 'Aarav Sharma', role: 'Child / Teen', access: 'Assigned tasks, shared calendar', initials: 'AS', status: 'ready' },
  { id: 'member-4', name: 'Grandma Sharma', role: 'Guest / Viewer', access: 'Shared health information', initials: 'GS', status: 'verified' },
];

export const expenses: Expense[] = [
  { id: 'expense-1', title: 'Monthly groceries', category: 'Food', amount: '₹1,850', date: 'Sep 14, 2026', status: 'planned' },
  { id: 'expense-2', title: 'Broadband utility invoice', category: 'Utilities', amount: '₹999', date: 'Sep 12, 2026', status: 'ready' },
  { id: 'expense-3', title: 'AC service visit', category: 'Maintenance', amount: '₹650', date: 'Sep 10, 2026', status: 'attention' },
];

export const maintenanceIssues: MaintenanceIssue[] = [
  { id: 'maintenance-1', title: 'Guest room AC filter dirty', location: 'Guest room', due: 'Service due today', status: 'attention' },
  { id: 'maintenance-2', title: 'Kitchen tap pressure check', location: 'Kitchen', due: 'Due Sep 20', status: 'planned' },
  { id: 'maintenance-3', title: 'Water purifier annual service', location: 'Utility area', due: 'Completed Aug 28', status: 'verified' },
];

export const documents: HouseholdDocument[] = [
  { id: 'document-1', title: "Dad's low-salt diet directive", type: 'Medical governance', updated: 'Updated Sep 12, 2026', status: 'verified' },
  { id: 'document-2', title: "Grandma's prescription schedule", type: 'Medical record', updated: 'Updated Sep 10, 2026', status: 'verified' },
  { id: 'document-3', title: 'Guest room appliance warranties', type: 'Household record', updated: 'Updated Aug 28, 2026', status: 'ready' },
];

export const agentSteps: AgentStep[] = [
  { id: 'agent-1', title: 'Understand weekend constraints', detail: 'Travel, guests, diet, and medication rules', status: 'complete' },
  { id: 'agent-2', title: 'Balance household responsibilities', detail: 'Distribute tasks across available members', status: 'active' },
  { id: 'agent-3', title: 'Prepare grocery and schedule actions', detail: 'Awaiting confirmation before changes', status: 'planned' },
];

export const insights = [
  { title: 'Dietary Constraint Guard', detail: "Dad's low-salt directive is enforced on grocery procurement lists.", status: 'verified' as Status },
  { title: 'Mom Travel Balancing', detail: "Mom's tasks are distributed to Rajesh and Aarav until Friday.", status: 'ready' as Status },
  { title: 'Financial Buffer', detail: '₹2,400 remains available for weekend contingencies.', status: 'planned' as Status },
];
