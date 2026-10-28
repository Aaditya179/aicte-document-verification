export type Role = 'institution' | 'reviewer' | 'rule_admin';

export type WorkflowStatus = 'draft' | 'submitted' | 'under_review' | 'awaiting_institution' | 'review_complete';

export interface InstitutionRef {
  id?: string;
  code: string;
  name: string;
  city: string | null;
  is_fictional?: boolean;
}

export interface Application {
  id: string;
  code: string;
  institution_id: string;
  category: 'new_institution' | 'extension_of_approval';
  academic_year: string;
  workflow_status: WorkflowStatus;
  admin_status: 'pending';
  declared_total_area_sqm: number | null;
  submitted_at: string | null;
  review_deadline: string | null;
  created_at: string;
}

export interface ApplicationRow extends Application {
  institution: InstitutionRef;
  documents: { current: number; failed_check: number; being_read: number };
}

export interface DocumentRow {
  id: string;
  application_id: string;
  doc_type: string;
  version: number;
  supersedes_id: string | null;
  status: 'current' | 'superseded';
  original_name: string | null;
  mime: string;
  size_bytes: number | null;
  page_count: number | null;
  sha256: string | null;
  integrity_status: 'pending' | 'passed' | 'failed';
  integrity_note: string | null;
  processing_status: 'pending' | 'processing' | 'done' | 'error';
  processing_note: string | null;
  uploaded_at: string;
  photo_category: string | null;
  application_code?: string;
  photo?: {
    phash: string | null;
    width: number | null;
    height: number | null;
    taken_at: string | null;
    gps: { lat: number; lon: number } | null;
    exif: Record<string, string | number> | null;
  };
}

export interface ChecklistItem {
  doc_type: string;
  label: string;
  mandatory: boolean;
  present: boolean;
}

export interface ApplicationDetail {
  application: Application;
  institution: InstitutionRef;
  documents: DocumentRow[];
  checklist: ChecklistItem[];
  photo_categories: string[];
}

export interface ExtractedField {
  id: string;
  field_name: string;
  field_value: string | null;
  original_value: string | null;
  value_type: string;
  page_number: number | null;
  source_method: 'PDF_TEXT' | 'OCR' | 'MANUAL' | null;
  confidence: number | null;
  review_state: 'auto' | 'needs_confirmation' | 'confirmed' | 'corrected';
  review_reason: string | null;
}

export interface FacultyRow {
  id: string;
  faculty_code: string;
  name_raw: string;
  designation: string | null;
  qualification: string | null;
  masked_id: string | null;
  page_number: number | null;
  period_start: string | null;
  period_end: string | null;
}

export interface DocumentType {
  code: string;
  label: string;
  has_expiry: boolean;
  signature_required: boolean;
  is_photo: boolean;
}

export interface Reference {
  categories: { code: string; label: string }[];
  document_types: DocumentType[];
  required_documents: { category: string; doc_type: string; mandatory: boolean }[];
}

export interface Rule {
  id: string;
  rule_code: string;
  version: number;
  title: string | null;
  description: string | null;
  check_type: string;
  params: Record<string, unknown>;
  severity: string | null;
  status: 'draft' | 'pending_approval' | 'active' | 'retired';
  effective_from: string | null;
  effective_to: string | null;
  note: string;
}

export interface DemoAccount {
  email: string;
  full_name: string;
  role: Role;
  institution: string | null;
  description: string;
}

export const ROLE_LABEL: Record<Role, string> = {
  institution: 'Institution',
  reviewer: 'Scrutiny reviewer',
  rule_admin: 'Rule administrator',
};

export const CATEGORY_LABEL: Record<Application['category'], string> = {
  new_institution: 'New institution',
  extension_of_approval: 'Extension of approval',
};

export const WORKFLOW_LABEL: Record<WorkflowStatus, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  awaiting_institution: 'Waiting for the institution',
  review_complete: 'Review complete',
};

export const PHOTO_CATEGORY_LABEL: Record<string, string> = {
  lab: 'Lab', classroom: 'Classroom', library: 'Library', other: 'Other',
};

