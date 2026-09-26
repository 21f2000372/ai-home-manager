import { request } from '@/lib/api/request';

export type Expense = {
  expense_id: string;
  amount_minor: number;
  currency: string;
  category: string;
  description: string | null;
  occurred_at: string;
  recorded_by: string;
  document_id: string | null;
};

export type Budget = {
  budget_id: string;
  category: string;
  limit_minor: number;
  currency: string;
  period: string;
  period_start: string | null;
  period_end: string | null;
};

export type RecurringBill = {
  bill_id: string;
  payee: string;
  expected_amount_minor: number;
  currency: string;
  category: string | null;
  due_at: string;
  recurrence: string;
};

export type BudgetStatus = {
  category: string;
  month: number;
  year: number;
  limit_minor: number;
  spent_minor: number;
  remaining_minor: number;
  has_budget: boolean;
  is_exceeded: boolean;
};

export type UpcomingBill = {
  bill_id: string;
  payee: string;
  expected_amount_minor: number;
  due_at: string;
  days_remaining: number;
  category: string | null;
};

export type ExpenseInput = Pick<Expense, 'amount_minor' | 'currency' | 'category' | 'description' | 'occurred_at'>;
export type BudgetInput = { category: string; limit_minor: number; currency: string; month: number; year: number };
export type BillInput = Pick<RecurringBill, 'payee' | 'expected_amount_minor' | 'currency' | 'category' | 'due_at' | 'recurrence'>;

const context = () => ({ correlationId: crypto.randomUUID() });
const json = (method: 'POST' | 'PUT', body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const getExpenses = (month?: number, year?: number) => {
  const search = new URLSearchParams();
  if (month) search.set('month', String(month));
  if (year) search.set('year', String(year));
  const suffix = search.size ? `?${search}` : '';
  return request<Expense[]>(`/api/finance/expenses${suffix}`, {}, context());
};
export const createExpense = (input: ExpenseInput) => request<Expense>('/api/finance/expenses', json('POST', input), context());
export const updateExpense = (id: string, input: ExpenseInput) => request<Expense>(`/api/finance/expenses/${id}`, json('PUT', input), context());
export const deleteExpense = (id: string) => request<{ message: string }>(`/api/finance/expenses/${id}`, { method: 'DELETE' }, context());

export const getBudgets = () => request<Budget[]>('/api/finance/budgets', {}, context());
export const setBudget = (input: BudgetInput) => request<Budget>('/api/finance/budgets', json('POST', input), context());
export const deleteBudget = (id: string) => request<{ message: string }>(`/api/finance/budgets/${id}`, { method: 'DELETE' }, context());
export const getBudgetStatus = (category: string, month: number, year: number) => request<BudgetStatus>(`/api/finance/budgets/status?${new URLSearchParams({ category, month: String(month), year: String(year) })}`, {}, context());

export const getBills = () => request<RecurringBill[]>('/api/finance/bills', {}, context());
export const createBill = (input: BillInput) => request<RecurringBill>('/api/finance/bills', json('POST', input), context());
export const updateBill = (id: string, input: BillInput) => request<RecurringBill>(`/api/finance/bills/${id}`, json('PUT', input), context());
export const deleteBill = (id: string) => request<{ message: string }>(`/api/finance/bills/${id}`, { method: 'DELETE' }, context());
export const getUpcomingBills = (days = 7) => request<UpcomingBill[]>(`/api/finance/bills/upcoming?days=${days}`, {}, context());
