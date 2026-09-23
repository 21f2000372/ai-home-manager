import { FormEvent, useState } from 'react';
import { AlertTriangle, Check, LoaderCircle, Package, Pencil, Plus, ShoppingBasket, Trash2, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge } from '@/components/design-system/badge';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { useSessionStore } from '@/stores/session-store';
import {
  addGrocery,
  addInventory,
  deleteGrocery,
  deleteInventory,
  getGroceries,
  getInventory,
  getLowStock,
  setGroceryPurchased,
  updateGrocery,
  updateInventory,
  type GroceryInput,
  type GroceryItem,
  type InventoryInput,
  type InventoryItem,
} from './inventory-api';

const inventoryKey = ['household', 'inventory'] as const;
const lowStockKey = ['household', 'inventory', 'low-stock'] as const;
const groceryKey = ['household', 'groceries'] as const;

type StockForm = { name: string; quantity: string; unit: string; threshold: string };
type GroceryForm = { name: string; quantity: string; unit: string };

const emptyStockForm: StockForm = { name: '', quantity: '1', unit: '', threshold: '' };
const emptyGroceryForm: GroceryForm = { name: '', quantity: '1', unit: '' };

export function InventoryWorkspace() {
  const queryClient = useQueryClient();
  const role = useSessionStore((state) => state.user?.role);
  const canManageStock = role === 'Admin' || role === 'Adult';
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [stockForm, setStockForm] = useState<StockForm>(emptyStockForm);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const inventoryQuery = useQuery({ queryKey: inventoryKey, queryFn: getInventory });
  const lowStockQuery = useQuery({ queryKey: lowStockKey, queryFn: getLowStock });
  const refreshInventory = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: inventoryKey }),
    queryClient.invalidateQueries({ queryKey: lowStockKey }),
  ]);

  const createMutation = useMutation({
    mutationFn: addInventory,
    onSuccess: async () => {
      await refreshInventory();
      closeComposer();
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ itemId, input }: { itemId: string; input: InventoryInput }) => updateInventory(itemId, input),
    onSuccess: async () => {
      await refreshInventory();
      closeComposer();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteInventory,
    onSuccess: async () => {
      await refreshInventory();
      setPendingDeleteId(null);
    },
  });

  const error = inventoryQuery.error ?? lowStockQuery.error ?? createMutation.error ?? updateMutation.error ?? deleteMutation.error;
  const errorMessage = messageFor(error, 'HomeOps could not update household stock. Please try again.');
  const isSaving = createMutation.isPending || updateMutation.isPending;

  function closeComposer() {
    setEditingItem(null);
    setStockForm(emptyStockForm);
    setIsComposerOpen(false);
  }

  function beginEdit(item: InventoryItem) {
    setEditingItem(item);
    setStockForm({
      name: item.name,
      quantity: String(item.quantity),
      unit: item.unit ?? '',
      threshold: item.low_stock_threshold === null ? '' : String(item.low_stock_threshold),
    });
    setIsComposerOpen(true);
  }

  function submitStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!stockForm.name.trim()) return;
    const quantity = Number(stockForm.quantity);
    const threshold = stockForm.threshold.trim() ? Number(stockForm.threshold) : null;
    if (!Number.isFinite(quantity) || quantity < 0 || (threshold !== null && (!Number.isFinite(threshold) || threshold < 0))) return;

    const input: InventoryInput = {
      name: stockForm.name.trim(),
      quantity,
      unit: stockForm.unit.trim() || null,
      low_stock_threshold: threshold,
    };
    if (editingItem) updateMutation.mutate({ itemId: editingItem.item_id, input });
    else createMutation.mutate(input);
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]"><Package size={14} />Food & inventory</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Household stock</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 muted">See what is in the house, restock essentials, and turn low stock into a shopping plan.</p>
        </div>
        {canManageStock && <Button onClick={() => isComposerOpen ? closeComposer() : setIsComposerOpen(true)}>{isComposerOpen ? <X size={16} /> : <Plus size={16} />}{isComposerOpen ? 'Close form' : 'Add stock'}</Button>}
      </header>

      {!canManageStock && <p className="rounded-xl bg-[#ECEAE4] px-4 py-3 text-sm muted">Your role can view household stock. An Adult or Admin can update stock levels.</p>}
      {errorMessage && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
      {isComposerOpen && <StockComposer form={stockForm} setForm={setStockForm} isEditing={Boolean(editingItem)} isSaving={isSaving} onSubmit={submitStock} />}

      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Card className="p-5 sm:p-6">
          <SectionHeading title="Current household stock" detail={`${inventoryQuery.data?.length ?? 0} tracked items`} />
          {inventoryQuery.isLoading ? <Loading label="Loading inventory" /> : inventoryQuery.data?.length ? <div className="mt-6 space-y-3">{inventoryQuery.data.map((item) => <InventoryRow key={item.item_id} item={item} canManage={canManageStock} isDeleting={deleteMutation.isPending && deleteMutation.variables === item.item_id} pendingDelete={pendingDeleteId === item.item_id} onEdit={() => beginEdit(item)} onRequestDelete={() => setPendingDeleteId(item.item_id)} onCancelDelete={() => setPendingDeleteId(null)} onConfirmDelete={() => deleteMutation.mutate(item.item_id)} />)}</div> : <Empty title="No stock tracked yet" detail="Add household items to make low-stock alerts useful." />}
        </Card>

        <div className="space-y-5">
          <Card className="p-5 sm:p-6">
            <SectionHeading title="Low-stock alerts" detail="Items at or below their threshold" action={<Badge tone={lowStockQuery.data?.length ? 'attention' : 'ready'}>{lowStockQuery.data?.length ?? 0} alerts</Badge>} />
            {lowStockQuery.isLoading ? <Loading label="Checking thresholds" /> : lowStockQuery.data?.length ? <div className="mt-5 space-y-3">{lowStockQuery.data.map((item) => <div key={item.item_id} className="flex gap-3 rounded-xl bg-[#FFF0E9] p-4"><AlertTriangle className="mt-0.5 shrink-0 text-[#C2603C]" size={18} /><div><p className="text-sm font-semibold text-[var(--ink)]">{item.name}</p><p className="mt-1 text-xs text-[#8D4B35]">{formatQuantity(item.quantity, item.unit)} remaining · threshold {formatQuantity(item.low_stock_threshold, item.unit)}</p></div></div>)}</div> : <Empty title="Everything is above threshold" detail="Low-stock alerts will appear here when needed." />}
          </Card>
          <Card className="bg-[#284837] p-6 text-white"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">Stock tip</p><p className="mt-3 text-lg font-bold leading-snug">Use a threshold for items you never want to run out of.</p><p className="mt-2 text-sm leading-6 text-[#D2E6D8]">For example, set rice to alert when only 1 kg remains.</p></Card>
        </div>
      </div>

      <GroceryPanel />
    </section>
  );
}

