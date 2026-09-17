// Initial Synthetic Data for The Sharma Family Household
export const INITIAL_HOUSEHOLD_DATA = {
  household: {
    id: "hh_sharma_01",
    name: "The Sharma Family",
    residence: "Flat 402, Green Meadows Residency",
    city: "Bengaluru, India",
    currency: "₹",
    budgetCycle: "Weekly",
    weeklyBudget: 5000,
    activeDietaryRestrictions: ["Dad: Strict Low-Sodium / Low-Salt (Verified Doc)"],
  },

  members: [
    {
      id: "rajesh",
      name: "Rajesh Sharma",
      relation: "Dad / Husband",
      role: "Parent / Administrator",
      avatar: "👨‍💼",
      color: "blue",
      clearance: "Full Admin",
      availability: "Available",
      statusText: "Working from home (Available for errands)",
      responsibilities: ["Grocery Procurement", "Financial Approvals", "Appliance Maintenance"],
      dietaryNotes: "Verified strict low-salt requirement (Cardiology guidance)",
      permissions: {
        canViewFinances: true,
        canApproveExpenses: true,
        canViewAllTasks: true,
        canAssignTasks: true,
        canViewMedicalDocs: true,
        canManageAppliances: true,
        canExecuteAgentPlan: true,
      },
    },
    {
      id: "priya",
      name: "Priya Sharma",
      relation: "Mom / Wife",
      role: "Parent / Administrator",
      avatar: "👩‍💼",
      color: "purple",
      clearance: "Full Admin",
      availability: "Away on Work Trip (Until Friday evening)",
      statusText: "Traveling out of town for business summit; returns Friday 7:00 PM",
      responsibilities: ["Meal Planning", "Elder Care Oversight", "Guest Hospitality Coordination"],
      dietaryNotes: "Standard vegetarian",
      permissions: {
        canViewFinances: true,
        canApproveExpenses: true,
        canViewAllTasks: true,
        canAssignTasks: true,
        canViewMedicalDocs: true,
        canManageAppliances: true,
        canExecuteAgentPlan: true,
      },
    },
    {
      id: "aarav",
      name: "Aarav Sharma",
      relation: "Son (16 yrs)",
      role: "Teenager",
      avatar: "👦",
      color: "emerald",
      clearance: "Restricted (Chores & Shared Events Only)",
      availability: "Available after 4:00 PM",
      statusText: "School until 3:30 PM; Free on evenings & weekend",
      responsibilities: ["Guest Room Preparation", "Plant Watering", "Trash & Recycling", "Pet Care"],
      dietaryNotes: "No restrictions",
      permissions: {
        canViewFinances: false, // RESTRICTED
        canApproveExpenses: false,
        canViewAllTasks: false, // Sees only assigned and shared tasks
        canAssignTasks: false,
        canViewMedicalDocs: false,
        canManageAppliances: false,
        canExecuteAgentPlan: false,
      },
    },
    {
      id: "savitri",
      name: "Savitri Devi",
      relation: "Grandmother (74 yrs)",
      role: "Elder / Senior Family Member",
      avatar: "👵",
      color: "amber",
      clearance: "Healthcare & Schedule Only",
      availability: "Home / Resting",
      statusText: "Resting at home; needs daily BP & joint medication refill",
      responsibilities: ["Medication Adherence", "Light morning walks"],
      dietaryNotes: "Soft, mildly spiced vegetarian meals",
      permissions: {
        canViewFinances: false,
        canApproveExpenses: false,
        canViewAllTasks: false,
        canAssignTasks: false,
        canViewMedicalDocs: true,
        canManageAppliances: false,
        canExecuteAgentPlan: false,
      },
    },
  ],

  tasks: [
    {
      id: "tsk-001",
      title: "Water balcony plants & garden",
      category: "Routine",
      assignedTo: "aarav",
      assignedToName: "Aarav Sharma",
      dueDate: "Daily (5:00 PM)",
      status: "pending",
      priority: "medium",
      domain: "Home",
      notes: "Check drip irrigation timer",
    },
    {
      id: "tsk-002",
      title: "Review monthly broadband utility invoice",
      category: "Finance",
      assignedTo: "rajesh",
      assignedToName: "Rajesh Sharma",
      dueDate: "Thursday",
      status: "pending",
      priority: "low",
      domain: "Finance",
      notes: "Automated payment scheduled",
    },
    {
      id: "tsk-003",
      title: "Restock weekly pantry snacks",
      category: "Food",
      assignedTo: "priya",
      assignedToName: "Priya Sharma",
      dueDate: "Wednesday",
      status: "pending",
      priority: "medium",
      domain: "Food",
      notes: "Original assignment before travel",
    },
  ],

  inventory: [
    { id: "inv-1", name: "Basmati Rice", category: "Grains", quantity: "4 kg", status: "available", minThreshold: "2 kg", dietaryNote: "Standard" },
    { id: "inv-2", name: "Fresh Cow Milk", category: "Dairy", quantity: "0.5 Litre", status: "low", minThreshold: "2 Litres", dietaryNote: "Need +3L for 4 guests" },
    { id: "inv-3", name: "Vegetables (Tomatoes, Onions, Paneer)", category: "Produce", quantity: "1.2 kg", status: "low", minThreshold: "4 kg", dietaryNote: "Fresh veggies for 4 visiting guests" },
    { id: "inv-4", name: "Cooking Oil (Cold Pressed Sunflower)", category: "Oils", quantity: "2 Litres", status: "available", minThreshold: "1 Litre", dietaryNote: "Heart-healthy" },
    { id: "inv-5", name: "Low-Sodium Rock Salt & Herb Seasonings", category: "Spices", quantity: "250g", status: "available", minThreshold: "100g", dietaryNote: "Verified Dad low-salt constraint" },
    { id: "inv-6", name: "Toor Dal (Lentils)", category: "Grains", quantity: "2.5 kg", status: "available", minThreshold: "1 kg", dietaryNote: "High protein" },
    { id: "inv-7", name: "Tea Leaves (Assam CTC) & Cardamom", category: "Beverages", quantity: "300g", status: "available", minThreshold: "200g", dietaryNote: "Chai for guest hospitality" },
    { id: "inv-8", name: "Guest Refreshment Snacks & Dry Fruits", category: "Hospitality", quantity: "0g", status: "out_of_stock", minThreshold: "500g", dietaryNote: "Needs procurement for 4 relatives" },
    { id: "inv-9", name: "Laundry Detergent & Fabric Conditioner", category: "Cleaning", quantity: "3 kg", status: "available", minThreshold: "1 kg", dietaryNote: "For guest linen wash" },
    { id: "inv-10", name: "Grandma BP/Diabetes Maintenance Rx", category: "Health", quantity: "2 days left", status: "low", minThreshold: "7 days", dietaryNote: "Urgent monthly refill required" },
  ],

  finance: {
    weeklyBudget: 5000,
    currency: "₹",
    currentExpenses: 0,
    plannedExpenses: 0,
    estimatedRemaining: 5000,
    breakdown: [
      { id: "exp-0", item: "Baseline Week Allocation", category: "Budget", amount: 5000, date: "Monday", status: "allocated" }
    ],
    recentTransactions: [
      { id: "tx-1", title: "Society Maintenance Advance", amount: 2200, date: "Last Friday", category: "Housing", paidBy: "Rajesh" },
      { id: "tx-2", title: "Daily Organic Milk Delivery", amount: 450, date: "Sunday", category: "Food", paidBy: "Priya" },
    ]
  },

  maintenance: [
    {
      id: "app-1",
      name: "Guest Bedroom AC (Daikin 1.5T Inverter)",
      category: "HVAC",
      location: "Guest Bedroom",
      status: "service_required",
      statusLabel: "Service Required",
      issueDescription: "Filter dirty; pre-arrival cooling inspection needed before 4 relatives arrive",
      lastService: "6 months ago",
      warrantyStatus: "Active till Dec 2027",
      warrantyDocId: "DOC-WAR-03",
      scheduledDate: null,
    },
    {
      id: "app-2",
      name: "Master Bedroom AC (Voltas 1.5T)",
      category: "HVAC",
      location: "Master Bedroom",
      status: "optimal",
      statusLabel: "Optimal",
      issueDescription: "Operating within normal parameters",
      lastService: "2 months ago",
      warrantyStatus: "Active till Aug 2028",
      scheduledDate: null,
    },
    {
      id: "app-3",
      name: "Refrigerator (Samsung 415L Frost Free)",
      category: "Kitchen",
      location: "Kitchen",
      status: "optimal",
      statusLabel: "Optimal (3°C / -18°C)",
      issueDescription: "Compressor healthy, ample storage for guest preparations",
      lastService: "Annual check Jan 2026",
      warrantyStatus: "10 Yr Compressor Warranty",
      scheduledDate: null,
    },
    {
      id: "app-4",
      name: "RO Water Purifier (Kent Grand+)",
      category: "Water",
      location: "Kitchen",
      status: "optimal",
      statusLabel: "Optimal (TDS: 85 ppm)",
      issueDescription: "Sediment and carbon filters replaced last month",
      lastService: "1 month ago",
      warrantyStatus: "Annual AMC Active",
      scheduledDate: null,
    },
    {
      id: "app-5",
      name: "Washing Machine (LG 8kg Front Load)",
      category: "Laundry",
      location: "Utility Area",
      status: "optimal",
      statusLabel: "Ready for Guest Linen Wash",
      issueDescription: "Clean drum cycle completed",
      lastService: "3 months ago",
      warrantyStatus: "Direct Drive 10yr Warranty",
      scheduledDate: null,
    },
  ],

  schedule: [
    {
      id: "sch-1",
      title: "Aarav Inter-School Football Match",
      day: "Thursday",
      time: "4:30 PM - 6:00 PM",
      attendees: ["aarav"],
      type: "school",
      domain: "Tasks & Schedule",
      location: "School Sports Complex",
    },
    {
      id: "sch-2",
      title: "Priya Returning from Work Trip",
      day: "Friday",
      time: "7:00 PM",
      attendees: ["priya"],
      type: "travel",
      domain: "People & Permissions",
      location: "Kempegowda Int'l Airport (BLR)",
    },
    {
      id: "sch-3",
      title: "4 Relatives Arrive for Weekend Stay",
      day: "Saturday",
      time: "11:00 AM",
      attendees: ["rajesh", "priya", "aarav", "savitri"],
      type: "guest",
      domain: "Food & Hospitality",
      location: "Home (Green Meadows)",
    },
  ],

  documents: [
    {
      id: "DOC-MED-01",
      title: "Dr. Verma Cardiology Consultation - Dad Dietary Restriction",
      category: "Medical & Health",
      verified: true,
      verifiedBy: "Dr. K. Verma, MD Cardiology, Manipal Hospital",
      verificationDate: "15 Jan 2026",
      extractedFacts: {
        subject: "Rajesh Sharma (Dad)",
        restriction: "Strict Low-Sodium / Low-Salt Diet",
        threshold: "Maximum 1,500 mg sodium daily",
        prohibitedItems: ["High-sodium processed snacks", "Heavy table salt", "Pickles/Papad with sodium", "MSG"],
        recommendedSubstitutes: ["Rock salt in moderation", "Lemon juice", "Herbs & cumin", "Fresh home-cooked dishes"]
      },
      summary: "Verified clinical directive mandating low-salt preparation for all household and guest meals involving Rajesh.",
      tags: ["Dietary", "Health", "Verified", "High-Priority"]
    },
    {
      id: "DOC-MED-02",
      title: "Grandma Monthly Prescription & Drug Schedule",
      category: "Medical & Health",
      verified: true,
      verifiedBy: "Apollo Clinic Geriatric Care",
      verificationDate: "02 Feb 2026",
      extractedFacts: {
        subject: "Savitri Devi (Grandma)",
        medications: ["Telmisartan 40mg (BP)", "Metformin 500mg SR", "Calcium + D3 Supplement"],
        monthlyEstimate: "₹900",
        refillDue: "Wednesday (2 days supply remaining)"
      },
      summary: "Mandatory monthly prescription refill protocol for Savitri Devi.",
      tags: ["Prescription", "Elder Care", "Budget ₹900"]
    },
    {
      id: "DOC-WAR-03",
      title: "Daikin Inverter AC Warranty Certificate & AMC",
      category: "Appliances & Warranty",
      verified: true,
      verifiedBy: "Daikin India Authorized Service Network",
      verificationDate: "10 Dec 2024",
      extractedFacts: {
        appliance: "Guest Bedroom 1.5T AC (Model FTKM50)",
        coverage: "Compressor 5-Yr, PCB 5-Yr, 2 Free Annual Services",
        tollFreeService: "1800-180-3444",
        policyStatus: "Valid till Dec 2027"
      },
      summary: "Complimentary service available under active warranty terms.",
      tags: ["Warranty", "HVAC", "Guest Room"]
    },
    {
      id: "DOC-POL-04",
      title: "Household Financial Governance & Privacy Policy",
      category: "Household Rules",
      verified: true,
      verifiedBy: "Sharma Family Governance Charter",
      verificationDate: "01 Jan 2026",
      extractedFacts: {
        weeklyBudgetCap: "₹5,000",
        approvalRequiredFor: "Expenses over ₹1,000",
        roleAccess: {
          parents: "Unrestricted visibility into balances, receipts, and line items",
          teenagers: "Restricted from viewing financial balances, account totals, or expense records",
          elders: "Health and medical item visibility only"
        }
      },
      summary: "Explicit role-based privacy rules governing financial data dissemination.",
      tags: ["Privacy", "RBAC", "Governance"]
    },
    {
      id: "DOC-REC-05",
      title: "Reliance Fresh Supermarket Receipt #RF-88392",
      category: "Receipts & Bills",
      verified: true,
      verifiedBy: "Reliance Retail POS Engine",
      verificationDate: "Last Sunday",
      extractedFacts: {
        store: "Reliance Fresh, HSR Layout",
        totalPaid: "₹1,450",
        itemsCategorized: ["Atta 10kg", "Sunflower Oil 2L", "Detergent 3kg"]
      },
      summary: "Historical price baseline for household staple items.",
      tags: ["Receipt", "Finance", "Food Baseline"]
    },
  ],

  recentActivities: [
    {
      id: "act-1",
      timestamp: "Today, 8:30 AM",
      agent: "Context Agent",
      message: "Mom departure recorded: Out of town until Friday 7:00 PM.",
      category: "Context Update"
    },
    {
      id: "act-2",
      timestamp: "Today, 9:15 AM",
      agent: "Operations Agent",
      message: "Detected low supply of Grandma's BP medication (2 days left).",
      category: "Inventory Alert"
    },
    {
      id: "act-3",
      timestamp: "Today, 9:45 AM",
      agent: "Document Agent",
      message: "Indexed Dad's low-salt clinical directive from Dr. Verma.",
      category: "Knowledge Index"
    }
  ]
};
