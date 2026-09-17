import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Modal } from '../ui/Modal';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { 
  Sparkles, 
  CheckCircle2, 
  XCircle, 
  ShieldCheck, 
  Wrench, 
  Pill, 
  ShoppingBag, 
  Calendar, 
  RotateCcw,
  UserCheck,
  AlertTriangle
} from 'lucide-react';

export const WeekendPlanModal = ({ isOpen, onClose }) => {
  const { isPlanApplied, applyPlanWithApprovals, resetToBaseline, activeUser } = useHousehold();

  // Individual Approvals State
  const [approveMedicine, setApproveMedicine] = useState(true);
  const [approveAC, setApproveAC] = useState(true);

  const canApprove = activeUser.permissions.canApproveExpenses || activeUser.permissions.canExecuteAgentPlan;

  const totalCost = 1700 + (approveMedicine ? 900 : 0);
  const remainingBudget = 5000 - totalCost;

  const handleExecute = () => {
    applyPlanWithApprovals({ approveMedicine, approveAC });
    onClose();
  };

  const handleReset = () => {
    resetToBaseline();
    setApproveMedicine(true);
    setApproveAC(true);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Multi-Agent Weekend Coordination Plan"
      subtitle="Synthesized from Family Calendar, Clinical Records, Pantry Audits, and Equipment Contracts"
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4 text-xs">
        {/* Coordination Context Strip */}
        <div className="p-3 rounded-xl bg-[#5E9278]/10 border border-[#5E9278]/30 flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-[#5E9278] shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold text-[#171918] dark:text-[#EFF1EC]">
              Cross-Domain Household Synthesis
            </span>
            <p className="text-[#676B68] dark:text-[#969D96] leading-relaxed">
              Mom away on business until Friday evening • 4 relatives visiting Saturday • Dad's low-salt clinical directive active (&lt;1,500mg) • Guest AC requires pre-arrival service.
            </p>
          </div>
        </div>

        {/* Section Title */}
        <div className="flex items-center justify-between pt-1">
          <span className="font-bold uppercase tracking-wider text-[11px] text-[#676B68] dark:text-[#969D96]">
            High-Impact Approvals (Human-in-the-Loop)
          </span>
          <Badge variant={canApprove ? 'primary' : 'critical'} size="xs">
            {canApprove ? 'Parent Clearance Verified' : 'Approval Restricted to Parent'}
          </Badge>
        </div>

        {/* Card 1: Medicine Refill */}
        <Card className={`p-3.5 space-y-2.5 transition-all border ${
          approveMedicine 
            ? 'border-[#5E9278]/50 bg-[#5E9278]/[0.02]' 
            : 'border-[#D9D8D2] dark:border-[#2D322E] opacity-70'
        }`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-[#6E96AD]/15 text-[#6E96AD] flex items-center justify-center shrink-0 mt-0.5">
                <Pill className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC]">
                    Grandma's Monthly Rx Refill (BP & Diabetes)
                  </span>
                  <Badge variant="agent" size="xs">Protected Health Data</Badge>
                </div>
                <p className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-0.5 leading-snug">
                  Verified against Apollo Clinic record DOC-MED-02. 3 days of Metformin & Telmisartan remaining.
                </p>
                <div className="flex items-center gap-3 mt-1.5 text-[11px]">
                  <span className="font-mono font-bold text-[#171918] dark:text-[#EFF1EC]">
                    Outlay: ₹900
                  </span>
                  <span className="text-[#676B68] dark:text-[#969D96]">
                    Delivery: Wednesday 11:30 AM
                  </span>
                  <span className="text-[#676B68] dark:text-[#969D96]">
                    Assigned: Rajesh
                  </span>
                </div>
              </div>
            </div>

            {/* Approve / Reject Controls */}
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setApproveMedicine(true)}
                disabled={!canApprove}
                className={`px-2.5 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1 transition-all ${
                  approveMedicine
                    ? 'bg-[#5E9278] text-white font-semibold shadow-xs'
                    : 'bg-black/5 dark:bg-white/5 text-[#676B68] hover:text-[#171918]'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
              <button
                type="button"
                onClick={() => setApproveMedicine(false)}
                disabled={!canApprove}
                className={`px-2.5 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1 transition-all ${
                  !approveMedicine
                    ? 'bg-[#B96359] text-white font-semibold shadow-xs'
                    : 'bg-black/5 dark:bg-white/5 text-[#676B68] hover:text-[#171918]'
                }`}
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        </Card>

        {/* Card 2: Daikin AC Service */}
        <Card className={`p-3.5 space-y-2.5 transition-all border ${
          approveAC 
            ? 'border-[#5E9278]/50 bg-[#5E9278]/[0.02]' 
            : 'border-[#D9D8D2] dark:border-[#2D322E] opacity-70'
        }`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-[#D19A4C]/15 text-[#D19A4C] flex items-center justify-center shrink-0 mt-0.5">
                <Wrench className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC]">
                    Daikin Authorized AC Service (Guest Bedroom)
                  </span>
                  <Badge variant="primary" size="xs">Complimentary AMC</Badge>
                </div>
                <p className="text-[11px] text-[#676B68] dark:text-[#969D96] mt-0.5 leading-snug">
                  Filter cleaning and coil disinfection before 4 relatives arrive. Technician Ramesh Kumar confirmed.
                </p>
                <div className="flex items-center gap-3 mt-1.5 text-[11px]">
                  <span className="font-mono font-bold text-[#5E9278] dark:text-[#9BCDB4]">
                    Outlay: ₹0 (Under Warranty)
                  </span>
                  <span className="text-[#676B68] dark:text-[#969D96]">
                    Slot: Friday 10:00 AM - 11:00 AM
                  </span>
                  <span className="text-[#676B68] dark:text-[#969D96]">
                    Supervisor: Rajesh
                  </span>
                </div>
              </div>
            </div>

            {/* Approve / Reject Controls */}
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setApproveAC(true)}
                disabled={!canApprove}
                className={`px-2.5 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1 transition-all ${
                  approveAC
                    ? 'bg-[#5E9278] text-white font-semibold shadow-xs'
                    : 'bg-black/5 dark:bg-white/5 text-[#676B68] hover:text-[#171918]'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
              <button
                type="button"
                onClick={() => setApproveAC(false)}
                disabled={!canApprove}
                className={`px-2.5 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1 transition-all ${
                  !approveAC
                    ? 'bg-[#B96359] text-white font-semibold shadow-xs'
                    : 'bg-black/5 dark:bg-white/5 text-[#676B68] hover:text-[#171918]'
                }`}
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        </Card>

        {/* Card 3: Autonomous Pre-Aligned Actions */}
        <div className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-[#D9D8D2] dark:border-[#2D322E] space-y-2">
          <span className="font-bold text-[11px] uppercase tracking-wider text-[#676B68] dark:text-[#969D96] block">
            Pre-Aligned Cross-Domain Actions (Auto-Prepared)
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <div className="p-2 rounded-lg bg-black/5 dark:bg-white/5 flex items-center gap-2">
              <ShoppingBag className="w-3.5 h-3.5 text-[#5E9278] shrink-0" />
              <div>
                <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">Groceries & Low-Salt (₹1,700)</span>
                <span className="text-[10px] text-[#676B68] dark:text-[#969D96] block">Reassigned to Rajesh for Thursday 6:30 PM</span>
              </div>
            </div>

            <div className="p-2 rounded-lg bg-black/5 dark:bg-white/5 flex items-center gap-2">
              <UserCheck className="w-3.5 h-3.5 text-[#5E9278] shrink-0" />
              <div>
                <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">Guest Room Prep (Chore)</span>
                <span className="text-[10px] text-[#676B68] dark:text-[#969D96] block">Assigned to Aarav for Friday 4:30 PM (after school)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Budget Impact Summary Strip */}
        <div className="p-3 rounded-xl bg-black/[0.03] dark:bg-white/[0.03] border border-[#D9D8D2] dark:border-[#2D322E] flex flex-wrap items-center justify-between gap-3 text-xs">
          <div>
            <span className="text-[#676B68] dark:text-[#969D96]">Weekly Budget Cycle:</span>
            <div className="font-bold text-sm text-[#171918] dark:text-[#EFF1EC]">
              ₹5,000 Cap
            </div>
          </div>
          <div>
            <span className="text-[#676B68] dark:text-[#969D96]">Plan Outlay:</span>
            <div className="font-bold text-sm text-[#D19A4C]">
              ₹{totalCost.toLocaleString()}
            </div>
          </div>
          <div>
            <span className="text-[#676B68] dark:text-[#969D96]">Uncommitted Remaining:</span>
            <div className="font-bold text-sm text-[#5E9278] dark:text-[#9BCDB4]">
              ₹{remainingBudget.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2.5 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
          {isPlanApplied ? (
            <Button
              type="button"
              variant="subtle"
              size="sm"
              onClick={handleReset}
              className="text-[#B96359] hover:bg-[#B96359]/10"
              icon={RotateCcw}
            >
              Reset to Baseline
            </Button>
          ) : (
            <div className="text-[11px] text-[#676B68] dark:text-[#969D96]">
              All changes previewed safely. Click confirm to synchronize live household.
            </div>
          )}

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
            >
              Close
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={!canApprove}
              onClick={handleExecute}
              icon={CheckCircle2}
            >
              {isPlanApplied ? 'Update Approvals' : 'Confirm & Synchronize'}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