export function GroceryWorkspace() {
  return <section className="space-y-6"><header className="border-b border-[var(--line)] pb-6"><p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]"><ShoppingBasket size={14} />Food & inventory</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Grocery list</h1><p className="mt-2 max-w-xl text-sm leading-6 muted">Keep the next household shop clear and mark items as they are purchased.</p></header><GroceryPanel /></section>;
}

function StockComposer({ form, setForm, isEditing, isSaving, onSubmit }: { form: StockForm; setForm: (value: StockForm) => void; isEditing: boolean; isSaving: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Card className="p-5 sm:p-6"><form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}><label className="md:col-span-2"><span className="mb-1.5 block text-sm font-semibold">Item name</span><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="task-input" placeholder="e.g. Basmati rice" /></label><label><span className="mb-1.5 block text-sm font-semibold">{isEditing ? 'Current quantity' : 'Quantity to add'}</span><input required min="0" step="any" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} className="task-input" /></label><label><span className="mb-1.5 block text-sm font-semibold">Unit <span className="font-normal muted">(optional)</span></span><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} className="task-input" placeholder="kg, bottles, packs" /></label><label><span className="mb-1.5 block text-sm font-semibold">Low-stock threshold <span className="font-normal muted">(optional)</span></span><input min="0" step="any" type="number" value={form.threshold} onChange={(event) => setForm({ ...form, threshold: event.target.value })} className="task-input" placeholder="e.g. 1" /></label><div className="flex items-end justify-end"><Button type="submit" disabled={isSaving}>{isSaving && <LoaderCircle className="animate-spin" size={16} />}{isSaving ? 'Saving…' : isEditing ? 'Update stock' : 'Add stock'}</Button></div></form></Card>;
}

