import { describe, expect, it } from 'vitest';
import {
  buildMaintenanceSummary,
  costMajorToMinor,
  formatCost,
  formatWarrantyDate,
  getNextIssueStatus,
  toDateInputValue,
  warrantyTone,
} from './maintenance-utils';

describe('maintenance utils', () => {
  it('normalizes date inputs to YYYY-MM-DD', () => {
    expect(toDateInputValue(null)).toBe('');
    expect(toDateInputValue('2026-10-15')).toBe('2026-10-15');
    expect(toDateInputValue('2026-10-15T00:00:00')).toBe('2026-10-15');
    expect(toDateInputValue('not-a-date')).toBe('');
  });

  it('formats a warranty date for display', () => {
    expect(formatWarrantyDate(null)).toBe('No warranty date');
    expect(formatWarrantyDate('2026-11-02')).toMatch(/Nov|2026/);
  });

  it('grades warranty urgency by days remaining', () => {
    expect(warrantyTone(3)).toBe('urgent');
    expect(warrantyTone(20)).toBe('watch');
    expect(warrantyTone(90)).toBe('ok');
  });

  it('formats minor-unit costs', () => {
    expect(formatCost(null)).toBe('Cost not recorded');
    expect(formatCost(2500, 'USD')).toMatch(/25/);
  });

  it('converts major-unit input to minor units', () => {
    expect(costMajorToMinor('')).toBeNull();
    expect(costMajorToMinor('25')).toBe(2500);
    expect(costMajorToMinor('-5')).toBeNull();
    expect(costMajorToMinor('abc')).toBeNull();
  });

  it('advances issue status through the workflow', () => {
    expect(getNextIssueStatus('Open')).toBe('InProgress');
    expect(getNextIssueStatus('InProgress')).toBe('Resolved');
    expect(getNextIssueStatus('Resolved')).toBe('Closed');
    expect(getNextIssueStatus('Closed')).toBe('Open');
  });

  it('summarizes maintenance activity', () => {
    const summary = buildMaintenanceSummary(
      [{ appliance_id: 'a1', name: 'Dishwasher', brand: null, model: null, purchased_at: null, warranty_ends_at: null }],
      [
        { issue_id: 'i1', description: 'Noise', status: 'Open', priority: 'High', reported_by: null, accountable_to: null, appliance_id: null, created_at: '2026-09-01T00:00:00' },
        { issue_id: 'i2', description: 'Leak', status: 'Closed', priority: 'Normal', reported_by: null, accountable_to: null, appliance_id: null, created_at: '2026-09-01T00:00:00' },
      ],
      [{ appliance_id: 'a1', name: 'Dishwasher', brand: null, model: null, warranty_ends_at: '2026-10-01', days_remaining: 7 }],
      [{ repair_id: 'r1', serviced_at: '2026-09-10', provider: 'Pro', cost_minor: 5000, currency: 'USD', notes: null, appliance_id: 'a1', logged_by: null }],
    );

    expect(summary).toEqual({ appliances: 1, openIssues: 1, expiringSoon: 1, repairSpendMinor: 5000, repairCurrency: 'USD' });
  });
});
