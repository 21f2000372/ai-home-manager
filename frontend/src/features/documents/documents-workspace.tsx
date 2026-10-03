import { useState } from 'react';
import { AlertTriangle, ExternalLink, FileText, LoaderCircle, ShieldCheck } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Badge, type BadgeTone } from '@/components/design-system/badge';
import { Card } from '@/components/design-system/card';
import { SectionHeading } from '@/components/design-system/section-heading';
import { ApiError } from '@/lib/api/request';
import { Button } from '@/components/design-system/button';
import { getDocumentViewLink, getDocuments, getPendingDocumentViewLink, type DocumentCollection, type DocumentRecordLink, type HouseholdDocument, type PendingDocument } from './documents-api';

type DocumentView = 'approved' | 'pending' | 'links';
const documentQueryKey = ['household', 'documents'] as const;

const dateLabel = (value: string | null) => value
  ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
  : 'Date unavailable';

const fileSizeLabel = (value: number | null) => {
  if (value === null) return 'Size unavailable';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
};

function statusTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();
  if (normalized === 'approved' || normalized === 'completed') return 'verified';
  if (normalized.includes('review') || normalized.includes('failed')) return 'attention';
  if (normalized === 'staged') return 'planned';
  return 'neutral';
}

export function DocumentsWorkspace() {
  const [view, setView] = useState<DocumentView>('approved');
  const documents = useQuery({ queryKey: documentQueryKey, queryFn: getDocuments });
  const data = documents.data;
  const counts = {
    approved: data?.documents.length ?? 0,
    pending: data?.pending_uploads.length ?? 0,
    links: data?.links.length ?? 0,
  };
  const errorMessage = documents.error instanceof ApiError
    ? documents.error.message
    : documents.error
      ? 'HomeOps could not load household documents.'
      : null;

  return <section className="space-y-6">
    <header className="flex flex-col justify-between gap-5 border-b border-[var(--line)] pb-6 sm:flex-row sm:items-end">
      <div>
        <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#5E9278]"><FileText size={14} />Household records</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--ink)] sm:text-4xl">Documents</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 muted">Approved records, your uploads awaiting review, and their connected household items.</p>
      </div>
      <div className="flex items-center gap-2 text-sm muted"><ShieldCheck size={17} className="text-[#42765C]" />Private records</div>
    </header>

    {errorMessage && <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-4 py-3 text-sm text-[#8B3F36]">
      <span>{errorMessage}</span><button className="font-semibold underline" onClick={() => void documents.refetch()}>Retry</button>
    </div>}

    <nav aria-label="Document views" className="flex flex-wrap gap-2 border-b border-[var(--line)]">
      <ViewButton current={view} value="approved" count={counts.approved} onSelect={setView}>Approved</ViewButton>
      <ViewButton current={view} value="pending" count={counts.pending} onSelect={setView}>Pending uploads</ViewButton>
      <ViewButton current={view} value="links" count={counts.links} onSelect={setView}>Record links</ViewButton>
    </nav>

    {documents.isLoading ? <LoadingState /> : data && <DocumentViewContent data={data} view={view} />}
  </section>;
}

function ViewButton({ current, value, count, onSelect, children }: { current: DocumentView; value: DocumentView; count: number; onSelect: (view: DocumentView) => void; children: string }) {
  const selected = current === value;
  return <button
    aria-current={selected ? 'page' : undefined}
    className={`-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-3 text-sm font-semibold transition-colors ${selected ? 'border-[#5E9278] text-[var(--ink)]' : 'border-transparent text-[var(--muted)] hover:text-[var(--ink)]'}`}
    onClick={() => onSelect(value)}
  >{children}<span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-xs">{count}</span></button>;
}

function DocumentViewContent({ data, view }: { data: DocumentCollection; view: DocumentView }) {
  if (view === 'approved') {
    return <RecordList title="Approved documents" detail="Documents available under your household role." empty="No approved documents are available." items={data.documents} renderItem={(document) => <ApprovedDocument key={document.document_id} document={document} links={data.links.filter((link) => link.document_id === document.document_id)} />} />;
  }
  if (view === 'pending') {
    return <RecordList title="Your pending uploads" detail="Only uploads submitted by your account are shown here." empty="You have no pending document uploads." items={data.pending_uploads} renderItem={(pending) => <PendingDocumentRow key={pending.pending_id} pending={pending} />} />;
  }
  return <RecordList title="Linked household records" detail="Each link connects an approved document to a domain record." empty="No approved documents are linked to household records." items={data.links} renderItem={(link) => <DocumentLinkRow key={link.link_id} link={link} document={data.documents.find((item) => item.document_id === link.document_id)} />} />;
}

function RecordList<T>({ title, detail, empty, items, renderItem }: { title: string; detail: string; empty: string; items: T[]; renderItem: (item: T) => React.ReactNode }) {
  return <Card className="p-5 sm:p-6">
    <SectionHeading title={title} detail={detail} action={<Badge tone="neutral">{items.length} records</Badge>} />
    {items.length ? <div className="mt-5 divide-y divide-[var(--line)]">{items.map(renderItem)}</div> : <p className="mt-5 rounded-xl bg-[var(--surface-muted)] p-4 text-sm muted">{empty}</p>}
  </Card>;
}

function ApprovedDocument({ document, links }: { document: HouseholdDocument; links: DocumentRecordLink[] }) {
  const [opening, setOpening] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);
  const title = document.original_filename || document.classified_document_type || 'Untitled document';

  async function viewDocument() {
    const tab = window.open('about:blank', '_blank');
    if (tab) tab.opener = null;
    setOpening(true);
    setViewError(null);
    try {
      const result = await getDocumentViewLink(document.document_id);
      if (tab) tab.location.href = result.download_url;
      else window.location.assign(result.download_url);
    } catch (error) {
      tab?.close();
      setViewError(error instanceof ApiError ? error.message : 'Unable to open this document.');
    } finally {
      setOpening(false);
    }
  }

  return <article className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-start">
    <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-[#E3EDF8] text-[#346B8E]"><FileText size={18} /></div>
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2"><h3 className="break-words text-sm font-semibold text-[var(--ink)]">{title}</h3><Badge tone={statusTone(document.status)}>{document.status}</Badge></div>
      <p className="mt-1 text-xs muted">{document.classified_document_type || document.document_type}{document.domain ? ` · ${document.domain}` : ''} · {dateLabel(document.created_at)}</p>
      <p className="mt-1 text-xs muted">{document.mime_type || document.extension || 'File type unavailable'} · {fileSizeLabel(document.file_size)}{document.page_count ? ` · ${document.page_count} pages` : ''}</p>
      {links.length > 0 && <p className="mt-2 text-xs text-[#42765C]">Linked to {links.map((link) => `${link.linked_domain} record`).join(', ')}</p>}
      {document.classification_reason && <p className="mt-2 text-xs leading-5 muted">{document.classification_reason}</p>}
      {viewError && <p role="alert" className="mt-2 text-xs text-[#8B3F36]">{viewError}</p>}
    </div>
    <Button tone="neutral" onClick={viewDocument} disabled={opening} aria-label={`View ${title}`}>
      {opening ? <LoaderCircle size={16} className="animate-spin" /> : <ExternalLink size={16} />}
      {opening ? 'Opening' : 'View'}
    </Button>
  </article>;
}

function PendingDocumentRow({ pending }: { pending: PendingDocument }) {
  const [opening, setOpening] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);
  const title = pending.original_filename || 'Untitled upload';

  async function viewPendingDocument() {
    const tab = window.open('about:blank', '_blank');
    if (tab) tab.opener = null;
    setOpening(true);
    setViewError(null);
    try {
      const result = await getPendingDocumentViewLink(pending.pending_id);
      if (tab) tab.location.href = result.view_url;
      else window.location.assign(result.view_url);
    } catch (error) {
      tab?.close();
      setViewError(error instanceof ApiError ? error.message : 'Unable to open this pending upload.');
    } finally {
      setOpening(false);
    }
  }

  return <article className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-start">
    <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-[#FFF0E9] text-[#A34F32]"><FileText size={18} /></div>
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2"><h3 className="break-words text-sm font-semibold text-[var(--ink)]">{title}</h3><Badge tone={statusTone(pending.status)}>{pending.status.replaceAll('_', ' ')}</Badge></div>
      <p className="mt-1 text-xs muted">{pending.classified_document_type || 'Classification pending'}{pending.domain ? ` · ${pending.domain}` : ''} · {dateLabel(pending.created_at)}</p>
      <p className="mt-1 text-xs muted">{pending.mime_type || pending.extension || 'File type unavailable'} · {fileSizeLabel(pending.file_size)}{pending.page_count ? ` · ${pending.page_count} pages` : ''}</p>
      {pending.review_reasons.map((reason) => <p key={reason} className="mt-2 flex items-start gap-2 text-xs leading-5 text-[#8D4B35]"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{reason}</p>)}
      {pending.classification_reason && <p className="mt-2 text-xs leading-5 muted">{pending.classification_reason}</p>}
      {viewError && <p role="alert" className="mt-2 text-xs text-[#8B3F36]">{viewError}</p>}
    </div>
    <Button tone="neutral" onClick={viewPendingDocument} disabled={opening} aria-label={`View pending upload ${title}`}>
      {opening ? <LoaderCircle size={16} className="animate-spin" /> : <ExternalLink size={16} />}
      {opening ? 'Opening' : 'View'}
    </Button>
  </article>;
}

function DocumentLinkRow({ link, document }: { link: DocumentRecordLink; document: HouseholdDocument | undefined }) {
  const [opening, setOpening] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);
  const title = document?.original_filename || document?.classified_document_type || 'Document';

  async function viewLinkedDocument() {
    if (!document) return;
    const tab = window.open('about:blank', '_blank');
    if (tab) tab.opener = null;
    setOpening(true);
    setViewError(null);
    try {
      const result = await getDocumentViewLink(document.document_id);
      if (tab) tab.location.href = result.download_url;
      else window.location.assign(result.download_url);
    } catch (error) {
      tab?.close();
      setViewError(error instanceof ApiError ? error.message : 'Unable to open the linked document.');
    } finally {
      setOpening(false);
    }
  }

  return <article className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
    <div className="min-w-0">
      <h3 className="break-words text-sm font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-1 text-xs muted">{link.linked_domain} record · {link.linked_record_id}</p>
      {viewError && <p role="alert" className="mt-2 text-xs text-[#8B3F36]">{viewError}</p>}
    </div>
    <div className="flex shrink-0 items-center gap-3">
      <p className="text-xs muted">Linked {dateLabel(link.created_at)}</p>
      <Button tone="neutral" onClick={viewLinkedDocument} disabled={!document || opening} aria-label={`View linked document ${title}`}>
        {opening ? <LoaderCircle size={16} className="animate-spin" /> : <ExternalLink size={16} />}
        {opening ? 'Opening' : 'View document'}
      </Button>
    </div>
  </article>;
}

function LoadingState() {
  return <p className="flex items-center gap-2 py-8 text-sm muted"><LoaderCircle size={16} className="animate-spin" />Loading household documents…</p>;
}