function InventoryRow({ item, canManage, isDeleting, pendingDelete, onEdit, onRequestDelete, onCancelDelete, onConfirmDelete }: { item: InventoryItem; canManage: boolean; isDeleting: boolean; pendingDelete: boolean; onEdit: () => void; onRequestDelete: () => void; onCancelDelete: () => void; onConfirmDelete: () => void }) {
  return <article className="rounded-2xl border border-[var(--line)] p-4"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-center gap-3"><div className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#E4F0E8] text-[#3D5F4E]"><Package size={18} /></div><div><p className="text-sm font-semibold text-[var(--ink)]">{item.name}</p><p className="mt-1 text-xs muted">{formatQuantity(item.quantity, item.unit)}{item.low_stock_threshold !== null ? ` · alert at ${formatQuantity(item.low_stock_threshold, item.unit)}` : ' · no alert threshold'}</p></div></div>{canManage && !pendingDelete && <div className="flex items-center gap-2"><Button tone="neutral" aria-label={`Edit ${item.name}`} onClick={onEdit}><Pencil size={16} />Edit</Button><Button tone="neutral" aria-label={`Delete ${item.name}`} onClick={onRequestDelete}><Trash2 size={16} />Delete</Button></div>}</div>{canManage && pendingDelete && <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-[var(--line)] pt-4"><p className="mr-auto text-sm muted">Remove {item.name} from household stock?</p><Button tone="neutral" onClick={onCancelDelete} disabled={isDeleting}>Cancel</Button><Button tone="danger" onClick={onConfirmDelete} disabled={isDeleting}>{isDeleting && <LoaderCircle className="animate-spin" size={16} />}Remove</Button></div>}</article>;
}

function GroceryPanel() {
  const queryClient = useQueryClient();
  const role = useSessionStore((state) => state.user?.role);
  const canManageGroceries = Boolean(role && role !== 'Guest');
  const [form, setForm] = useState<GroceryForm>(emptyGroceryForm);
  const [editingItem, setEditingItem] = useState<GroceryItem | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const groceriesQuery = useQuery({ queryKey: groceryKey, queryFn: () => getGroceries(true) });
  const refreshGroceries = () => queryClient.invalidateQueries({ queryKey: groceryKey });
  const createMutation = useMutation({ mutationFn: addGrocery, onSuccess: async () => { await refreshGroceries(); resetForm(); } });
  const updateMutation = useMutation({ mutationFn: ({ itemId, input }: { itemId: string; input: GroceryInput }) => updateGrocery(itemId, input), onSuccess: async () => { await refreshGroceries(); resetForm(); } });
  const purchaseMutation = useMutation({ mutationFn: ({ itemId, purchased }: { itemId: string; purchased: boolean }) => setGroceryPurchased(itemId, purchased), onSuccess: refreshGroceries });
  const deleteMutation = useMutation({ mutationFn: deleteGrocery, onSuccess: async () => { await refreshGroceries(); setPendingDeleteId(null); } });
  const error = groceriesQuery.error ?? createMutation.error ?? updateMutation.error ?? purchaseMutation.error ?? deleteMutation.error;
  const errorMessage = messageFor(error, 'HomeOps could not update the grocery list. Please try again.');
  const openItems = groceriesQuery.data?.filter((item) => !item.purchased) ?? [];
  const purchasedItems = groceriesQuery.data?.filter((item) => item.purchased) ?? [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  function resetForm() {
    setEditingItem(null);
    setForm(emptyGroceryForm);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.name.trim()) return;
    const quantity = form.quantity.trim() ? Number(form.quantity) : null;
    if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0)) return;
    const input: GroceryInput = { name: form.name.trim(), quantity, unit: form.unit.trim() || null };
    if (editingItem) updateMutation.mutate({ itemId: editingItem.grocery_item_id, input });
    else createMutation.mutate(input);
  }

  function beginEdit(item: GroceryItem) {
    setEditingItem(item);
    setForm({ name: item.name, quantity: item.quantity === null ? '' : String(item.quantity), unit: item.unit ?? '' });
  }

  return <Card className="p-5 sm:p-6"><SectionHeading title="Grocery list" detail={`${openItems.length} items to buy${purchasedItems.length ? ` · ${purchasedItems.length} purchased` : ''}`} action={<Badge tone="planned">Shared list</Badge>} />{errorMessage && <p role="alert" className="mt-5 rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">{errorMessage}</p>}{canManageGroceries ? <form className="mt-5 grid gap-3 md:grid-cols-[1fr_120px_140px_auto]" onSubmit={submit}><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="task-input" placeholder="Add grocery item" /><input min="0" step="any" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} className="task-input" placeholder="Quantity" /><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} className="task-input" placeholder="Unit" /><div className="flex gap-2"><Button type="submit" disabled={isSaving}>{isSaving && <LoaderCircle className="animate-spin" size={16} />}{editingItem ? 'Save' : 'Add item'}</Button>{editingItem && <Button tone="neutral" onClick={resetForm}>Cancel</Button>}</div></form> : <p className="mt-5 rounded-xl bg-[#ECEAE4] px-4 py-3 text-sm muted">Guest accounts can view this list but cannot change it.</p>}{groceriesQuery.isLoading ? <Loading label="Loading grocery list" /> : groceriesQuery.data?.length ? <div className="mt-6 space-y-3">{openItems.map((item) => <GroceryRow key={item.grocery_item_id} item={item} canManage={canManageGroceries} pendingDelete={pendingDeleteId === item.grocery_item_id} isPending={purchaseMutation.isPending || deleteMutation.isPending} onToggle={() => purchaseMutation.mutate({ itemId: item.grocery_item_id, purchased: true })} onEdit={() => beginEdit(item)} onRequestDelete={() => setPendingDeleteId(item.grocery_item_id)} onCancelDelete={() => setPendingDeleteId(null)} onConfirmDelete={() => deleteMutation.mutate(item.grocery_item_id)} />)}{purchasedItems.length > 0 && <><p className="pt-3 text-xs font-bold uppercase tracking-[0.14em] muted">Purchased</p>{purchasedItems.map((item) => <GroceryRow key={item.grocery_item_id} item={item} canManage={canManageGroceries} pendingDelete={pendingDeleteId === item.grocery_item_id} isPending={purchaseMutation.isPending || deleteMutation.isPending} onToggle={() => purchaseMutation.mutate({ itemId: item.grocery_item_id, purchased: false })} onEdit={() => beginEdit(item)} onRequestDelete={() => setPendingDeleteId(item.grocery_item_id)} onCancelDelete={() => setPendingDeleteId(null)} onConfirmDelete={() => deleteMutation.mutate(item.grocery_item_id)} />)}</>}</div> : <Empty title="Your grocery list is clear" detail="Add items as soon as you notice they are needed." />}</Card>;
}

