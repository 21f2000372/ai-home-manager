import { useState } from 'react';
import { CalendarDays, Check, CircleAlert, FileText, MessageCircle, Package, Plus, ShieldCheck, Sparkles, Users, WalletCards, Wrench } from 'lucide-react';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { Badge, type BadgeTone } from '@/components/design-system/badge';
import { Progress } from '@/components/design-system/progress';
import { SectionHeading } from '@/components/design-system/section-heading';
import { documents, events, expenses, inventoryAlerts, maintenanceIssues, members, tasks } from '@/data/homeops-fixtures';
import { PeoplePermissionsWorkspace } from '@/features/people-permissions/people-permissions-workspace';
import { GroceryWorkspace, InventoryWorkspace } from '@/features/inventory/inventory-workspace';
import { TaskWorkspace } from '@/features/tasks-schedule/task-workspace';
import { CalendarWorkspace } from '@/features/calendar-schedule';
import { sendAgentMessage, type PlannedAction } from '@/features/conversation/agent-api';
import { ApiError } from '@/lib/api/request';

type WorkspaceKind = 'people' | 'tasks' | 'calendar' | 'inventory' | 'grocery' | 'finance' | 'maintenance' | 'documents' | 'chat';

const pageMeta: Record<WorkspaceKind, { eyebrow: string; description: string; icon: typeof Users }> = {
  people: { eyebrow: 'People & privacy', description: 'Manage household roles, access, and shared privacy boundaries.', icon: Users },
  tasks: { eyebrow: 'Tasks & chores', description: 'Coordinate recurring work and make ownership visible.', icon: Check },
  calendar: { eyebrow: 'Schedule & events', description: 'Keep family plans, travel, and guest arrivals in one timeline.', icon: CalendarDays },
  inventory: { eyebrow: 'Food & inventory', description: 'Track household stock and turn low inventory into a grocery plan.', icon: Package },
  grocery: { eyebrow: 'Food & inventory', description: 'Organize the next household shop with verified constraints.', icon: Package },
  finance: { eyebrow: 'Finance & budget', description: 'See planned spend, expenses, bills, and the household buffer.', icon: WalletCards },
  maintenance: { eyebrow: 'Home maintenance', description: 'Track service needs, warranties, and repair history.', icon: Wrench },
  documents: { eyebrow: 'Knowledge & governance', description: 'Keep verified household records private, searchable, and current.', icon: FileText },
  chat: { eyebrow: 'Conversation workspace', description: 'Ask the household assistant to reason over approved context and propose actions.', icon: MessageCircle },
};

const actionLabels: Record<WorkspaceKind, string> = {
  people: 'Invite member',
  tasks: 'Add task',
  calendar: 'Add event',
  inventory: 'Add item',
  grocery: 'Add item',
  finance: 'Add expense',
  maintenance: 'Log repair',
  documents: 'Upload document',
  chat: 'New conversation',
};

export function DomainWorkspace({ kind }: { kind: WorkspaceKind }) {
  if (kind === 'people') return <PeoplePermissionsWorkspace />;
  if (kind === 'inventory') return <InventoryWorkspace />;
  if (kind === 'grocery') return <GroceryWorkspace />;
  const meta = pageMeta[kind];
  const Icon = meta.icon;
  return <section className="space-y-6"><div className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end"><div><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#ee7b4b]"><Icon size={14} />{meta.eyebrow}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl">{kind === 'chat' ? 'AI assistant' : kind[0].toUpperCase() + kind.slice(1)}</h1><p className="mt-2 max-w-xl text-sm leading-6 muted">{meta.description}</p></div><Button><Plus size={16} />{actionLabels[kind]}</Button></div>{renderWorkspace(kind)}</section>;
}

function renderWorkspace(kind: WorkspaceKind) {
  switch (kind) {
    case 'people': return <PeopleWorkspace />;
    case 'tasks': return <TaskWorkspace />;
    case 'calendar': return <CalendarWorkspace />;
    case 'inventory': return <InventoryWorkspace />;
    case 'grocery': return <GroceryWorkspace />;
    case 'finance': return <FinanceWorkspace />;
    case 'maintenance': return <MaintenanceWorkspace />;
    case 'documents': return <DocumentsWorkspace />;
    case 'chat': return <ChatWorkspace />;
  }
}

