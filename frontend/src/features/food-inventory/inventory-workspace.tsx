import { FormEvent, useState } from 'react';
import { Check, LoaderCircle, Package, Plus, Trash2, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { HouseholdChat } from '@/components/ai/household-chat';
import { ApiError } from '@/lib/api/request';
import {
  addGrocery,
  addOrUpdateStock,
  deleteGrocery,
  deleteInventoryItem,
  getGroceries,
  getInventory,
  toggleGroceryPurchased,
  type GroceryItem,
  type InventoryItem,
} from './inventory-api';

const inventoryKey = ['household', 'inventory'] as const;
const groceryKey = ['household', 'groceries'] as const;

function isLowStock(item: InventoryItem) {
  return item.low_stock_threshold != null && item.quantity <= item.low_stock_threshold;
}

export function InventoryWorkspace({ showGrocery = false }: { showGrocery?: boolean }) {
  const queryClient = useQueryClient();

  const inventoryQuery = useQuery({ queryKey: inventoryKey, queryFn: getInventory });
  const groceryQuery = useQuery({ queryKey: groceryKey, queryFn: () => getGroceries(true) });

  const [stockForm, setStockForm] = useState({ name: '', quantity: '', unit: '', low_stock_threshold: '' });
  const [groceryForm, setGroceryForm] = useState({ name: '', quantity: '', unit: '' });

  const addStockMutation = useMutation({
    mutationFn: addOrUpdateStock,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKey });
      setStockForm({ name: '', quantity: '', unit: '', low_stock_threshold: '' });
    },
  });

  const deleteStockMutation = useMutation({
    mutationFn: deleteInventoryItem,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKey });
    },
  });

  const addGroceryMutation = useMutation({
    mutationFn: addGrocery,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: groceryKey });
      setGroceryForm({ name: '', quantity: '', unit: '' });
    },
  });

  const toggleGroceryMutation = useMutation({
    mutationFn: ({ id, purchased }: { id: string; purchased: boolean }) => toggleGroceryPurchased(id, purchased),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: groceryKey });
    },
  });

  const deleteGroceryMutation = useMutation({
    mutationFn: deleteGrocery,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: groceryKey });
    },
  });

  function submitStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!stockForm.name.trim() || stockForm.quantity === '') return;
    addStockMutation.mutate({
      name: stockForm.name,
      quantity: Number(stockForm.quantity),
      unit: stockForm.unit || undefined,
      low_stock_threshold: stockForm.low_stock_threshold ? Number(stockForm.low_stock_threshold) : undefined,
    });
  }

  function submitGrocery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!groceryForm.name.trim()) return;
    addGroceryMutation.mutate({
      name: groceryForm.name,
      quantity: groceryForm.quantity ? Number(groceryForm.quantity) : undefined,
      unit: groceryForm.unit || undefined,
    });
  }

  const error =
    inventoryQuery.error ??
    groceryQuery.error ??
    addStockMutation.error ??
    deleteStockMutation.error ??
    addGroceryMutation.error ??
    toggleGroceryMutation.error ??
    deleteGroceryMutation.error;
  const errorMessage = error instanceof ApiError ? error.message : error ? 'HomeOps could not load food & inventory. Please try again.' : null;

  const items = inventoryQuery.data ?? [];
  const lowStockCount = items.filter(isLowStock).length;
  const groceries = groceryQuery.data ?? [];

  return (
    <section className="space-y-6">
      <div className="border-b border-[var(--line)] pb-6">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]">Food & inventory</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{showGrocery ? 'Grocery list' : 'Household inventory'}</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 muted">Live stock and shopping data from the backend. Track what is in the house and what to buy next.</p>
      </div>

      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Inventory stock */}
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Stock" detail={lowStockCount > 0 ? `${items.length} items · ${lowStockCount} low` : `${items.length} items`} action={<Package size={18} className="text-[#5E9278]" />} />
          {inventoryQuery.isLoading ? (
            <div className="mt-6 flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading inventory</div>
          ) : items.length ? (
            <div className="mt-5 space-y-2">
              {items.map((item) => (
                <div key={item.item_id} className="flex items-center gap-3 rounded-xl border border-[var(--line)] p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-[var(--ink)]">{item.name}</p>
                    <p className="text-xs muted">{item.quantity}{item.unit ? ` ${item.unit}` : ''}{item.low_stock_threshold != null ? ` · threshold ${item.low_stock_threshold}` : ''}</p>
                  </div>
                  {isLowStock(item) && <span className="shrink-0 rounded-full bg-[#F6EADB] px-2 py-0.5 text-xs font-semibold text-[#8A5D2F]">Low</span>}
                  <button type="button" onClick={() => deleteStockMutation.mutate(item.item_id)} aria-label={`Delete ${item.name}`} className="grid size-8 shrink-0 place-items-center rounded-full text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[#8B3F36]"><Trash2 size={15} /></button>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-6 text-sm muted">No inventory items yet. Add one below.</p>
          )}

          <form className="mt-5 space-y-2 border-t border-[var(--line)] pt-4" onSubmit={submitStock}>
            <div className="flex flex-wrap gap-2">
              <input value={stockForm.name} onChange={(e) => setStockForm((f) => ({ ...f, name: e.target.value }))} placeholder="Item name" aria-label="Item name" className="task-input min-w-32 flex-1 py-2" />
              <input value={stockForm.quantity} onChange={(e) => setStockForm((f) => ({ ...f, quantity: e.target.value }))} placeholder="Qty" aria-label="Quantity" type="number" step="any" className="task-input w-20 py-2" />
              <input value={stockForm.unit} onChange={(e) => setStockForm((f) => ({ ...f, unit: e.target.value }))} placeholder="Unit" aria-label="Unit" className="task-input w-24 py-2" />
              <input value={stockForm.low_stock_threshold} onChange={(e) => setStockForm((f) => ({ ...f, low_stock_threshold: e.target.value }))} placeholder="Low at" aria-label="Low stock threshold" type="number" step="any" className="task-input w-24 py-2" />
            </div>
            <Button type="submit" disabled={addStockMutation.isPending || !stockForm.name.trim() || stockForm.quantity === ''} className="w-full sm:w-auto"><Plus size={16} />Add / update stock</Button>
          </form>
        </Card>

        {/* Grocery list */}
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Grocery list" detail={`${groceries.filter((g) => !g.purchased).length} to buy`} />
          {groceryQuery.isLoading ? (
            <div className="mt-6 flex min-h-32 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />Loading grocery list</div>
          ) : groceries.length ? (
            <div className="mt-5 space-y-2">
              {groceries.map((g: GroceryItem) => (
                <div key={g.grocery_item_id} className="flex items-center gap-3 rounded-xl border border-[var(--line)] p-3">
                  <button type="button" onClick={() => toggleGroceryMutation.mutate({ id: g.grocery_item_id, purchased: !g.purchased })} aria-label={g.purchased ? `Mark ${g.name} not purchased` : `Mark ${g.name} purchased`} className={`grid size-5 shrink-0 place-items-center rounded-full border ${g.purchased ? 'border-[#3D5F4E] bg-[#E4F0E8] text-[#3D5F4E]' : 'border-[var(--line)] text-transparent hover:border-[#5E9278]'}`}><Check size={13} /></button>
                  <div className="min-w-0 flex-1">
                    <p className={`truncate text-sm font-semibold ${g.purchased ? 'text-[var(--muted)] line-through' : 'text-[var(--ink)]'}`}>{g.name}</p>
                    {(g.quantity || g.unit) && <p className="text-xs muted">{g.quantity ?? ''}{g.unit ? ` ${g.unit}` : ''}</p>}
                  </div>
                  <button type="button" onClick={() => deleteGroceryMutation.mutate(g.grocery_item_id)} aria-label={`Remove ${g.name}`} className="grid size-8 shrink-0 place-items-center rounded-full text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[#8B3F36]"><X size={15} /></button>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-6 text-sm muted">Grocery list is empty. Add an item below.</p>
          )}

          <form className="mt-5 space-y-2 border-t border-[var(--line)] pt-4" onSubmit={submitGrocery}>
            <div className="flex flex-wrap gap-2">
              <input value={groceryForm.name} onChange={(e) => setGroceryForm((f) => ({ ...f, name: e.target.value }))} placeholder="Item name" aria-label="Grocery item name" className="task-input min-w-32 flex-1 py-2" />
              <input value={groceryForm.quantity} onChange={(e) => setGroceryForm((f) => ({ ...f, quantity: e.target.value }))} placeholder="Qty" aria-label="Grocery quantity" type="number" step="any" className="task-input w-20 py-2" />
              <input value={groceryForm.unit} onChange={(e) => setGroceryForm((f) => ({ ...f, unit: e.target.value }))} placeholder="Unit" aria-label="Grocery unit" className="task-input w-24 py-2" />
            </div>
            <Button type="submit" disabled={addGroceryMutation.isPending || !groceryForm.name.trim()} className="w-full sm:w-auto"><Plus size={16} />Add to grocery list</Button>
          </form>
        </Card>
      </div>

      <HouseholdChat
        title="Ask about food & inventory"
        description="Ask what is running low, or add items to the grocery list. The assistant responds through the household agent."
        onMessageProcessed={() => {
          void queryClient.invalidateQueries({ queryKey: inventoryKey });
          void queryClient.invalidateQueries({ queryKey: groceryKey });
        }}
      />
    </section>
  );
}
