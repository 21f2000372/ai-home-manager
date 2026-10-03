import { request } from '@/lib/api/request';

export type HouseholdDocument = {
  document_id: string;
  document_type: string;
  classified_document_type: string | null;
  domain: string | null;
  classification_confidence: number | null;
  classification_reason: string | null;
  original_filename: string | null;
  mime_type: string | null;
  extension: string | null;
  file_size: number | null;
  extraction_method: string | null;
  page_count: number | null;
  prompt_injection_detected: boolean;
  status: string;
  uploaded_by: string | null;
  created_at: string | null;
};

export type PendingDocument = {
  pending_id: string;
  upload_id: string;
  original_filename: string;
  mime_type: string | null;
  extension: string | null;
  file_size: number | null;
  extraction_method: string | null;
  page_count: number | null;
  domain: string | null;
  classified_document_type: string | null;
  classification_confidence: number | null;
  classification_reason: string | null;
  prompt_injection_detected: boolean;
  status: string;
  review_reasons: string[];
  created_at: string | null;
};

export type DocumentRecordLink = {
  link_id: string;
  document_id: string;
  linked_domain: string;
  linked_record_id: string;
  created_at: string | null;
};

export type DocumentCollection = {
  documents: HouseholdDocument[];
  pending_uploads: PendingDocument[];
  links: DocumentRecordLink[];
};

export function getDocuments() {
  return request<DocumentCollection>('/api/documents', {}, { correlationId: crypto.randomUUID() });
}

export function getDocumentViewLink(documentId: string) {
  return request<{ document_id: string; filename: string; mime_type: string; download_url: string }>(
    `/api/documents/${encodeURIComponent(documentId)}/view`,
    {},
    { correlationId: crypto.randomUUID() },
  );
}

export function getPendingDocumentViewLink(pendingId: string) {
  return request<{ view_url: string }>(
    `/api/documents/pending/${encodeURIComponent(pendingId)}/view`,
    {},
    { correlationId: crypto.randomUUID() },
  );
}