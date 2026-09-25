export type IssueStatus = 'Open' | 'InProgress' | 'Resolved' | 'Closed';
export type MaintenancePriority = 'Low' | 'Normal' | 'High';

export type Appliance = {
  appliance_id: string;
  name: string;
  brand: string | null;
  model: string | null;
  purchased_at: string | null;
  warranty_ends_at: string | null;
};

export type CreateApplianceInput = {
  name: string;
  brand?: string;
  model?: string;
  purchased_at?: string;
  warranty_ends_at?: string;
};

export type UpdateApplianceInput = Partial<CreateApplianceInput>;

export type ExpiringWarranty = {
  appliance_id: string;
  name: string;
  brand: string | null;
  model: string | null;
  warranty_ends_at: string;
  days_remaining: number;
};

export type MaintenanceIssue = {
  issue_id: string;
  description: string;
  status: IssueStatus;
  priority: MaintenancePriority;
  reported_by: string | null;
  accountable_to: string | null;
  appliance_id: string | null;
  created_at: string;
};

export type CreateIssueInput = {
  description: string;
  priority: MaintenancePriority;
  appliance_id?: string | null;
  accountable_to?: string | null;
};

export type UpdateIssueInput = {
  description?: string;
  status?: IssueStatus;
  priority?: MaintenancePriority;
  accountable_to?: string | null;
};

export type IssueFilters = {
  status?: IssueStatus | 'All';
  appliance_id?: string;
};

export type Repair = {
  repair_id: string;
  serviced_at: string;
  provider: string | null;
  cost_minor: number | null;
  currency: string;
  notes: string | null;
  appliance_id: string | null;
  logged_by: string | null;
};

export type LogRepairInput = {
  serviced_at: string;
  appliance_id?: string | null;
  provider?: string;
  cost_minor?: number | null;
  currency?: string;
  notes?: string;
};

export type MaintenanceSummary = {
  appliances: number;
  openIssues: number;
  expiringSoon: number;
  repairSpendMinor: number;
  repairCurrency: string;
};
