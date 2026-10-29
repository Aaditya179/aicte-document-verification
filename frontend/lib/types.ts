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
  source_method: 'PDF_TEXT' | 'OCR' | 'MANUAL' | 'AI_SUGGESTED' | null;
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

export type RuleStatus = 'draft' | 'pending_approval' | 'active' | 'retired';

export interface Rule {
  id: string;
  rule_code: string;
  version: number;
  title: string | null;
  description: string | null;
  check_type: string;
  params: Record<string, unknown>;
  severity: string | null;
  status: RuleStatus;
  effective_from: string | null;
  effective_to: string | null;
  note: string | null;
  source_reference: string | null;
  clause: string | null;
  created_by: string | null;
  created_by_name: string | null;
  approved_by: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  check: string | null;
  finding_types: string[];
}

export type ParamSpec =
  | { kind: 'number' | 'int'; min: number; max: number; label: string }
  | { kind: 'bool'; label: string }
  | { kind: 'choices'; choices: string[]; label: string };

export interface RuleEvent {
  id: number;
  event_type: string;
  actor_role: string | null;
  actor_id: string | null;
  actor_name: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface RuleDetail {
  rule: Rule;
  versions: Rule[];
  history: RuleEvent[];
  params_schema: Record<string, ParamSpec>;
}

type ImpactFinding = { key: string; title: string; severity: string };

export interface RuleImpact {
  rule_code: string;
  version: number;
  check: string | null;
  compared_with: number | null;
  as_of_date: string;
  available: boolean;
  note: string;
  applications: { id: string; code: string; institution: string | null; created: ImpactFinding[]; closed: ImpactFinding[]; unchanged: number }[];
  totals: { applications_checked: number; affected: number; created: number; closed: number };
}

/** A version is "approved" between a second administrator's approval and activation; the stored status stays pending_approval. */
export function ruleStage(r: Pick<Rule, 'status' | 'approved_by'>): { label: string; tone: 'neutral' | 'pending' | 'active' | 'ok' } {
  if (r.status === 'pending_approval') return r.approved_by ? { label: 'Approved, not yet active', tone: 'ok' } : { label: 'Waiting for approval', tone: 'pending' };
  if (r.status === 'active') return { label: 'Active', tone: 'active' };
  if (r.status === 'draft') return { label: 'Draft', tone: 'neutral' };
  return { label: 'Retired', tone: 'neutral' };
}

export interface TrustedCertificate {
  name: string;
  subject: string;
  issuer: string;
  fingerprint: string;
  not_before: string;
  not_after: string;
  is_ca: boolean;
  source: string;
  added_at: string;
}

export interface ExtractionTemplate {
  id: string;
  doc_type: string;
  field_name: string;
  regex: string;
  group_index: number | null;
  value_type: string | null;
  required: boolean;
}

export interface AdminSettings {
  as_of: { mode: 'today' | 'fixed'; date: string | null; effective: string };
  priority_weights: { key: string; weight: number; label: string }[];
  categories: { code: string; label: string }[];
  document_types: { code: string; label: string; has_expiry: boolean; signature_required: boolean; is_photo: boolean }[];
  required_documents: { category: string; doc_type: string; mandatory: boolean }[];
  extraction_templates: ExtractionTemplate[];
  trust_store: TrustedCertificate[];
  registry_mode: string;
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
  entity_id: string | null;
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
    verification: { method: string; status: string; source: string | null; is_mock: boolean; checked_at: string; detail?: string }[];
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
  REGISTRY_MISMATCH: 'Differs from issuer registry',
  SIGNATURE_INVALID: 'Signature not verified',
  METADATA_ANOMALY: 'File metadata indicator',
};

// Authenticity (build spec 10). Each method keeps its own state; the latest check of a method is its state.
export type VerifyMethod = 'HASH' | 'SIGNATURE' | 'REGISTRY' | 'METADATA' | 'MANUAL';

export const VERIFY_METHOD_LABEL: Record<string, string> = {
  HASH: 'File check', SIGNATURE: 'Signature', REGISTRY: 'Issuer registry', METADATA: 'File metadata', MANUAL: 'Manual check with the issuer',
};

export const VERIFY_STATUS_LABEL: Record<string, string> = {
  passed: 'Passed', failed: 'Failed',
  match: 'Matches the registry', mismatch: 'Values differ from the registry', unavailable: 'Source unavailable (pending, not a failure)',
  manual_pending: 'Asked, waiting for an answer', manual_confirmed: 'Confirmed by the issuer', manual_not_confirmed: 'Issuer did not confirm',
  valid: 'Valid', invalid: 'Does not verify', untrusted_chain: 'Untrusted certificate chain', unsigned: 'Unsigned', unsupported: 'Not supported',
  clear: 'No indicators', indicators: 'Indicators found',
};

export interface RegistryComparison {
  field: string;
  document_value: string | null;
  document_shown: string | null;
  page_number: number | null;
  value_type: string;
  registry_value: string | null;
  same: boolean | null;
}

export interface VerificationCheck {
  id: string;
  document_id: string;
  method: VerifyMethod;
  source: string | null;
  status: string;
  is_mock: boolean;
  checked_by: string | null;
  checked_by_name: string | null;
  checked_at: string;
  response: {
    // REGISTRY
    mode?: string; issuer?: string; key?: { field: string; value: string }; record?: Record<string, string> | null;
    compared?: RegistryComparison[]; note?: string;
    // MANUAL
    contact?: string; attachment?: { name: string; mime: string; size: number } | null;
    // HASH
    sha256?: string;
    // SIGNATURE
    signatures?: { field: string; signer?: string | null; signer_issuer?: string | null; signed_at?: string | null; status: string; note: string }[];
    // METADATA
    indicators?: { code: string; text: string }[]; creation_date?: string | null; modification_date?: string | null;
    producer?: string | null; revisions?: number;
  };
}

export interface DocumentVerification {
  registry: { supported: boolean; issuer: string | null; key_field: string | null; mode: string; is_mock: boolean };
  checks: VerificationCheck[];
}

export type RegistryMode = 'unavailable' | 'match' | 'mismatch';

export interface RegistrySetting {
  mode: RegistryMode;
  modes: RegistryMode[];
  is_mock: boolean;
  documents: { doc_type: string; label: string; issuer: string; key: string; fields: string[] }[];
}

// Pre-flight (the institution's own check before submitting; nothing is stored)
export type WizardStep = 'details' | 'documents' | 'evidence' | 'preflight' | 'submit';

export interface PreflightItem {
  key: string;
  finding_type: string;
  rule_code: string;
  severity: string;
  title: string;
  detail: string;
  evidence: { document_id: string | null; page_number: number | null; role: string; label: string | null; shown_value: string | null }[];
  fix: { step: WizardStep; doc_type?: string | null; category?: string | null; anchor?: string; hint: string };
}

export interface PreflightResult {
  as_of_date: string;
  rule_versions: Record<string, number>;
  items: PreflightItem[];
  stored: false;
}

// Regulation clauses behind a finding (ASSUMPTIONS A41). The seeded clauses are illustrative, not AICTE text.
export interface RegulationClause {
  id: string;
  clause_ref: string;
  source: string;
  heading: string;
  body: string;
  rule_codes: string[];
  is_illustrative: boolean;
  /** How it was found for a finding: named by the rule, or by keyword search */
  matched_by?: 'rule' | 'search' | null;
  created_at?: string | null;
}

export interface FindingClauses {
  rule: { rule_code: string; version: number; title: string | null; description: string | null; source_reference: string | null; clause: string | null; note: string | null } | null;
  clauses: RegulationClause[];
  explanation?: { text: string; clause_refs: string[]; by: 'llm' | 'rules' };
}
