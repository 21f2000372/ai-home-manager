import React, { useState, useRef } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { 
  ShoppingBag, 
  AlertTriangle, 
  Check, 
  Sparkles, 
  ShieldCheck,
  Plus,
  Receipt,
  UploadCloud,
  FileText,
  CheckCircle2
} from 'lucide-react';

export const PantryView = () => {
  const { state, isPlanApplied, setActiveTab, addInventoryItem, addBulkInventoryItems } = useHousehold();
  const [filterCategory, setFilterCategory] = useState('all');

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [activeModalTab, setActiveModalTab] = useState('manual'); // 'manual' | 'receipt'

  // Manual Form State
  const [itemName, setItemName] = useState('');
  const [itemQuantity, setItemQuantity] = useState('1');
  const [itemUnit, setItemUnit] = useState('kg');
  const [itemCategory, setItemCategory] = useState('Produce');
  const [itemThreshold, setItemThreshold] = useState('1');
  const [itemDietaryNote, setItemDietaryNote] = useState('');

  // Receipt Scan Simulation State
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [selectedReceiptBatch, setSelectedReceiptBatch] = useState(null);
  const [isScanningReceipt, setIsScanningReceipt] = useState(false);

  const handleFileUpload = (file) => {
    if (!file) return;
    setUploadedFileName(file.name);
    setIsScanningReceipt(true);
    setSelectedReceiptBatch(null);

    setTimeout(() => {
      setSelectedReceiptBatch({
        id: `upload-${Date.now()}`,
        name: `Scanned Receipt (${file.name})`,
        store: file.name.toUpperCase().replace(/\.[^/.]+$/, "") + " Store",
        date: 'Today',
        items: [
          { name: 'Basmati Rice (Organic)', quantity: '5 kg', category: 'Grains', dietaryNote: 'Low Glycemic Index' },
          { name: 'Pure Cow Milk (A2)', quantity: '2 L', category: 'Dairy', dietaryNote: 'Fresh daily stock' },
          { name: 'Cold-Pressed Sunflower Oil', quantity: '1 L', category: 'Grains', dietaryNote: 'Heart healthy' },
          { name: 'Low-Sodium Rock Salt', quantity: '1 unit', category: 'Spices', dietaryNote: 'Dad compliant low-sodium' }
        ]
      });
      setIsScanningReceipt(false);
    }, 600);
  };

  const RECEIPT_BATCHES = [
    {
      id: 'batch-nature',
      name: "Nature's Basket Organic Basket (4 items)",
      store: "Nature's Basket Supermarket",
      date: 'Today',
      items: [
        { name: 'Basmati Rice (Aged)', quantity: '5 kg', category: 'Grains', dietaryNote: 'Low Glycemic Index' },
        { name: 'Cold Pressed Mustard Oil', quantity: '2 L', category: 'Grains', dietaryNote: 'Pure Cold-Pressed' },
        { name: 'Himalayan Pink Salt', quantity: '1 unit', category: 'Spices', dietaryNote: 'Dad compliant low-sodium alternative' },
        { name: 'Green Moong Dal', quantity: '2 kg', category: 'Grains', dietaryNote: 'High protein' }
      ]
    },
    {
      id: 'batch-daily',
      name: "Country Delight Fresh Dairy & Breakfast (3 items)",
      store: 'Country Delight Morning Delivery',
      date: 'Today',
      items: [
        { name: 'Farm Cow Milk (Whole)', quantity: '2 L', category: 'Dairy', dietaryNote: 'Fresh daily stock' },
        { name: 'Low-Fat Greek Curd', quantity: '1 kg', category: 'Dairy', dietaryNote: 'Low sodium probiotic' },
        { name: 'Organic Cage-Free Eggs', quantity: '12 pcs', category: 'Hospitality', dietaryNote: 'Farm fresh' }
      ]
    }
  ];

  const handleManualAddItem = (e) => {
    e.preventDefault();
    if (!itemName.trim()) return;
    addInventoryItem({
      name: itemName.trim(),
      quantity: `${itemQuantity} ${itemUnit}`,
      category: itemCategory,
      threshold: itemThreshold,
      dietaryNote: itemDietaryNote.trim() || 'Household staple',
    });
    setItemName('');
    setItemQuantity('1');
    setItemDietaryNote('');
    setIsAddModalOpen(false);
  };

  const handleSelectReceiptBatch = (batch) => {
    setIsScanningReceipt(true);
    setSelectedReceiptBatch(null);
    setTimeout(() => {
      setSelectedReceiptBatch(batch);
      setIsScanningReceipt(false);
    }, 400);
  };

  const handleIngestReceiptBatch = () => {
    if (!selectedReceiptBatch) return;
    addBulkInventoryItems(selectedReceiptBatch.items);
    setSelectedReceiptBatch(null);
    setIsAddModalOpen(false);
  };

  const categories = ['all', 'Produce', 'Dairy', 'Grains', 'Spices', 'Hospitality', 'Health'];

  const filteredItems = state.inventory.filter((item) => {
    if (filterCategory === 'all') return true;
    return item.category.toLowerCase() === filterCategory.toLowerCase();
  });

  const lowStockCount = state.inventory.filter(i => i.status === 'low' || i.status === 'out_of_stock').length;

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Pantry & Groceries
            </h2>
            {lowStockCount > 0 && (
              <Badge variant="warning" size="xs">{lowStockCount} Need Restocking</Badge>
            )}
          </div>
          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
            Household staples and planned replenishment scaled for family and guests.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setActiveModalTab('receipt');
              setIsAddModalOpen(true);
            }}
            icon={Receipt}
          >
            Scan Receipt
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setActiveModalTab('manual');
              setIsAddModalOpen(true);
            }}
            icon={Plus}
          >
            Add Item
          </Button>
        </div>
      </div>

      {/* Dietary Guard Banner */}
      <Card className="p-4 bg-[#5E9278]/10 border-[#5E9278]/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-[#5E9278] dark:text-[#9BCDB4] shrink-0 mt-0.5" />
          <div>
            <span className="text-xs font-bold text-[#171918] dark:text-[#EFF1EC]">
              Active Dietary Directive: Dad (Strict Low-Salt)
            </span>
            <p className="text-xs text-[#676B68] dark:text-[#969D96] mt-0.5 leading-relaxed">
              Dr. Verma clinical directive (&lt;1,500mg daily) is automatically enforced. High-sodium items are filtered out and low-sodium substitutes are prioritized.
            </p>
          </div>
        </div>
      </Card>

      {/* Category Filter */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none text-xs">
        <span className="text-[#676B68] dark:text-[#969D96] font-medium shrink-0 mr-1 text-[11px]">
          Filter:
        </span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            className={`min-h-[34px] px-3 py-1 rounded-xl capitalize shrink-0 transition-colors text-xs active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] ${
              filterCategory === cat
                ? 'bg-[#5E9278] text-white font-semibold shadow-xs'
                : 'bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC]'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Inventory Grid - Reduced Card Height */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 sm:gap-3">
        {filteredItems.map((item) => {
          const isLow = item.status === 'low';
          const isOut = item.status === 'out_of_stock';
          const isRestocking = item.status === 'restocking' || item.status === 'refill_scheduled';

          return (
            <Card
              key={item.id}
              className={`p-3 flex flex-col justify-between space-y-2 transition-all ${
                isOut
                  ? 'border-[#B96359]/50 bg-[#B96359]/5'
                  : isLow
                  ? 'border-[#D19A4C]/50 bg-[#D19A4C]/5'
                  : isRestocking
                  ? 'border-[#5E9278]/40 bg-[#5E9278]/5'
                  : ''
              }`}
            >
              {/* Top Row: Name + Quantity + Status */}
              <div className="flex items-start justify-between gap-2 min-w-0">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs sm:text-sm font-semibold text-[#171918] dark:text-[#EFF1EC] truncate">
                      {item.name}
                    </span>
                    <span className="text-xs font-bold text-[#5E9278] dark:text-[#9BCDB4] shrink-0 font-mono">
                      • {item.quantity}
                    </span>
                  </div>
                </div>

                <Badge
                  variant={isOut ? 'critical' : isLow ? 'warning' : isRestocking ? 'primary' : 'neutral'}
                  size="xs"
                >
                  {isRestocking ? 'Restock Scheduled' : item.status.replace('_', ' ')}
                </Badge>
              </div>

              {/* Bottom Row: Category + Context Note */}
              <div className="flex items-center justify-between text-[11px] text-[#676B68] dark:text-[#969D96] pt-1.5 border-t border-[#D9D8D2]/40 dark:border-[#2D322E]/40 gap-2">
                <span className="text-[10px] uppercase font-mono tracking-wider text-[#676B68] dark:text-[#969D96] shrink-0">
                  {item.category}
                </span>
                <span className="truncate text-right max-w-[180px] sm:max-w-none">
                  {item.notes || item.dietaryNote}
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Add Item / Scan Receipt Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false);
          setSelectedReceiptBatch(null);
        }}
        title="Stock Household Pantry"
        subtitle="Manual inventory entry or Document Agent grocery receipt extraction"
      >
        <div className="space-y-4 text-xs">
          {/* Mode Switcher Tabs */}
          <div className="flex rounded-xl bg-black/5 dark:bg-white/5 p-1 gap-1">
            <button
              type="button"
              onClick={() => setActiveModalTab('manual')}
              className={`flex-1 py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all text-xs active:scale-[0.98] ${
                activeModalTab === 'manual'
                  ? 'bg-white dark:bg-[#1E231F] text-[#171918] dark:text-[#EFF1EC] shadow-xs font-semibold'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918]'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-[#5E9278]" />
              <span>Manual Entry Form</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveModalTab('receipt')}
              className={`flex-1 py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all text-xs active:scale-[0.98] ${
                activeModalTab === 'receipt'
                  ? 'bg-white dark:bg-[#1E231F] text-[#171918] dark:text-[#EFF1EC] shadow-xs font-semibold'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918]'
              }`}
            >
              <Receipt className="w-3.5 h-3.5 text-[#5E9278]" />
              <span>Scan Grocery Receipt</span>
            </button>
          </div>

          {/* TAB 1: Manual Form Entry */}
          {activeModalTab === 'manual' && (
            <form onSubmit={handleManualAddItem} className="space-y-3.5 animate-fade-in">
              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Item Name *
                </label>
                <Input
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="e.g. Toor Dal, Olive Oil, Brown Eggs..."
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Quantity *
                  </label>
                  <Input
                    type="number"
                    value={itemQuantity}
                    onChange={(e) => setItemQuantity(e.target.value)}
                    placeholder="e.g. 2"
                    min="1"
                    required
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Unit
                  </label>
                  <select
                    value={itemUnit}
                    onChange={(e) => setItemUnit(e.target.value)}
                    className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
                  >
                    <option value="kg">kg (Kilograms)</option>
                    <option value="g">g (Grams)</option>
                    <option value="L">L (Litres)</option>
                    <option value="ml">ml (Millilitres)</option>
                    <option value="packs">packs</option>
                    <option value="boxes">boxes</option>
                    <option value="bottles">bottles</option>
                    <option value="pcs">pcs / units</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Category
                  </label>
                  <select
                    value={itemCategory}
                    onChange={(e) => setItemCategory(e.target.value)}
                    className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
                  >
                    <option value="Produce">Produce & Greens</option>
                    <option value="Dairy">Dairy & Eggs</option>
                    <option value="Grains">Grains & Pulses</option>
                    <option value="Spices">Spices & Condiments</option>
                    <option value="Hospitality">Hospitality & Snacks</option>
                    <option value="Health">Health & Dietary</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Low Stock Threshold
                  </label>
                  <Input
                    type="number"
                    value={itemThreshold}
                    onChange={(e) => setItemThreshold(e.target.value)}
                    placeholder="1"
                    min="1"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Dietary / Health Note
                </label>
                <Input
                  value={itemDietaryNote}
                  onChange={(e) => setItemDietaryNote(e.target.value)}
                  placeholder="e.g. Low-sodium compliant, Diabetic friendly, Organic..."
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsAddModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                >
                  Add to Pantry
                </Button>
              </div>
            </form>
          )}

          {/* TAB 2: Scan Grocery Receipt (Document Agent OCR) */}
          {activeModalTab === 'receipt' && (
            <div className="space-y-3.5 animate-fade-in">
              {/* Functional Dropzone */}
              <div 
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
                }}
                className={`p-4 border-2 border-dashed rounded-xl text-center cursor-pointer transition-all space-y-2 select-none ${
                  isDragging 
                    ? 'border-[#5E9278] bg-[#5E9278]/10' 
                    : 'border-[#D9D8D2] dark:border-[#2D322E] bg-black/[0.01] dark:bg-white/[0.01] hover:border-[#5E9278]/70 hover:bg-[#5E9278]/5'
                }`}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                  }} 
                  accept="image/*,.pdf,.jpg,.jpeg,.png" 
                  className="hidden" 
                />
                <div className="w-10 h-10 rounded-full bg-[#5E9278]/10 text-[#5E9278] flex items-center justify-center mx-auto">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-semibold text-xs text-[#171918] dark:text-[#EFF1EC]">
                    {uploadedFileName ? `Selected: ${uploadedFileName}` : "Click to browse or drop supermarket receipt"}
                  </p>
                  <p className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-0.5">
                    Document Agent OCR automatically parses line items, counts, and dietary compliance
                  </p>
                </div>
                <div className="pt-1">
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium bg-[#5E9278]/15 text-[#3d6551] dark:text-[#9BCDB4] hover:bg-[#5E9278]/25 transition-colors">
                    <Receipt className="w-3.5 h-3.5" />
                    Browse Files
                  </span>
                </div>
              </div>

              {/* Sample Batch Receipts */}
              <div>
                <span className="text-[11px] font-bold text-[#676B68] dark:text-[#969D96] uppercase tracking-wider block mb-1.5">
                  Select sample supermarket receipt to ingest:
                </span>
                <div className="grid grid-cols-1 gap-2">
                  {RECEIPT_BATCHES.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => handleSelectReceiptBatch(b)}
                      className={`p-2.5 rounded-xl border text-left transition-all flex items-center justify-between gap-2 ${
                        selectedReceiptBatch?.id === b.id
                          ? 'border-[#5E9278] bg-[#5E9278]/10 text-[#171918] dark:text-[#EFF1EC]'
                          : 'border-[#D9D8D2] dark:border-[#2D322E] bg-black/[0.02] dark:bg-white/[0.02] hover:border-[#5E9278]/50 text-[#171918] dark:text-[#EFF1EC]'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-xs truncate">{b.name}</div>
                        <div className="text-[11px] text-[#676B68] dark:text-[#969D96]">
                          {b.store} • {b.items.length} items parsed
                        </div>
                      </div>
                      <Badge variant="primary" size="xs">
                        {b.items.length} Items
                      </Badge>
                    </button>
                  ))}
                </div>
              </div>

              {/* Scanning Indicator */}
              {isScanningReceipt && (
                <div className="p-3 rounded-xl bg-[#5E9278]/10 border border-[#5E9278]/30 flex items-center gap-2 text-xs text-[#2F5542] dark:text-[#9BCDB4] animate-pulse">
                  <Sparkles className="w-4 h-4 text-[#5E9278]" />
                  <span>Document Agent parsing item names, weights, and dietary compliance...</span>
                </div>
              )}

              {/* Parsed Items Preview */}
              {selectedReceiptBatch && !isScanningReceipt && (
                <div className="p-3.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.03] border border-[#5E9278]/40 space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between border-b border-[#D9D8D2]/60 dark:border-[#2D322E]/60 pb-2">
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-[#5E9278]" />
                      <span className="font-bold text-xs text-[#171918] dark:text-[#EFF1EC]">
                        {selectedReceiptBatch.items.length} Line Items Extracted
                      </span>
                    </div>
                    <Badge variant="primary" size="xs">{selectedReceiptBatch.store.split(' ')[0]}</Badge>
                  </div>

                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {selectedReceiptBatch.items.map((it, idx) => (
                      <div key={idx} className="p-2 rounded-lg bg-black/5 dark:bg-white/5 flex items-center justify-between text-xs">
                        <div>
                          <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{it.name}</span>
                          <span className="text-[10px] text-[#676B68] dark:text-[#969D96] block">{it.dietaryNote}</span>
                        </div>
                        <span className="font-mono font-bold text-[#5E9278] dark:text-[#9BCDB4] shrink-0">
                          {it.quantity}
                        </span>
                      </div>
                    ))}
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full mt-2"
                    onClick={handleIngestReceiptBatch}
                  >
                    Stock All {selectedReceiptBatch.items.length} Items into Pantry
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