function PeopleWorkspace() {
  return <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]"><Card className="p-6"><SectionHeading title="Household members" detail="Access is scoped by role and capability." action={<Badge tone="verified">4 active</Badge>} /><div className="mt-6 space-y-3">{members.map((member) => <div key={member.id} className="flex flex-col gap-3 rounded-xl bg-[var(--surface-muted)] p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-full bg-[#d9eadf] text-sm font-semibold text-[#27736d]">{member.initials}</div><div><p className="text-sm font-semibold text-[var(--ink)]">{member.name}</p><p className="text-xs muted">{member.role} · {member.access}</p></div></div><Badge tone={member.status as BadgeTone}>{member.status}</Badge></div>)}</div></Card><Card className="p-6"><SectionHeading title="Privacy & access" detail="Verified governance boundaries" /><div className="mt-6 space-y-5"><div className="flex gap-3"><ShieldCheck className="shrink-0 text-[#27736d]" size={20} /><p className="text-sm leading-6 muted">Private documents and finance records are only visible to authorized adult members.</p></div><div className="rounded-xl bg-[#e1f1eb] p-4"><p className="text-sm font-semibold text-[#27736d]">No pending invites</p><p className="mt-1 text-xs text-[#37615e]">The household roster is up to date.</p></div></div></Card></div>;
}

function TasksWorkspace() {
  const [showCompleted, setShowCompleted] = useState(false);
  return <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]"><Card className="p-6"><SectionHeading title="Active household tasks" detail="Assigned across family members based on availability." action={<button className="text-xs font-semibold text-[#27736d]" onClick={() => setShowCompleted((value) => !value)}>{showCompleted ? 'Hide completed' : 'Show completed'}</button>} /><div className="mt-5 flex flex-wrap gap-2"><Badge tone="neutral">All owners</Badge><Badge tone="ready">On track</Badge><Badge tone="attention">Needs attention</Badge></div><div className="mt-5 space-y-3">{tasks.filter((task) => showCompleted || task.status !== 'verified').map((task) => <div key={task.id} className="flex items-start gap-3 rounded-xl border border-[var(--line)] p-4"><button aria-label={`Complete ${task.title}`} className="mt-0.5 grid size-5 place-items-center rounded-full border border-[var(--line)] text-transparent hover:border-[#27736d] hover:text-[#27736d]"><Check size={13} /></button><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-[var(--ink)]">{task.title}</p><p className="mt-1 text-xs muted">{task.owner} · {task.cadence}</p></div><Badge tone={task.priority === 'high' ? 'attention' : task.priority === 'low' ? 'ready' : 'planned'}>{task.priority}</Badge></div>)}</div></Card><Card className="p-6"><SectionHeading title="Task health" detail="This week's operating rhythm" /><div className="mt-7 space-y-7"><Progress label="On track" value={75} /><Progress label="Assigned" value={92} /><Progress label="Completed" value={61} /></div></Card></div>;
}

function FixtureInventoryWorkspace({ showGrocery }: { showGrocery: boolean }) {
  const items = showGrocery ? inventoryAlerts : inventoryAlerts.slice(0, 3);
  return <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]"><Card className="p-6"><SectionHeading title={showGrocery ? 'Next grocery run' : 'Pantry restock alerts'} detail={showGrocery ? 'Verified against household dietary and guest constraints.' : 'Items below their household threshold.'} action={<Badge tone="attention">{items.length} alerts</Badge>} /><div className="mt-6 space-y-3">{items.map((item) => <div key={item.id} className="flex items-center gap-4 rounded-xl border border-[var(--line)] p-4"><div className="grid size-10 shrink-0 place-items-center rounded-lg bg-[#fff0e9] text-[#c2603c]"><Package size={18} /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-[var(--ink)]">{item.title}</p><p className="mt-1 text-xs muted">{item.detail}</p></div><span className="text-xs font-semibold text-[#c2603c]">{item.quantity}</span></div>)}</div></Card><Card className="p-6"><SectionHeading title="Stock health" detail="Household thresholds" /><div className="mt-7 space-y-7"><Progress label="Fresh food" value={42} /><Progress label="Dry goods" value={76} /><Progress label="Medication" value={28} /></div></Card></div>;
}

