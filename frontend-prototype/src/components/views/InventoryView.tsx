import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  UtensilsCrossed, 
  AlertTriangle, 
  CheckCircle2, 
  Sparkles, 
  Filter, 
  ShoppingCart,
  ShieldCheck,
  Plus
} from 'lucide-react';

export const InventoryView = () => {
  const { state, isPlanApplied } = useHousehold();
  const [filterCategory, setFilterCategory] = useState('all');

  const categories = ['all', 'Produce', 'Dairy', 'Grains', 'Spices', 'Hospitality', 'Cleaning', 'Health'];

  const filteredItems = state.inventory.filter((item) => {
    if (filterCategory === 'all') return true;
    return item.category.toLowerCase() === filterCategory.toLowerCase();
  });

  const lowStockCount = state.inventory.filter(i => i.status === 'low' || i.status === 'out_of_stock').length;

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-emerald-950 via-slate-900 to-navy-900 border border-emerald-500/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="emerald" size="sm">
                <UtensilsCrossed className="w-3.5 h-3.5" />
                Pantry & Supply Inventory
              </Badge>
              {lowStockCount > 0 && (
                <Badge variant="amber" size="sm">{lowStockCount} Need Restocking</Badge>
              )}
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              Food, Inventory & Dietary Constraints
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              Operations Agent cross-checks current stocks against upcoming guest headcount (+4 relatives) and verified health dietary guidelines.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="p-3 rounded-2xl bg-slate-950/80 border border-slate-800 text-right">
              <span className="text-[10px] text-slate-400 uppercase font-mono block">Estimated Restock</span>
              <span className="text-sm font-bold text-emerald-400">
                {isPlanApplied ? '₹1,700 (Scheduled Thu)' : '₹1,700 (Pending Approval)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Medical & Dietary Restriction Alert */}
      <div className="p-4 rounded-2xl bg-slate-900/90 border border-brand-500/40 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-brand-500/20 text-brand-400 shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-white flex items-center gap-2">
              <span>Cardiology Dietary Directive Active (Rajesh Sharma)</span>
              <Badge variant="brand" size="sm">DOC-MED-01</Badge>
            </div>
            <p className="text-slate-300 mt-0.5 leading-relaxed">
              Verified clinical restriction: <strong>Strict low-sodium / low-salt diet (&lt;1,500mg daily)</strong>. 
              Operations Agent automatically omits high-sodium processed foods and includes rock salt / low-sodium alternatives for all household recipes.
            </p>
          </div>
        </div>
      </div>

      {/* Categories Filter */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <span className="text-slate-500 font-semibold shrink-0">Filter Category:</span>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            className={`px-3 py-1.5 rounded-xl capitalize shrink-0 transition-colors ${
              filterCategory === cat
                ? 'bg-emerald-600 text-white font-semibold shadow-glow-emerald'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Inventory Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredItems.map((item) => {
          const isLow = item.status === 'low';
          const isOut = item.status === 'out_of_stock';
          const isRestocking = item.status === 'restocking' || item.status === 'refill_scheduled';

          return (
            <div
              key={item.id}
              className={`p-4 rounded-2xl border transition-all flex flex-col justify-between ${
                isOut
                  ? 'bg-rose-950/20 border-rose-500/40'
                  : isLow
                  ? 'bg-amber-950/20 border-amber-500/40'
                  : isRestocking
                  ? 'bg-brand-950/20 border-brand-500/40'
                  : 'bg-slate-900/80 border-slate-800'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                    {item.category}
                  </Badge>
                  <Badge
                    variant={
                      isOut
                        ? 'rose'
                        : isLow
                        ? 'amber'
                        : isRestocking
                        ? 'brand'
                        : 'emerald'
                    }
                    size="sm"
                  >
                    {isRestocking ? 'Restock Scheduled' : item.status.replace('_', ' ').toUpperCase()}
                  </Badge>
                </div>

                <h4 className="text-sm font-bold text-white">{item.name}</h4>
                <div className="text-lg font-black text-slate-200 mt-1">
                  {item.quantity}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Min Threshold: <span className="font-mono text-slate-300">{item.minThreshold}</span>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-800/80 text-[11px] text-slate-300">
                <span className="text-emerald-400 font-semibold">AI Context: </span>
                {item.notes || item.dietaryNote}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
