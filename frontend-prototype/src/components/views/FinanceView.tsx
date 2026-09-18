import React, { useState, useRef } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { 
  Wallet, 
  Lock, 
  ArrowRight, 
  ShieldCheck, 
  Sparkles, 
  TrendingDown, 
  Plus, 
  Receipt, 
  PieChart, 
  Calendar, 
  CheckCircle2,
  UploadCloud,
  FileText
} from 'lucide-react';

export const FinanceView = () => {
  const { state, activeUser, switchUser, isPlanApplied, addExpense } = useHousehold();
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [activeModalTab, setActiveModalTab] = useState('ocr'); // 'ocr' | 'manual'
  
  // Manual Form State
  const [txTitle, setTxTitle] = useState('');
  const [txAmount, setTxAmount] = useState('');
  const [txCategory, setTxCategory] = useState('Groceries');
  const [txMerchant, setTxMerchant] = useState('');
  const [txDate, setTxDate] = useState('Today');
  const [txNotes, setTxNotes] = useState('');

  // OCR Upload / Simulation State
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [isParsingReceipt, setIsParsingReceipt] = useState(false);

  const handleFileUpload = (file) => {
    if (!file) return;
    setUploadedFileName(file.name);
    setIsParsingReceipt(true);
    setSelectedReceipt(null);

    setTimeout(() => {
      const lower = file.name.toLowerCase();
      const isMed = lower.includes('rx') || lower.includes('med') || lower.includes('clinic') || lower.includes('apollo') || lower.includes('health');
      const isUC = lower.includes('ac') || lower.includes('urban') || lower.includes('service') || lower.includes('repair') || lower.includes('daikin');
      
      if (isMed) {
        setSelectedReceipt({
          id: `upload-${Date.now()}`,
          title: `Prescription Receipt (${file.name})`,
          merchant: 'Apollo Pharmacy & Diagnostics',
          amount: 880,
          category: 'Pharmacy',
          date: 'Today',
          items: ['Metformin 500mg (₹320)', 'Telmisartan 40mg (₹410)', 'Digital Thermometer (₹150)'],
          sourceDoc: file.name.toUpperCase(),
          envelopeMatch: 'Healthcare & Pharmacy'
        });
      } else if (isUC) {
        setSelectedReceipt({
          id: `upload-${Date.now()}`,
          title: `Service Invoice (${file.name})`,
          merchant: 'Urban Company Maintenance',
          amount: 550,
          category: 'Utilities',
          date: 'Today',
          items: ['AC Deep Clean & Filter Disinfection (₹550)'],
          sourceDoc: file.name.toUpperCase(),
          envelopeMatch: 'Household Utilities'
        });
      } else {
        setSelectedReceipt({
          id: `upload-${Date.now()}`,
          title: `Grocery Receipt (${file.name})`,
          merchant: 'Reliance Fresh Supermarket',
          amount: 1420,
          category: 'Groceries',
          date: 'Today',
          items: ['Basmati Rice 5kg (₹480)', 'Amul Taaza Milk 2L (₹140)', 'Cold Pressed Oil 1L (₹280)', 'Organic Vegetables (₹520)'],
          sourceDoc: file.name.toUpperCase(),
          envelopeMatch: 'Groceries & Provisions'
        });
      }
      setIsParsingReceipt(false);
    }, 600);
  };

  const RECEIPT_SAMPLES = [
    {
      id: 'rcpt-1',
      title: 'Reliance Fresh Supermarket Receipt',
      merchant: 'Reliance Fresh',
      amount: 1420,
      category: 'Groceries',
      date: 'Today',
      items: ['Basmati Rice 5kg (₹480)', 'Amul Taaza Milk 2L (₹140)', 'Cold Pressed Oil 1L (₹280)', 'Organic Vegetables (₹520)'],
      sourceDoc: 'RECEIPT_REL_2819.PDF',
      envelopeMatch: 'Groceries & Provisions'
    },
    {
      id: 'rcpt-2',
      title: 'Apollo Pharmacy Clinical Bill',
      merchant: 'Apollo Pharmacy',
      amount: 880,
      category: 'Pharmacy',
      date: 'Today',
      items: ['Metformin 500mg (₹320)', 'Telmisartan 40mg (₹410)', 'Digital Thermometer (₹150)'],
      sourceDoc: 'RX_APOLLO_7721.JPG',
      envelopeMatch: 'Healthcare & Pharmacy'
    },
    {
      id: 'rcpt-3',
      title: 'Urban Company Service Invoice',
      merchant: 'Urban Company',
      amount: 550,
      category: 'Utilities',
      date: 'Yesterday',
      items: ['AC Deep Clean & Filter Disinfection (₹550)'],
      sourceDoc: 'UC_INV_90812.PDF',
      envelopeMatch: 'Household Utilities'
    }
  ];

  const isRestricted = !activeUser.permissions.canViewFinances;

  if (isRestricted) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center animate-fade-in space-y-4">
        <Card className="p-8 border-[#B96359]/40 space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-[#B96359]/15 text-[#B96359] flex items-center justify-center mx-auto">
            <Lock className="w-6 h-6" />
          </div>

          <div>
            <Badge variant="critical" size="sm" className="mb-2">Privacy Restricted</Badge>
            <h3 className="text-base sm:text-lg font-bold text-[#171918] dark:text-[#EFF1EC]">
              Financial Information Hidden
            </h3>
            <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96] mt-1.5 leading-relaxed max-w-sm mx-auto">
              You are logged in as <strong>{activeUser.name}</strong> ({activeUser.role}). Line-item budgets, account balances, and receipts are restricted to Parent Administrator accounts.
            </p>
          </div>

          <div className="pt-2">
            <Button
              variant="primary"
              size="md"
              onClick={() => switchUser('rajesh')}
            >
              Switch to Parent Profile (Rajesh)
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const finance = state.finance;
  const weeklyBudget = finance.weeklyBudget || 5000;
  const plannedExpenses = finance.plannedExpenses || 0;
  const estimatedRemaining = finance.estimatedRemaining || 5000;

  const plannedPercent = Math.min(100, Math.round((plannedExpenses / weeklyBudget) * 100));
  const remainingPercent = 100 - plannedPercent;

  const handleManualAddTransaction = (e) => {
    e.preventDefault();
    if (!txTitle.trim() || !txAmount) return;
    addExpense({
      title: txTitle.trim(),
      amount: parseFloat(txAmount),
      category: txCategory,
      merchant: txMerchant.trim() || undefined,
      date: txDate.trim() || 'Today',
      notes: txNotes.trim() || undefined,
      paidBy: activeUser.name.split(' ')[0],
    });
    setTxTitle('');
    setTxAmount('');
    setTxMerchant('');
    setTxNotes('');
    setIsLogModalOpen(false);
  };

  const handleSelectSampleReceipt = (rcpt) => {
    setIsParsingReceipt(true);
    setSelectedReceipt(null);
    setTimeout(() => {
      setSelectedReceipt(rcpt);
      setIsParsingReceipt(false);
    }, 450);
  };

  const handleConfirmReceiptIngestion = () => {
    if (!selectedReceipt) return;
    addExpense({
      title: selectedReceipt.title,
      amount: selectedReceipt.amount,
      category: selectedReceipt.category,
      merchant: selectedReceipt.merchant,
      date: selectedReceipt.date,
      notes: `Ingested via Document Agent OCR (${selectedReceipt.sourceDoc}) • ${selectedReceipt.items.join(', ')}`,
      paidBy: activeUser.name.split(' ')[0],
    });
    setSelectedReceipt(null);
    setIsLogModalOpen(false);
  };

  const allTransactions = finance.recentTransactions || [];

  const ENVELOPES = [
    { name: 'Groceries & Provisions', cap: 2000, allocated: isPlanApplied ? 1700 : 450, color: '#5E9278' },
    { name: 'Healthcare & Pharmacy', cap: 1000, allocated: isPlanApplied ? 900 : 0, color: '#6E96AD' },
    { name: 'Household Utilities', cap: 1200, allocated: 600, color: '#D19A4C' },
    { name: 'Emergency Contingency', cap: 800, allocated: isPlanApplied ? 0 : 0, color: '#9BCDB4' },
  ];

  return (
    <div className="space-y-5 max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Household Budget & Envelope Progress
            </h2>
            <Badge variant="primary" size="xs">Weekly ₹5,000 Cycle</Badge>
          </div>
          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
            Balanced multi-domain allocation across groceries, elder care, and maintenance.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsLogModalOpen(true)}
            icon={Plus}
          >
            Log Outlay
          </Button>
        </div>
      </div>

      {/* Cycle & Privacy Status Strip */}
      <div className="p-3 rounded-xl bg-black/[0.03] dark:bg-white/[0.03] border border-[#D9D8D2] dark:border-[#2D322E] flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2 text-[#676B68] dark:text-[#969D96]">
          <Calendar className="w-3.5 h-3.5 text-[#5E9278]" />
          <span>Weekly Cycle: <strong>Day 4 of 7 (Thursday)</strong> • Resets Monday 00:00</span>
        </div>
        <div className="flex items-center gap-2 text-[#676B68] dark:text-[#969D96]">
          <ShieldCheck className="w-3.5 h-3.5 text-[#5E9278]" />
          <span>Parent Clearances: <strong>Rajesh & Priya</strong></span>
        </div>
      </div>

      {/* Primary Financial Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <Card className="p-4 sm:p-5">
          <span className="text-xs text-[#676B68] dark:text-[#969D96] font-medium block mb-1">
            Weekly Budget Cap
          </span>
          <div className="text-2xl font-bold text-[#171918] dark:text-[#EFF1EC]">
            ₹{weeklyBudget.toLocaleString()}
          </div>
          <span className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-1 block">
            Reset every Monday
          </span>
        </Card>

        <Card className="p-4 sm:p-5">
          <span className="text-xs text-[#676B68] dark:text-[#969D96] font-medium block mb-1">
            Planned Commitments
          </span>
          <div className="text-2xl font-bold text-[#D19A4C]">
            ₹{plannedExpenses.toLocaleString()}
          </div>
          <span className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-1 block truncate">
            {isPlanApplied ? "Groceries (₹1,700) + Rx (₹900)" : "No planned outlays yet"}
          </span>
        </Card>

        <Card className="p-4 sm:p-5 border-[#5E9278]/40 bg-[#5E9278]/5">
          <span className="text-xs text-[#5E9278] dark:text-[#9BCDB4] font-medium block mb-1">
            Uncommitted Reserve Buffer
          </span>
          <div className="text-2xl font-bold text-[#5E9278] dark:text-[#9BCDB4]">
            ₹{estimatedRemaining.toLocaleString()}
          </div>
          <span className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-1 block">
            Safe buffer for contingencies
          </span>
        </Card>
      </div>

      {/* Multi-Segment Allocation Bar */}
      <Card className="p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">
            Weekly Allocation Envelope Progress
          </span>
          <span className="text-[#676B68] dark:text-[#969D96]">
            {plannedPercent}% Committed • {remainingPercent}% Available
          </span>
        </div>

        {/* The Progress Bar */}
        <div className="w-full h-3 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden flex">
          <div 
            style={{ width: `${plannedPercent}%` }} 
            className="h-full bg-[#D19A4C] transition-all duration-300"
            title={`Planned: ₹${plannedExpenses}`}
          />
          <div 
            style={{ width: `${remainingPercent}%` }} 
            className="h-full bg-[#5E9278] transition-all duration-300"
            title={`Available: ₹${estimatedRemaining}`}
          />
        </div>

        <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#676B68] dark:text-[#969D96] pt-0.5">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#D19A4C]" />
            <span>Planned Outlays: <strong>₹{plannedExpenses.toLocaleString()}</strong></span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#5E9278]" />
            <span>Available Reserve: <strong>₹{estimatedRemaining.toLocaleString()}</strong></span>
          </span>
        </div>
      </Card>

      {/* Category Envelopes Breakdown */}
      <div className="space-y-3">
        <h3 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC]">
          Domain Budget Envelopes
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {ENVELOPES.map((env) => {
            const pct = Math.round((env.allocated / env.cap) * 100);
            return (
              <Card key={env.name} className="p-3.5 space-y-2">
                <div className="flex items-start justify-between gap-1">
                  <span className="text-xs font-semibold text-[#171918] dark:text-[#EFF1EC]">
                    {env.name}
                  </span>
                  <Badge variant={pct > 80 ? 'warning' : 'primary'} size="xs">
                    {pct}%
                  </Badge>
                </div>

                <div className="text-base font-bold text-[#171918] dark:text-[#EFF1EC]">
                  ₹{env.allocated.toLocaleString()} <span className="text-xs font-normal text-[#676B68] dark:text-[#969D96]">/ ₹{env.cap.toLocaleString()}</span>
                </div>

                <div className="w-full h-1.5 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
                  <div 
                    style={{ width: `${pct}%`, backgroundColor: env.color }}
                    className="h-full rounded-full transition-all"
                  />
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Dual Column: Planned Allocations + Settled Transactions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Planned Breakdown */}
        <div className="space-y-3">
          <h3 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC]">
            Active Coordinated Outlays
          </h3>

          <div className="space-y-2.5">
            {finance.breakdown.map((item) => (
              <Card key={item.id} className="p-3.5 space-y-1.5">
                <div className="flex items-center justify-between text-xs sm:text-sm">
                  <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{item.item}</span>
                  <span className="font-bold text-[#D19A4C]">₹{item.amount?.toLocaleString()}</span>
                </div>
                {item.agentReasoning && (
                  <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-snug">
                    {item.agentReasoning}
                  </p>
                )}
              </Card>
            ))}
          </div>
        </div>

        {/* Recent Settled Transactions */}
        <div className="space-y-3">
          <h3 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC]">
            Settled Transactions
          </h3>

          <div className="space-y-2.5">
            {allTransactions.map((tx) => (
              <Card key={tx.id} className="p-3.5 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{tx.title}</div>
                  <div className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-0.5">
                    Paid by {tx.paidBy} • {tx.date}
                  </div>
                </div>
                <span className="font-semibold text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC]">
                  ₹{tx.amount?.toLocaleString()}
                </span>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* Dual-Mode Log Outlay Modal */}
      <Modal
        isOpen={isLogModalOpen}
        onClose={() => {
          setIsLogModalOpen(false);
          setSelectedReceipt(null);
        }}
        title="Log Household Outlay"
        subtitle="Document Agent receipt extraction or manual ledger entry"
      >
        <div className="space-y-4 text-xs">
          {/* Mode Switcher Tabs */}
          <div className="flex rounded-xl bg-black/5 dark:bg-white/5 p-1 gap-1">
            <button
              type="button"
              onClick={() => setActiveModalTab('ocr')}
              className={`flex-1 py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all text-xs active:scale-[0.98] ${
                activeModalTab === 'ocr'
                  ? 'bg-white dark:bg-[#1E231F] text-[#171918] dark:text-[#EFF1EC] shadow-xs font-semibold'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918]'
              }`}
            >
              <UploadCloud className="w-3.5 h-3.5 text-[#5E9278]" />
              <span>Upload Bill / Receipt</span>
            </button>
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
          </div>

          {/* TAB 1: Upload Bill / Receipt (Document Agent OCR) */}
          {activeModalTab === 'ocr' && (
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
                  <Receipt className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-semibold text-xs text-[#171918] dark:text-[#EFF1EC]">
                    {uploadedFileName ? `Selected: ${uploadedFileName}` : "Click to browse or drop bill / receipt photo"}
                  </p>
                  <p className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-0.5">
                    Supports PDF, JPG, PNG • Document Agent OCR parses merchant & totals automatically
                  </p>
                </div>
                <div className="pt-1">
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium bg-[#5E9278]/15 text-[#3d6551] dark:text-[#9BCDB4] hover:bg-[#5E9278]/25 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5" />
                    Browse Files
                  </span>
                </div>
              </div>

              {/* Sample Receipts Selector */}
              <div>
                <span className="text-[11px] font-bold text-[#676B68] dark:text-[#969D96] uppercase tracking-wider block mb-1.5">
                  Or select sample scanned bill to parse:
                </span>
                <div className="grid grid-cols-1 gap-2">
                  {RECEIPT_SAMPLES.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => handleSelectSampleReceipt(s)}
                      className={`p-2.5 rounded-xl border text-left transition-all flex items-center justify-between gap-2 ${
                        selectedReceipt?.id === s.id
                          ? 'border-[#5E9278] bg-[#5E9278]/10 text-[#171918] dark:text-[#EFF1EC]'
                          : 'border-[#D9D8D2] dark:border-[#2D322E] bg-black/[0.02] dark:bg-white/[0.02] hover:border-[#5E9278]/50 text-[#171918] dark:text-[#EFF1EC]'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-xs truncate">{s.title}</div>
                        <div className="text-[11px] text-[#676B68] dark:text-[#969D96]">
                          {s.merchant} • {s.items.length} line items detected
                        </div>
                      </div>
                      <span className="font-bold font-mono text-xs text-[#5E9278] dark:text-[#9BCDB4] shrink-0">
                        ₹{s.amount}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Parsing Indicator */}
              {isParsingReceipt && (
                <div className="p-3 rounded-xl bg-[#5E9278]/10 border border-[#5E9278]/30 flex items-center gap-2 text-xs text-[#2F5542] dark:text-[#9BCDB4] animate-pulse">
                  <Sparkles className="w-4 h-4 text-[#5E9278]" />
                  <span>Document Agent parsing receipt layout, amounts, and tax lines...</span>
                </div>
              )}

              {/* Extracted Receipt Preview */}
              {selectedReceipt && !isParsingReceipt && (
                <div className="p-3.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.03] border border-[#5E9278]/40 space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between border-b border-[#D9D8D2]/60 dark:border-[#2D322E]/60 pb-2">
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-[#5E9278]" />
                      <span className="font-bold text-xs text-[#171918] dark:text-[#EFF1EC]">
                        OCR Extraction Verified
                      </span>
                    </div>
                    <Badge variant="primary" size="xs">{selectedReceipt.envelopeMatch}</Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-[#676B68] dark:text-[#969D96]">Merchant:</span>
                      <div className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{selectedReceipt.merchant}</div>
                    </div>
                    <div>
                      <span className="text-[#676B68] dark:text-[#969D96]">Amount:</span>
                      <div className="font-bold font-mono text-[#171918] dark:text-[#EFF1EC]">₹{selectedReceipt.amount}</div>
                    </div>
                  </div>

                  <div className="text-[11px] pt-1">
                    <span className="text-[#676B68] dark:text-[#969D96] block mb-1">Extracted Line Items:</span>
                    <ul className="list-disc list-inside space-y-0.5 text-[#171918] dark:text-[#EFF1EC]">
                      {selectedReceipt.items.map((it, idx) => (
                        <li key={idx} className="truncate">{it}</li>
                      ))}
                    </ul>
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full mt-2"
                    onClick={handleConfirmReceiptIngestion}
                  >
                    Ingest Outlay to {selectedReceipt.envelopeMatch}
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Manual Form Entry */}
          {activeModalTab === 'manual' && (
            <form onSubmit={handleManualAddTransaction} className="space-y-3.5 animate-fade-in">
              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Expense Description *
                </label>
                <Input
                  value={txTitle}
                  onChange={(e) => setTxTitle(e.target.value)}
                  placeholder="e.g. Milk & curd delivery, Water canister..."
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Amount (₹) *
                  </label>
                  <Input
                    type="number"
                    value={txAmount}
                    onChange={(e) => setTxAmount(e.target.value)}
                    placeholder="e.g. 240"
                    required
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Envelope / Category
                  </label>
                  <select
                    value={txCategory}
                    onChange={(e) => setTxCategory(e.target.value)}
                    className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
                  >
                    <option value="Groceries">Groceries & Provisions</option>
                    <option value="Pharmacy">Healthcare & Pharmacy</option>
                    <option value="Utilities">Household Utilities</option>
                    <option value="Hospitality">Family Hospitality</option>
                    <option value="General">General Contingency</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Merchant / Payee
                  </label>
                  <Input
                    value={txMerchant}
                    onChange={(e) => setTxMerchant(e.target.value)}
                    placeholder="e.g. Local Dairy, Apollo Clinic"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                    Date
                  </label>
                  <Input
                    value={txDate}
                    onChange={(e) => setTxDate(e.target.value)}
                    placeholder="Today"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Notes / Reference
                </label>
                <Input
                  value={txNotes}
                  onChange={(e) => setTxNotes(e.target.value)}
                  placeholder="Optional context or bill invoice number..."
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsLogModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                >
                  Save Outlay
                </Button>
              </div>
            </form>
          )}
        </div>
      </Modal>
    </div>
  );
};