function FinanceWorkspace() {
  return <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]"><Card className="p-6"><SectionHeading title="Weekly budget" detail="A clear view of planned and available spend." action={<Badge tone="ready">₹2,400 buffer</Badge>} /><div className="mt-7"><div className="flex items-end justify-between"><p className="font-display text-4xl font-semibold text-[var(--ink)]">₹5,000</p><p className="text-sm muted">of ₹5,000 planned</p></div><div className="mt-4"><Progress label="Planned spend" value={52} /></div></div><div className="mt-7 grid gap-3 sm:grid-cols-3"><Stat label="Planned" value="₹2,600" /><Stat label="Spent" value="₹1,050" /><Stat label="Remaining" value="₹2,400" /></div></Card><Card className="p-6"><SectionHeading title="Recent expenses" detail="Latest household activity" /><div className="mt-5 space-y-3">{expenses.map((expense) => <div key={expense.id} className="flex items-center justify-between gap-3 border-b border-[var(--line)] pb-3 last:border-0"><div><p className="text-sm font-semibold text-[var(--ink)]">{expense.title}</p><p className="mt-1 text-xs muted">{expense.category} · {expense.date}</p></div><span className="text-sm font-semibold text-[var(--ink)]">{expense.amount}</span></div>)}</div></Card></div>;
}

function MaintenanceWorkspace() {
  return <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]"><Card className="p-6"><SectionHeading title="Service status" detail="Appliances and repair history" action={<Badge tone="attention">1 needs service</Badge>} /><div className="mt-6 space-y-3">{maintenanceIssues.map((issue) => <div key={issue.id} className="flex items-start gap-3 rounded-xl bg-[var(--surface-muted)] p-4"><Wrench size={18} className="mt-0.5 text-[#ee7b4b]" /><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-[var(--ink)]">{issue.title}</p><p className="mt-1 text-xs muted">{issue.location} · {issue.due}</p></div><Badge tone={issue.status as BadgeTone}>{issue.status}</Badge></div>)}</div></Card><Card className="p-6"><SectionHeading title="Maintenance rhythm" detail="Keep recurring work visible." /><div className="mt-6 space-y-4"><div className="rounded-xl bg-[#fff0e9] p-4"><p className="text-sm font-semibold text-[#c2603c]">Guest room AC filter</p><p className="mt-1 text-xs text-[#8d4b35]">Schedule a service before guests arrive Saturday.</p></div><Button>Log a repair</Button></div></Card></div>;
}

function DocumentsWorkspace() {
  return <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]"><Card className="p-6"><SectionHeading title="Verified household documents" detail="Governance rules and important records." action={<Badge tone="verified">Private</Badge>} /><div className="mt-6 space-y-3">{documents.map((document) => <div key={document.id} className="flex items-center gap-4 rounded-xl border border-[var(--line)] p-4"><div className="grid size-10 shrink-0 place-items-center rounded-lg bg-[#e3edf8] text-[#346b8e]"><FileText size={18} /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-[var(--ink)]">{document.title}</p><p className="mt-1 text-xs muted">{document.type} · {document.updated}</p></div><Badge tone={document.status as BadgeTone}>{document.status}</Badge></div>)}</div></Card><Card className="p-6"><SectionHeading title="Document actions" detail="Keep sensitive records current." /><div className="mt-6 space-y-3"><Button>Upload document</Button><Button tone="neutral">Review access</Button><div className="flex gap-3 rounded-xl bg-[#e1f1eb] p-4"><ShieldCheck className="shrink-0 text-[#27736d]" size={18} /><p className="text-xs leading-5 text-[#37615e]">AI agents can use verified summaries without exposing private source files.</p></div></div></Card></div>;
}

