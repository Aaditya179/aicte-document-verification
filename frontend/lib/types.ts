export type CheckStatus = 'verified' | 'conflict' | 'unverified';

export type Tally = Record<CheckStatus, number>;

export interface Institution {
  id?: string;
  name: string;
  aicte_id: string | null;
  state?: string | null;
  city?: string | null;
}

export interface CaseRow {
  id: string;
  case_no: string;
  institution_id: string;
  application_type: string;
  academic_year: string;
  status: 'open' | 'in_review' | 'closed';
  created_at: string;
  institutions: Institution | null;
  checks: Tally;
}

export interface Fact {
  id: string;
  document_id: string | null;
  field: string;
  value_text: string;
  page: number | null;
  source_quote: string | null;
  confidence: number | null;
  extracted_by: string;
}

export interface Check {
  id: string;
  field: string;
  status: CheckStatus;
  reason: string;
  rule: string | null;
  facts: Fact[];
  reviewed_at: string | null;
  review_note: string | null;
}

export interface DocumentRow {
  id: string;
  doc_type: string;
  title: string;
  sha256: string | null;
  page_count: number | null;
  uploaded_at: string;
}

export interface Pattern {
  id: string;
  kind: string;
  match_key: string;
  summary: string;
  severity: 'low' | 'medium' | 'high';
  institution_ids: string[];
  case_ids: string[];
  status: 'open' | 'confirmed' | 'dismissed';
  detected_at: string;
}

export interface CaseFile {
  case: CaseRow & { institutions: Institution };
  documents: DocumentRow[];
  checks: Check[];
  summary: Tally;
  patterns: Pattern[];
}

export const STATUS_META: Record<CheckStatus, { label: string; tone: 'green' | 'red' | 'amber'; blurb: string }> = {
  verified: { label: 'Verified', tone: 'green', blurb: 'The documents agree with each other and with the record.' },
  conflict: { label: 'Conflict', tone: 'red', blurb: 'Two sources disagree, or a value breaks a rule.' },
  unverified: { label: 'Unverified', tone: 'amber', blurb: 'Not enough evidence yet to say either way.' },
};

export function humanize(code: string) {
  const s = code.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}
