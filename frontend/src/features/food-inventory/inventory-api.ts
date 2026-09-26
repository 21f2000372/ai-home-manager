import { request } from '@/lib/api/request';
import type {
  AddGroceryInput,
  AddInventoryInput,
  GroceryItem,
  InventoryItem,
} from './inventory-types';

export type { AddGroceryInput, AddInventoryInput, GroceryItem, InventoryItem } from './inventory-types';

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

const base = '/api/inventory';

// --- Inventory stock ---

export function getInventory() {
  return request<InventoryItem[]>(base, {}, requestContext());
}

export function getLowStock() {
  return request<InventoryItem[]>(`${base}/low-stock`, {}, requestContext());
}

export function addOrUpdateStock(input: AddInventoryInput) {
  return request<InventoryItem>(
    base,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: input.name.trim(),
        quantity: input.quantity,
        unit: input.unit?.trim() || undefined,
        low_stock_threshold: input.low_stock_threshold ?? undefined,
      }),
    },
    requestContext(),
  );
}

export function deleteInventoryItem(itemId: string) {
  return request<{ message: string }>(`${base}/${itemId}`, { method: 'DELETE' }, requestContext());
}

// --- Grocery list ---

export function getGroceries(includePurchased = true) {
  const params = new URLSearchParams();
  params.set('include_purchased', String(includePurchased));
  return request<GroceryItem[]>(`${base}/groceries?${params.toString()}`, {}, requestContext());
}

export function addGrocery(input: AddGroceryInput) {
  return request<GroceryItem>(
    `${base}/groceries`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: input.name.trim(),
        quantity: input.quantity ?? undefined,
        unit: input.unit?.trim() || undefined,
      }),
    },
    requestContext(),
  );
}

export function toggleGroceryPurchased(groceryItemId: string, purchased: boolean) {
  return request<GroceryItem>(
    `${base}/groceries/${groceryItemId}/purchase`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ purchased }),
    },
    requestContext(),
  );
}

export function deleteGrocery(groceryItemId: string) {
  return request<{ message: string }>(`${base}/groceries/${groceryItemId}`, { method: 'DELETE' }, requestContext());
}
