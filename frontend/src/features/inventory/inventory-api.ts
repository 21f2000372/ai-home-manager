import { request } from '@/lib/api/request';

export type InventoryItem = {
  item_id: string;
  name: string;
  quantity: number;
  unit: string | null;
  low_stock_threshold: number | null;
};

export type InventoryInput = {
  name: string;
  quantity: number;
  unit?: string | null;
  low_stock_threshold?: number | null;
};

export type GroceryItem = {
  grocery_item_id: string;
  name: string;
  quantity: number | null;
  unit: string | null;
  purchased: boolean;
  added_by?: string | null;
  added_by_id?: string | null;
};

export type GroceryInput = {
  name: string;
  quantity?: number | null;
  unit?: string | null;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function getInventory() {
  return request<InventoryItem[]>('/api/inventory', {}, requestContext());
}

export function getLowStock() {
  return request<InventoryItem[]>('/api/inventory/low-stock', {}, requestContext());
}

export function addInventory(input: InventoryInput) {
  return request<InventoryItem>('/api/inventory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}

export function updateInventory(itemId: string, input: InventoryInput) {
  return request<InventoryItem>(`/api/inventory/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}

export function deleteInventory(itemId: string) {
  return request<{ message: string }>(`/api/inventory/${itemId}`, { method: 'DELETE' }, requestContext());
}

export function getGroceries(includePurchased = true) {
  return request<GroceryItem[]>(`/api/inventory/groceries?include_purchased=${includePurchased}`, {}, requestContext());
}

export function addGrocery(input: GroceryInput) {
  return request<GroceryItem>('/api/inventory/groceries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}

export function updateGrocery(itemId: string, input: GroceryInput) {
  return request<GroceryItem>(`/api/inventory/groceries/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, requestContext());
}

export function setGroceryPurchased(itemId: string, purchased: boolean) {
  return request<GroceryItem>(`/api/inventory/groceries/${itemId}/purchase`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ purchased }),
  }, requestContext());
}

export function deleteGrocery(itemId: string) {
  return request<{ message: string }>(`/api/inventory/groceries/${itemId}`, { method: 'DELETE' }, requestContext());
}