function GroceryRow({ item, canManage, pendingDelete, isPending, onToggle, onEdit, onRequestDelete, onCancelDelete, onConfirmDelete }: { item: GroceryItem; canManage: boolean; pendingDelete: boolean; isPending: boolean; onToggle: () => void; onEdit: () => void; onRequestDelete: () => void; onCancelDelete: () => void; onConfirmDelete: () => void }) {
  return <article className="rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center gap-3"><button type="button" aria-label={`${item.purchased ? 'Mark unpurchased' : 'Mark purchased'} ${item.name}`} onClick={onToggle} disabled={!canManage || isPending} className={`grid size-6 shrink-0 place-items-center rounded-full border transition ${item.purchased ? 'border-[#5E9278] bg-[#5E9278] text-white' : 'border-[#B9B9B2] text-transparent hover:border-[#5E9278] hover:text-[#5E9278]'}`}><Check size={14} /></button><div className="min-w-0 flex-1"><p className={`text-sm font-semibold ${item.purchased ? 'text-[#676B68] line-through' : 'text-[var(--ink)]'}`}>{item.name}</p><p className="mt-1 text-xs muted">{formatQuantity(item.quantity, item.unit)}</p></div>{canManage && !pendingDelete && <div className="flex gap-2"><Button tone="neutral" aria-label={`Edit ${item.name}`} onClick={onEdit}><Pencil size={16} /></Button><Button tone="neutral" aria-label={`Remove ${item.name}`} onClick={onRequestDelete}><Trash2 size={16} /></Button></div>}</div>{canManage && pendingDelete && <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-[var(--line)] pt-4"><p className="mr-auto text-sm muted">Remove {item.name} from the list?</p><Button tone="neutral" onClick={onCancelDelete} disabled={isPending}>Cancel</Button><Button tone="danger" onClick={onConfirmDelete} disabled={isPending}>Remove</Button></div>}</article>;
}

function Loading({ label }: { label: string }) {
  return <div className="flex min-h-28 items-center justify-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={18} />{label}</div>;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="mt-6 rounded-2xl bg-[#ECEAE4] p-5 text-sm leading-6 muted"><p className="font-semibold text-[var(--ink)]">{title}</p><p className="mt-1">{detail}</p></div>;
}

function messageFor(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : error ? fallback : null;
}

function formatQuantity(quantity: number | null, unit: string | null) {
  if (quantity === null) return unit ?? 'No quantity set';
  return `${quantity}${unit ? ` ${unit}` : ''}`;
}