export function humanize(code: string) {
  const s = code.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Findings, statuses and priority (phase 2)

export type FindingStatus = 'open' | 'evidence_requested' | 'resolved' | 'dismissed' | 'auto_closed';
export type ReviewActionKind = 'resolve' | 'dismiss' | 'request_evidence';

export interface FindingEvidence {
  id: string;
  document_id: string | null;
  page_number: number | null;
  role: 'A' | 'B' | 'SINGLE' | null;
  label: string | null;
  shown_value: string | null;
  document: { doc_type: string; original_name: string | null; version: number; status: string; mime: string } | null;
}

export interface ReviewAction {
  id: string;
  action: ReviewActionKind | 'confirm_field' | 'correct_field';
  action_label: string;
  reason: string;
  actor_name: string | null;
  actor_role: string | null;
  created_at: string;
}

export interface EvidenceRequest {
  id: string;
  message: string | null;
  due_date: string | null;
  status: 'open' | 'fulfilled' | 'cancelled';
  fulfilled_by_document_id?: string | null;
  created_at: string;
}

export interface Finding {
  id: string;
  finding_key: string;
  application_id: string;
  related_application_id: string | null;
  finding_type: string;
  rule_code: string | null;
  rule_version: number | null;
  severity: 'info' | 'low' | 'medium' | 'high' | null;
  title: string;
  detail: string;
  status: FindingStatus;
  is_cross_institution: boolean;
  created_at: string;
  evidence: FindingEvidence[];
  actions: ReviewAction[];
  evidence_requests: EvidenceRequest[];
}

export interface StatusCard {
  key: 'integrity' | 'consistency' | 'authenticity' | 'compliance';
  label: string;
  value: string;
  tone: 'ok' | 'conflict' | 'pending' | 'neutral';
  reasons: string[];
}

export interface LatestRun {
  id: string;
  started_at: string;
  as_of_date: string;
  rule_versions?: Record<string, number>;
  summary: { findings: number; created: number; reopened: number; still_open: number; auto_closed: number } | null;
}

export interface StatusView {
  statuses: StatusCard[];
  administrative: string;
  last_run: LatestRun | null;
}

export interface PriorityTerm {
  key: string;
  label: string;
  weight: number;
  count: number;
  contribution: number;
}

export interface Priority {
  score: number;
  band: 'High' | 'Medium' | 'Low';
  raw: number;
  capped: boolean;
  unresolved: number;
  days_to_deadline: number | null;
  composition: PriorityTerm[];
}

export interface ValidateResult {
  run_id: string;
  as_of_date: string;
  rule_versions: Record<string, number>;
  summary: NonNullable<LatestRun['summary']>;
  statuses: StatusView;
  priority: Priority;
}

export interface AuditEvent {
  id: number;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  event_type: string;
  entity_type: string | null;
  application_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
  event_hash: string;
}

export interface CaseFile {
  application: Pick<Application, 'id' | 'code' | 'category' | 'academic_year' | 'workflow_status' | 'submitted_at' | 'review_deadline' | 'declared_total_area_sqm'>;
  institution: InstitutionRef;
  statuses: StatusView;
  priority: Priority;
  findings: Finding[];
  documents: {
    id: string; doc_type: string; label: string; original_name: string | null; version: number; status: string;
    sha256: string | null; integrity_status: string; integrity_note: string | null; uploaded_at: string;
    verification: { method: string; status: string; source: string | null; is_mock: boolean; checked_at: string }[];
  }[];
  reviewer_actions: (ReviewAction & { finding_title: string; finding_key: string })[];
  latest_run: LatestRun | null;
  rule_versions: { rule_code: string; version: number; title: string | null; note: string | null }[];
  final_decision: string;
  disclaimers: string[];
}

export const FINDING_STATUS_LABEL: Record<FindingStatus, string> = {
  open: 'Open',
  evidence_requested: 'Evidence requested',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
  auto_closed: 'Closed by a later run',
};

export const SEVERITY_LABEL: Record<string, string> = {
  info: 'Information', low: 'Low', medium: 'Medium', high: 'High',
};

// Queue, cross-institution flags, rooms, notifications and evidence requests (phase 3)

export interface QueueRow {
  application: Pick<Application, 'id' | 'code' | 'category' | 'academic_year' | 'workflow_status' | 'submitted_at' | 'review_deadline'>;
  institution: InstitutionRef & { id: string };
  priority: Priority;
  finding_types: string[];
  cross_flags: number;
  last_run_at: string | null;
}

export interface CrossApplication {
  id: string;
  code: string;
  workflow_status: WorkflowStatus;
  institution: InstitutionRef;
}

export interface CrossFlag {
  id: string;
  finding_key: string;
  finding_type: 'REUSED_IDENTIFIER' | 'GHOST_FACULTY' | 'PHOTO_REUSE';
  title: string;
  status: FindingStatus;
  created_at: string;
  application: CrossApplication | null;
  related_application: CrossApplication | null;
}

export interface Room {
  id?: string;
  room_label: string;
  length_m: number;
  width_m: number;
  area_sqm?: number;
}

export interface RoomView {
  rooms: Room[];
  total_sqm: number;
  declared_total_area_sqm: number | null;
}

export interface AppNotification {
  id: string;
  kind: string;
  ref_type: string | null;
  ref_id: string | null;
  message: string;
  read_at: string | null;
  created_at: string;
}

export interface EvidenceRequestRow extends EvidenceRequest {
  finding_id: string;
  application_id: string;
  finding: { id: string; title: string; finding_type: string; status: FindingStatus };
  application: { id: string; code: string; workflow_status: WorkflowStatus };
}

export const FINDING_TYPE_LABEL: Record<string, string> = {
  MISSING_DOCUMENT: 'Missing document',
  EXPIRED_DOCUMENT: 'Expired document',
  DATE_ORDER_INVALID: 'Dates out of order',
  DATE_CONFLICT: 'Date conflict',
  ID_MISMATCH: 'ID mismatch',
  COUNT_CONFLICT: 'Count conflict',
  FIELD_NEEDS_CONFIRMATION: 'Value needs confirmation',
  DUPLICATE_FILE: 'Duplicate file',
  REUSED_IDENTIFIER: 'Identifier in another application',
  GHOST_FACULTY: 'Faculty listed elsewhere',
  PHOTO_REUSE: 'Photo matches another application',
  INFRA_EVIDENCE_MISSING: 'Infrastructure evidence missing',
  AREA_MISMATCH: 'Area mismatch',
  AREA_BELOW_MINIMUM: 'Area below minimum',
  PHOTO_METADATA: 'Photo date',
};
