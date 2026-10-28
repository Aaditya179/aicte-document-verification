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