type ChatMessage = { id: string; sender: 'user' | 'assistant'; text: string };

function ChatWorkspace() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [actions, setActions] = useState<PlannedAction[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;

    const userMessage: ChatMessage = { id: crypto.randomUUID(), sender: 'user', text };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsSending(true);
    setError(null);

    try {
      const result = await sendAgentMessage({ message: text, conversationId });
      setConversationId(result.conversation_id);
      setActions(result.planned_actions ?? []);
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), sender: 'assistant', text: result.response || 'No response.' },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 401
            ? 'Please sign in to use the assistant.'
            : err.message
          : 'The assistant is unavailable. Please try again.';
      setError(message);
    } finally {
      setIsSending(false);
    }
  }

  return <div className="grid gap-5 xl:grid-cols-[1fr_0.75fr]"><Card className="flex min-h-[480px] flex-col p-6"><SectionHeading title="Ask HomeOps Assistant" detail="Plans are visible and require confirmation before changes." action={<Badge tone={isSending ? 'attention' : 'ready'}>{isSending ? 'Thinking…' : 'Ready'}</Badge>} /><div className="mt-6 flex-1 space-y-4">{messages.length === 0 ? <div className="max-w-xl rounded-2xl rounded-tl-sm bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--ink)]">Ask me about your household — tasks, groceries, expenses, maintenance, and more. For example: “What tasks are assigned to me?”</div> : messages.map((message) => message.sender === 'user' ? <div key={message.id} className="ml-auto max-w-xl whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-[#27736d] p-4 text-sm leading-6 text-white">{message.text}</div> : <div key={message.id} className="max-w-xl whitespace-pre-wrap rounded-2xl rounded-tl-sm bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--ink)]">{message.text}</div>)}{isSending ? <div className="max-w-xl rounded-2xl rounded-tl-sm bg-[var(--surface-muted)] p-4 text-sm leading-6 muted">Thinking…</div> : null}{error ? <div className="max-w-xl rounded-2xl bg-[#fff0e9] p-4 text-sm leading-6 text-[#c2603c]">{error}</div> : null}</div><div className="mt-6 flex gap-2"><input value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void handleSend(); } }} disabled={isSending} className="min-h-11 min-w-0 flex-1 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-4 text-sm text-[var(--ink)] outline-none focus:border-[#27736d] disabled:opacity-60" placeholder="Ask about your household..." aria-label="Ask the household assistant" /><Button aria-label="Send message" onClick={() => void handleSend()} disabled={isSending}><MessageCircle size={16} /></Button></div></Card><Card className="p-6"><SectionHeading title="Agent reasoning" detail="Multi-agent state, bounded and reviewable." action={<Sparkles size={18} className="text-[#ee7b4b]" />} /><div className="mt-6 space-y-4">{actions.length === 0 ? <p className="text-sm leading-6 muted">Planned actions from the assistant will appear here after you send a message.</p> : actions.map((action, index) => <div key={index} className="flex gap-3"><div className={`mt-1 grid size-6 shrink-0 place-items-center rounded-full ${action.status === 'completed' ? 'bg-[#e1f1eb] text-[#27736d]' : action.status === 'unauthorized' || action.status === 'failed' ? 'bg-[#fff0e9] text-[#c2603c]' : 'bg-[var(--surface-muted)] text-[var(--muted)]'}`}>{action.status === 'completed' ? <Check size={14} /> : action.status === 'unauthorized' || action.status === 'failed' ? <CircleAlert size={14} /> : <span className="size-1.5 rounded-full bg-current" />}</div><div className="min-w-0"><p className="text-sm font-semibold text-[var(--ink)]">{action.intent || action.description}</p><p className="mt-1 text-xs leading-5 muted">{action.domain}{action.result ? ` · ${action.result}` : ''}</p></div></div>)}</div></Card></div>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-[var(--surface-muted)] p-3"><p className="text-xs muted">{label}</p><p className="mt-1 font-display text-lg font-semibold text-[var(--ink)]">{value}</p></div>;
}
