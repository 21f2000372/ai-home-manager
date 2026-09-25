import type { Appliance, ExpiringWarranty, IssueStatus, MaintenanceIssue, MaintenanceSummary, Repair } from './maintenance-types';

export type WarrantyTone = 'urgent' | 'watch' | 'ok';

export function toDateInputValue(value: string | null | undefined): string {
  if (!value) return '';
  const match = value.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString().slice(0, 10);
}

export function formatWarrantyDate(value: string | null): string {
  if (!value) return 'No warranty date';
  const normalized = toDateInputValue(value);
  const date = new Date(`${normalized}T00:00:00`);
  if (Number.isNaN(date.getTime())) return 'No warranty date';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

export function warrantyTone(daysRemaining: number): WarrantyTone {
  if (daysRemaining <= 7) return 'urgent';
  if (daysRemaining <= 30) return 'watch';
  return 'ok';
}

export function formatCost(costMinor: number | null | undefined, currency = 'USD'): string {
  if (costMinor === null || costMinor === undefined) return 'Cost not recorded';
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(costMinor / 100);
  } catch {
    return `${(costMinor / 100).toFixed(2)} ${currency}`;
  }
}

export function costMajorToMinor(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseFloat(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed * 100);
}

export function getNextIssueStatus(status: IssueStatus): IssueStatus {
  switch (status) {
    case 'Open':
      return 'InProgress';
    case 'InProgress':
      return 'Resolved';
    case 'Resolved':
      return 'Closed';
    case 'Closed':
      return 'Open';
  }
}

export function buildMaintenanceSummary(
  appliances: Appliance[],
  issues: MaintenanceIssue[],
  expiring: ExpiringWarranty[],
  repairs: Repair[],
): MaintenanceSummary {
  const repairSpendMinor = repairs.reduce((total, repair) => total + (repair.cost_minor ?? 0), 0);
  return {
    appliances: appliances.length,
    openIssues: issues.filter((issue) => issue.status === 'Open' || issue.status === 'InProgress').length,
    expiringSoon: expiring.length,
    repairSpendMinor,
    repairCurrency: repairs.find((repair) => repair.currency)?.currency ?? 'USD',
  };
}
