import React, { useState, useRef, useEffect } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { WeekendPlanModal } from '../modals/WeekendPlanModal';
import { 
  Send, 
  Sparkles, 
  CheckCircle2, 
  UtensilsCrossed, 
  Wallet, 
  CheckSquare, 
  Wrench, 
  Lock
} from 'lucide-react';

const SUGGESTIONS = [
  { label: "Plan for this weekend", prompt: "Mom will be away until Friday. Dad has a verified low-salt dietary restriction. Grandma's medicine needs to be purchased. Four relatives are coming Saturday, and we have ₹5,000 remaining this week." },
  { label: "Remaining budget?", prompt: "How much household budget is remaining this week?" },
  { label: "Pending chores?", prompt: "What chores are pending for me?" },
  { label: "Pantry needs?", prompt: "What groceries and pantry items do we need to buy?" },
  { label: "AC status?", prompt: "Check appliance maintenance status and AC warranty." },
];

export const ChatView = () => {
  const { 
    chatMessages, 
    sendAgentMessage, 
    isProcessing, 
    activeUser, 
    applyPlan, 
    isPlanApplied,
    setActiveTab 
  } = useHousehold();

  const [inputVal, setInputVal] = useState('');
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isProcessing]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim() || isProcessing) return;
    sendAgentMessage(inputVal);
    setInputVal('');
  };

  return (
    <div className="flex flex-col h-[calc(100vh-145px)] md:h-[calc(100vh-120px)] max-w-3xl mx-auto rounded-2xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] overflow-hidden animate-fade-in shadow-xs">
      {/* Sticky Chat Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 sm:px-4 sm:py-3 border-b border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-[#5E9278]/20 text-[#5E9278] dark:text-[#9BCDB4] flex items-center justify-center font-bold text-xs shrink-0">
            H
          </div>
          <div className="min-w-0">
            <h2 className="text-xs sm:text-sm font-bold text-[#171918] dark:text-[#EFF1EC] truncate">
              HomeOps Coordinator
            </h2>
            <p className="text-[11px] text-[#676B68] dark:text-[#969D96] truncate">
              Perspective: <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{activeUser.name}</span> ({activeUser.role})
            </p>
          </div>
        </div>

        <Badge variant="agent" size="xs">
          Multi-Agent Ready
        </Badge>
      </div>

      {/* Scrollable Messages Stream */}
      <div className="flex-1 overflow-y-auto p-3.5 sm:p-4 space-y-3.5 min-h-0">
        {chatMessages.map((msg) => {
          const isUser = msg.sender === 'user';

          if (isUser) {
            return (
              <div key={msg.id} className="flex justify-end gap-2 max-w-lg ml-auto">
                <div className="space-y-0.5 text-right min-w-0">
                  <div className="text-[10px] text-[#676B68] dark:text-[#969D96]">
                    {msg.author} • {msg.timestamp}
                  </div>
                  <div className="p-2.5 sm:p-3 rounded-2xl rounded-tr-xs bg-[#5E9278] text-white text-xs sm:text-sm leading-relaxed shadow-xs text-left">
                    {msg.text}
                  </div>
                </div>
                <span className="text-lg mt-2 shrink-0">{msg.avatar}</span>
              </div>
            );
          }

          // Assistant Response
          const data = msg.data;
          const isProposal = data?.type === 'plan_proposal';
          const isPrivacy = data?.type === 'privacy_restricted';

          return (
            <div key={msg.id} className="flex gap-2.5 max-w-2xl">
              <div className="w-7 h-7 rounded-lg bg-[#5E9278]/20 text-[#5E9278] dark:text-[#9BCDB4] flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                H
              </div>

              <div className="flex-1 min-w-0 space-y-1.5">
                <div className="text-[10px] text-[#676B68] dark:text-[#969D96]">
                  HomeOps Agent • {msg.timestamp}
                </div>

                {isPrivacy ? (
                  <div className="p-3 sm:p-3.5 rounded-2xl rounded-tl-xs bg-[#B96359]/10 border border-[#B96359]/30 text-xs text-[#171918] dark:text-[#EFF1EC] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-[#B96359]">
                      <Lock className="w-3.5 h-3.5" />
                      <span>Privacy Notice</span>
                    </div>
                    <p className="leading-relaxed">{data.text}</p>
                    {data.actionTab && (
                      <button
                        onClick={() => setActiveTab(data.actionTab)}
                        className="text-xs font-semibold text-[#5E9278] dark:text-[#9BCDB4] hover:underline flex items-center gap-1 mt-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278]"
                      >
                        {data.actionLabel} →
                      </button>
                    )}
                  </div>
                ) : isProposal ? (
                  <div className="p-3.5 sm:p-4 rounded-2xl rounded-tl-xs bg-black/5 dark:bg-white/5 border border-[#5E9278]/40 space-y-3 shadow-xs">
                    <div>
                      <Badge variant="primary" size="xs" className="mb-1.5">Coordinated Plan</Badge>
                      <h4 className="font-bold text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC]">{data.title}</h4>
                      <p className="text-xs text-[#676B68] dark:text-[#969D96] mt-0.5 leading-relaxed">{data.summary}</p>
                    </div>

                    {/* Proposal Domain Blocks - Dense 2-column on tablet+ */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {/* Food */}
                      <div className="p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 space-y-1">
                        <span className="font-bold text-[#5E9278] dark:text-[#9BCDB4] flex items-center gap-1.5 text-[11px]">
                          <UtensilsCrossed className="w-3 h-3" /> Food & Groceries
                        </span>
                        <ul className="list-disc list-inside space-y-0.5 text-[#171918] dark:text-[#EFF1EC] text-[11px]">
                          {data.details.groceries.map((g, i) => (
                            <li key={i} className="truncate">{g}</li>
                          ))}
                        </ul>
                      </div>

                      {/* Tasks */}
                      <div className="p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 space-y-1">
                        <span className="font-bold text-[#5E9278] dark:text-[#9BCDB4] flex items-center gap-1.5 text-[11px]">
                          <CheckSquare className="w-3 h-3" /> Task Assignments
                        </span>
                        <ul className="list-disc list-inside space-y-0.5 text-[#171918] dark:text-[#EFF1EC] text-[11px]">
                          {data.details.tasks.map((t, i) => (
                            <li key={i} className="truncate">{t}</li>
                          ))}
                        </ul>
                      </div>

                      {/* Finance (if authorized) */}
                      {data.details.finance && (
                        <div className="p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 space-y-1">
                          <span className="font-bold text-[#5E9278] dark:text-[#9BCDB4] flex items-center gap-1.5 text-[11px]">
                            <Wallet className="w-3 h-3" /> Budget Impact
                          </span>
                          <div className="text-[#171918] dark:text-[#EFF1EC] text-[11px] space-y-0.5">
                            <div>• Groceries: {data.details.finance.groceries}</div>
                            <div>• Medicine: {data.details.finance.medicine}</div>
                            <div className="font-semibold text-[#5E9278] dark:text-[#9BCDB4]">
                              • {data.details.finance.remaining}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Maintenance */}
                      <div className="p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 space-y-1">
                        <span className="font-bold text-[#5E9278] dark:text-[#9BCDB4] flex items-center gap-1.5 text-[11px]">
                          <Wrench className="w-3 h-3" /> Appliance Service
                        </span>
                        <div className="text-[#171918] dark:text-[#EFF1EC] text-[11px]">
                          {data.details.maintenance[0]}
                        </div>
                      </div>
                    </div>

                    {/* Apply Action Button */}
                    <div className="pt-2 border-t border-[#D9D8D2]/60 dark:border-[#2D322E]/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <span className="text-[10px] text-[#676B68] dark:text-[#969D96]">
                        {isPlanApplied ? "Actions synced to household state" : "Human-in-the-Loop review & authorization"}
                      </span>

                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <Button
                          variant={isPlanApplied ? "secondary" : "primary"}
                          size="sm"
                          onClick={() => setIsPlanModalOpen(true)}
                          className="min-h-[36px]"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>{isPlanApplied ? "Review HITL Approvals" : "Authorize Plan (HITL)"}</span>
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-2.5 sm:p-3 rounded-2xl rounded-tl-xs bg-black/5 dark:bg-white/5 border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC] leading-relaxed space-y-1.5">
                    <p className="whitespace-pre-wrap">{data?.text || msg.text}</p>
                    {data?.items && (
                      <ul className="list-disc list-inside space-y-0.5 pt-0.5 text-xs">
                        {data.items.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    )}
                    {data?.actionTab && (
                      <button
                        onClick={() => setActiveTab(data.actionTab)}
                        className="text-xs font-semibold text-[#5E9278] dark:text-[#9BCDB4] hover:underline flex items-center gap-1 mt-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278]"
                      >
                        {data.actionLabel} →
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isProcessing && (
          <div className="flex gap-2 items-center text-xs text-[#676B68] dark:text-[#969D96] italic pl-9">
            <span className="w-1.5 h-1.5 rounded-full bg-[#5E9278] animate-pulse" />
            HomeOps is coordinating...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Sticky Bottom Area: Chips + Input Composer */}
      <div className="p-2.5 sm:p-3 border-t border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6]/95 dark:bg-[#181B18]/95 backdrop-blur-xs space-y-2 shrink-0">
        {/* Suggestion Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none text-xs">
          <span className="text-[10px] uppercase font-bold tracking-wider text-[#676B68] dark:text-[#969D96] shrink-0 mr-0.5">
            Ask:
          </span>
          {SUGGESTIONS.map((sug, i) => (
            <button
              key={i}
              onClick={() => sendAgentMessage(sug.prompt)}
              disabled={isProcessing}
              className="px-2.5 py-1 rounded-lg bg-black/5 dark:bg-white/5 border border-[#D9D8D2] dark:border-[#2D322E] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:border-[#5E9278] whitespace-nowrap text-[11px] transition-colors shrink-0 disabled:opacity-40 min-h-[32px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] active:scale-95"
            >
              {sug.label}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSubmit} className="relative flex items-center gap-1.5">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Tell HomeOps what changed or ask what to do..."
            disabled={isProcessing}
            className="flex-1 pl-3.5 pr-12 py-2 rounded-xl bg-white dark:bg-[#101210] border border-[#D9D8D2] dark:border-[#2D322E] text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC] placeholder-[#676B68]/70 dark:placeholder-[#969D96]/70 outline-none focus:border-[#5E9278] focus:ring-1 focus:ring-[#5E9278] min-h-[44px] transition-colors"
          />
          <button
            type="submit"
            disabled={!inputVal.trim() || isProcessing}
            aria-label="Send message"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 min-h-[36px] min-w-[36px] flex items-center justify-center rounded-lg bg-[#5E9278] hover:bg-[#4D7A64] text-white disabled:opacity-30 disabled:pointer-events-none transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5E9278]"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Weekend Plan HITL Approval Modal */}
      <WeekendPlanModal
        isOpen={isPlanModalOpen}
        onClose={() => setIsPlanModalOpen(false)}
      />
    </div>
  );
};
