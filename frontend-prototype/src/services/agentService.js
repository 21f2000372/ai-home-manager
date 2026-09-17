/**
 * HomeOps Coordinator Service
 * Translates natural language household updates into coordinated actions
 * across food, chores, budget, and appliances without exposing raw technical traces.
 */
import { householdService } from './householdService';

class AgentService {
  /**
   * Process natural language household request or update
   */
  async processQuery(prompt, userId = 'rajesh') {
    const activeMember = householdService.getState().members.find(m => m.id === userId) || householdService.getActiveUser();
    const cleanPrompt = prompt.trim();
    const lower = cleanPrompt.toLowerCase();

    // Brief realistic processing pause
    await new Promise(resolve => setTimeout(resolve, 350));

    // 1. Check for Household Privacy Boundaries (RBAC)
    const isBudgetQuery = lower.includes('budget') || lower.includes('remaining') || lower.includes('money') || lower.includes('cost') || lower.includes('finance') || lower.includes('spend');
    if (isBudgetQuery && !activeMember.permissions.canViewFinances) {
      return {
        type: 'privacy_restricted',
        text: `Household financial totals and expense lines are restricted for your account under the family privacy policy. You can still check your assigned chores or pantry supplies!`,
        actionLabel: 'View My Tasks',
        actionTab: 'tasks',
      };
    }

    // 2. Main Household Scenario (Mom away, Dad low-salt, Grandma Rx, 4 guests, ₹5,000 budget)
    if (this._isMainScenario(lower)) {
      return this._generateMainScenarioResponse(activeMember);
    }

    // 3. Tasks & Chores Query
    if (lower.includes('task') || lower.includes('chore') || lower.includes('todo') || lower.includes('to do') || lower.includes('pending')) {
      const tasks = householdService.getState().tasks.filter(t => t.status === 'pending');
      const myTasks = tasks.filter(t => t.assignedTo === activeMember.id);
      
      if (activeMember.role.includes('Teenager')) {
        return {
          type: 'text',
          text: `You have ${myTasks.length} pending chores right now:`,
          items: myTasks.map(t => `${t.title} (${t.dueDate})`),
          actionLabel: 'Open Tasks',
          actionTab: 'tasks',
        };
      }

      return {
        type: 'text',
        text: `There are ${tasks.length} pending household tasks across the family:`,
        items: tasks.map(t => `${t.title} — assigned to ${t.assignedToName} (${t.dueDate})`),
        actionLabel: 'Open Tasks',
        actionTab: 'tasks',
      };
    }

    // 4. Pantry & Groceries Query
    if (lower.includes('grocery') || lower.includes('groceries') || lower.includes('buy') || lower.includes('pantry') || lower.includes('stock') || lower.includes('food')) {
      const lowStock = householdService.getState().inventory.filter(i => i.status === 'low' || i.status === 'out_of_stock');
      return {
        type: 'text',
        text: `Here are the items that need restocking, keeping Dad's verified low-salt diet in mind:`,
        items: lowStock.map(i => `${i.name} (${i.quantity} left — ${i.dietaryNote})`),
        actionLabel: 'View Pantry',
        actionTab: 'pantry',
      };
    }

    // 5. Budget Query (Authorized)
    if (isBudgetQuery) {
      const isPlanApplied = householdService.getState().isPlanApplied;
      const remaining = isPlanApplied ? '₹2,400' : '₹5,000';
      const planned = isPlanApplied ? '₹2,600 (Groceries ₹1,700 + Medicine ₹900)' : '₹0';

      return {
        type: 'text',
        text: `Your weekly budget envelope is ₹5,000.\n• Planned outlay: ${planned}\n• Estimated remaining: ${remaining}\n\nThe remaining balance provides a safe buffer for any unexpected weekend needs.`,
        actionLabel: 'View Finances',
        actionTab: 'finance',
      };
    }

    // 6. Appliances / Maintenance Query
    if (lower.includes('maintenance') || lower.includes('appliance') || lower.includes('ac') || lower.includes('service') || lower.includes('warranty')) {
      return {
        type: 'text',
        text: `The Guest Bedroom AC has an active Daikin warranty (#DOC-WAR-03). Its pre-arrival filter service is scheduled for Friday 10:00 AM before relatives arrive. All other appliances are operating normally.`,
        actionLabel: 'View Appliances',
        actionTab: 'home',
      };
    }

    // 7. General Friendly Fallback
    return {
      type: 'text',
      text: `I've noted that for the household. You can tell me what changed (like member availability, unexpected guests, or dietary notes) or ask what needs to happen.`,
      actionLabel: 'Open Today Overview',
      actionTab: 'today',
    };
  }

  _isMainScenario(lower) {
    return (
      (lower.includes('mom') && lower.includes('relatives')) ||
      (lower.includes('low-salt') || lower.includes('low salt')) ||
      (lower.includes('grandma') && lower.includes('medicine')) ||
      (lower.includes('5000') || lower.includes('5,000')) ||
      lower.includes('plan for this weekend') ||
      lower.includes('guests')
    );
  }

  _generateMainScenarioResponse(activeMember) {
    const isParent = activeMember.permissions.canViewFinances;

    return {
      type: 'plan_proposal',
      title: 'Coordinated Weekend Action Plan',
      summary: 'I have updated our household context: Mom is away until Friday, 4 guests are arriving Saturday, and Dad has a low-salt constraint. Here is what needs to happen:',
      details: {
        groceries: [
          'Buy groceries scaled for 4 guests (+3L milk, fresh veggies, dry fruits).',
          'Strictly follow Dad’s cardiologist-verified low-salt restriction (DOC-MED-01).'
        ],
        tasks: [
          'Reassign Mom’s pending snack restocking to Rajesh.',
          'Assign Guest Bedroom setup & fresh linen to Aarav (Friday after 4:00 PM).',
          'Rajesh to handle grocery procurement on Thursday.'
        ],
        finance: isParent ? {
          budget: '₹5,000 weekly budget',
          groceries: '₹1,700 (4 guests + low-salt produce)',
          medicine: '₹900 (Grandma monthly BP refill)',
          remaining: '₹2,400 remaining balance (safe buffer)'
        } : null,
        maintenance: [
          'Schedule Daikin AC inspection & filter tune-up for Friday 10:00 AM under warranty.'
        ],
        timeline: [
          { day: 'Wednesday', text: "Grandma's medicine refill delivery (₹900)" },
          { day: 'Thursday', text: 'Hospitality grocery shopping (₹1,700)' },
          { day: 'Friday 10 AM', text: 'Daikin AC filter cleaning' },
          { day: 'Friday 4 PM', text: 'Guest room preparation (Aarav)' },
          { day: 'Friday 7 PM', text: 'Mom returns from work trip' },
          { day: 'Saturday 11 AM', text: '4 Relatives arrive for weekend stay' },
        ]
      },
      actionable: true,
    };
  }
}

export const agentService = new AgentService();
