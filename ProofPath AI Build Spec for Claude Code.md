# ProofPath AI: Build Spec for Claude Code

Oct 28, 2026 · @Aaditya

SIH 2026, PS SIH26261: AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification (AICTE). Stack: Next.js, FastAPI, Supabase. This document is written for Claude Code: build the whole product from it, one phase at a time.

## 0. How to use this document

- This is the single source of truth. If something is not specified, choose the simplest option and record the choice in `ASSUMPTIONS.md`. Ask before deviating from anything stated here.
- MUST means required. SHOULD means required unless impossible, in which case record why.
- If two sections conflict, section 1.2 (principles) wins, then sections 6 to 10 (logic), then the rest.
- **Secrets.** Real values live only in local `.env` files that are git-ignored. Never print, log, commit, or paste a secret into code, tests, docs or screenshots. Create `.env.example` with placeholders only. The Supabase service-role key MUST exist only in the backend environment; the frontend may only use variables that start with `NEXT_PUBLIC_`.
- **Shared project.** The Supabase project may also hold another app. Prefix every table with `pp_`, name the storage bucket `pp-files`, and never read or change tables without that prefix.
- **Words.** No UI text, code string or data value may state fraud, forged, fake, approve or reject as a system conclusion. Use conflict, mismatch, flag, candidate for review. Add an automated test that greps for these words in the frontend source and API response strings.
- All institutions, people, documents and photos are FICTIONAL and synthetic. All rules are ILLUSTRATIVE, not official AICTE rules. Everything simulated is labelled MOCK.
- UI colours, fonts and spacing come from screenshots the owner will place in `/design` (section 13). Do not invent a visual style before they arrive; use neutral placeholder tokens.

## 1. Product summary

### 1.1 What it is

ProofPath AI is an evidence-first validation layer beside the AICTE approval workflow. It ingests an application, extracts claims from every document, checks them against versioned rules and against each other, runs the authenticity checks that are genuinely possible, compares claims across institutions, and gives the reviewer a case file in which every finding links to its exact evidence. It reports four independent statuses and routes uncertainty to a human.

MUST-have differentiators:

1. Four independent Trust-Calibrated statuses instead of one fraud score.
2. Conflict Finder: the same claim stated differently in two documents, shown side by side with page and rule.
3. Cross-Institution Engine: ghost faculty, reused photos, reused document identifiers.
4. Rules as versioned data with a draft, approve and activate lifecycle and an impact preview.
5. Evidence-linked Case File and an append-only, hash-chained audit trail.

NOT in scope: replacing the AICTE portal; automatic decisions; machine-learning forgery classification; live government integrations (adapters exist, real connections are future work); email or SMS delivery (in-app notifications only); payments.

### 1.2 Non-negotiable principles

1. Decision support only. The administrative decision field exists but is always `pending` and no screen or endpoint changes it. The UI shows: Final decision: Pending (authorised AICTE official).
2. Findings are preliminary indicators with a stated rule, evidence and status.
3. Never collapse the four statuses. A valid signature does not mean compliant; consistent documents do not mean genuine; an unavailable source does not mean a failure.
4. Deterministic checks (dates, IDs, counts, hashes, areas, rules) run as plain Python, never in an LLM. An LLM may only draft text or summaries and its output is never active without human approval.
5. Every finding stores the rule code and version, evidence rows (document, page, value), status, and who acted on it and why.
6. Ambiguous or low-confidence extractions become `needs_confirmation` items for a human, never silently resolved.
7. Everything simulated is labelled MOCK; everything fictional is labelled SYNTHETIC or Fictional.
8. Nothing in the audit trail is deleted. Rule changes never rewrite history; each validation run records the rule versions it used.
9. Institutions never see other institutions' data. Cross-institution results are visible only to reviewers, with identifiers masked in list views.
10. No secret ever reaches the browser or the repository.

## 2. Stack and repository layout

**Frontend:** Next.js 14 (App Router), TypeScript strict, Tailwind CSS 3.4, `@supabase/supabase-js` 2, `@tanstack/react-query` 5, `pdfjs-dist` or `react-pdf` for the document viewer.

**Backend:** FastAPI on Python 3.11 with uvicorn, Pydantic v2, `supabase` (supabase-py, service role), `PyJWT`, `PyMuPDF`, `pytesseract` with `Pillow`, `imagehash`, `rapidfuzz`, `python-multipart`, `reportlab` (seed PDFs), `pytest`, `httpx`. Optional: the Anthropic SDK for summaries and explanations only.

**Platform:** Supabase Postgres (extensions `pgcrypto`, `pg_trgm`), Auth, Storage (private bucket `pp-files`), Realtime on `pp_notifications`.

```
proofpath/
  supabase/migrations/   0001_schema.sql, 0002_rls.sql, 0003_seed_reference.sql
  backend/
    app/main.py
    app/core/            config.py, security.py, db.py, audit.py, clock.py
    app/routers/         applications, documents, findings, reviews, cross, rules, casefile, admin, audit, notifications, demo
    app/services/        pipeline.py, extraction.py, normalise.py, validation.py, checks/, crossinst.py,
                         statuses.py, priority.py, rules_registry.py, authenticity.py, registry_adapter.py, casefile.py, llm.py
    app/schemas/
    tests/
    seed/                seed.py, make_documents.py, ground_truth.json
    scripts/evaluate.py
  frontend/
    app/                 welcome, login, institution/*, review/*, admin/*, audit
    components/          StatusCard, FindingCard, EvidenceViewer, SideBySide, PhotoPair, DocViewer, ScoreBreakdown, Banner
    lib/                 supabase.ts, api.ts, format.ts
  design/                screenshots supplied by the owner
  ASSUMPTIONS.md
  README.md
```

## 3. Environment and secrets

Never commit real values. Ship `.env.example` with these names and placeholder values.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | backend | Project URL |
| `SUPABASE_SERVICE_KEY` | backend only | Service-role key for privileged access |
| `SUPABASE_JWT_SECRET` | backend | Verifies user tokens (HS256). If verification fails, copy the secret from the Supabase dashboard under API settings |
| `DEMO_PASSWORD` | seed script | Password for seeded demo accounts |
| `NEXT_PUBLIC_SUPABASE_URL` | frontend | Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | frontend | Public anon key |
| `NEXT_PUBLIC_API_URL` | frontend | Backend base URL, for example `http://localhost:8000/api/v1` |
| `FRONTEND_ORIGIN` | backend | CORS allow-list |
| `MAX_UPLOAD_MB` | backend | Default 15 |
| `MAX_PAGES` | backend | Default 50 |
| `OCR_ENABLED` | backend | true when the Tesseract binary is installed |
| `AS_OF_DATE_MODE` | backend | `today` or `fixed` |
| `AS_OF_DATE` | backend | Used when mode is `fixed`, so demos are reproducible |
| `LLM_API_KEY` | backend, optional | Summaries and explanations only |

Backend verifies every request's bearer token with `SUPABASE_JWT_SECRET`, reads the user id from `sub`, then loads the role and institution from `pp_profiles` with the service client. All privileged writes happen in the backend. The browser talks to Supabase only for sign-in, signed uploads and Realtime on `pp_notifications`.

## 4. Roles and permissions

Three roles, stored in `pp_profiles`. Enforce in FastAPI with a `require_role` dependency and again with row-level security.

| Capability | institution\_user | scrutiny\_reviewer | rule\_admin |
| --- | --- | --- | --- |
| Create and edit own institution's draft applications, upload documents, enter room data | Yes, own institution only | No | No |
| Run pre-flight check on own application | Yes | No | No |
| Submit application | Yes | No | No |
| See own applications, documents, evidence requests | Yes | Yes, all | Read only |
| See findings | Only `evidence_requested` findings on own applications, never cross-institution types | Yes, all | Read only |
| Run validation; resolve, dismiss, request evidence; confirm or correct extracted values | No | Yes | No |
| See cross-institution flags | No | Yes | No |
| Upload replacement document for an evidence request | Yes | No | No |
| Save Case File snapshot | No | Yes | No |
| Create, edit, submit, approve, activate rules | No | No | Yes; the approver MUST differ from the author |
| Manage checklists, extraction templates, priority weights, adapters, trust store | No | No | Yes |
| Read audit log | Own application events only | Yes | Yes |

## 5. Database

Save as `supabase/migrations/0001_schema.sql`. Every table has `id uuid primary key default gen_random_uuid()` unless stated, and row-level security enabled (policies in `0002_rls.sql`, see 5.2).

```sql
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create type pp_role as enum ('institution_user','scrutiny_reviewer','rule_admin');

create table pp_institutions (
  id uuid primary key default gen_random_uuid(),
  code text unique not null, name text not null, city text,
  is_fictional boolean default true, created_at timestamptz default now()
);
create table pp_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null, role pp_role not null,
  institution_id uuid references pp_institutions(id)
);
create table pp_categories (code text primary key, label text not null);
create table pp_document_types (
  code text primary key, label text not null,
  has_expiry boolean default false, signature_required boolean default false, is_photo boolean default false
);
create table pp_required_documents (
  id uuid primary key default gen_random_uuid(),
  category text references pp_categories(code), doc_type text references pp_document_types(code),
  mandatory boolean default true, unique (category, doc_type)
);
create table pp_applications (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  institution_id uuid not null references pp_institutions(id),
  category text references pp_categories(code),
  academic_year text,
  workflow_status text default 'draft' check (workflow_status in ('draft','submitted','under_review','awaiting_institution','review_complete')),
  admin_status text default 'pending' check (admin_status = 'pending'),
  declared_total_area_sqm numeric,
  submitted_at timestamptz, review_deadline date,
  created_by uuid references pp_profiles(user_id), created_at timestamptz default now()
);
create table pp_documents (
  id uuid primary key default gen_random_uuid(),
  application_id uuid not null references pp_applications(id) on delete cascade,
  doc_type text references pp_document_types(code),
  version int default 1, supersedes_id uuid references pp_documents(id),
  status text default 'current' check (status in ('current','superseded')),
  storage_path text, original_name text, mime text, size_bytes bigint, page_count int,
  sha256 text, integrity_status text default 'pending' check (integrity_status in ('pending','passed','failed')),
  integrity_note text, processing_status text default 'pending' check (processing_status in ('pending','processing','done','error')),
  uploaded_by uuid references pp_profiles(user_id), uploaded_at timestamptz default now()
);
create table pp_extraction_templates (
  id uuid primary key default gen_random_uuid(),
  doc_type text references pp_document_types(code), field_name text not null,
  value_type text check (value_type in ('text','date','int','number')),
  regex text not null, group_index int default 1, required boolean default false,
  unique (doc_type, field_name)
);
create table pp_extracted_fields (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references pp_documents(id) on delete cascade,
  field_name text not null, field_value text, original_value text, value_type text,
  page_number int, bbox jsonb,
  source_method text check (source_method in ('PDF_TEXT','OCR','MANUAL')),
  confidence numeric,
  review_state text default 'auto' check (review_state in ('auto','needs_confirmation','confirmed','corrected')),
  reviewed_by uuid references pp_profiles(user_id), reviewed_at timestamptz
);
create table pp_faculty (
  id uuid primary key default gen_random_uuid(),
  faculty_code text, institution_id uuid references pp_institutions(id),
  application_id uuid references pp_applications(id) on delete cascade,
  document_id uuid references pp_documents(id) on delete cascade,
  name_raw text, name_norm text, designation text, qualification text,
  masked_id text, period_start date, period_end date
);
create index pp_faculty_name_trgm on pp_faculty using gin (name_norm gin_trgm_ops);
create table pp_media_assets (
  id uuid primary key default gen_random_uuid(),
  document_id uuid unique references pp_documents(id) on delete cascade,
  category text,  -- lab | classroom | library | floor_plan | other
  phash text,     -- 16 hex characters = 64 bits
  width int, height int, exif jsonb, taken_at timestamptz, gps jsonb
);
create table pp_rooms (
  id uuid primary key default gen_random_uuid(),
  application_id uuid references pp_applications(id) on delete cascade,
  floor_plan_document_id uuid references pp_documents(id),
  room_label text, length_m numeric, width_m numeric,
  area_sqm numeric generated always as (length_m * width_m) stored
);
create table pp_rules (
  id uuid primary key default gen_random_uuid(),
  rule_code text not null, version int not null default 1,
  title text, description text, check_type text not null, params jsonb default '{}',
  categories text[], source_reference text, clause text,
  severity text, requires_human_review boolean default true,
  status text default 'draft' check (status in ('draft','pending_approval','active','retired')),
  effective_from date, effective_to date,
  created_by uuid references pp_profiles(user_id), approved_by uuid references pp_profiles(user_id), approved_at timestamptz,
  note text default 'Illustrative demo rule, not an official AICTE rule',
  unique (rule_code, version)
);
create table pp_comparison_pairs (
  id uuid primary key default gen_random_uuid(),
  pair_code text unique, rule_code text, finding_type text,
  doc_type_a text, field_a text, doc_type_b text, field_b text, label text
);
create table pp_validation_runs (
  id uuid primary key default gen_random_uuid(),
  application_id uuid references pp_applications(id) on delete cascade,
  mode text check (mode in ('full','preflight','dry_run')),
  as_of_date date, rule_versions jsonb, started_by uuid, started_at timestamptz default now(),
  finished_at timestamptz, summary jsonb
);
create table pp_findings (
  id uuid primary key default gen_random_uuid(),
  finding_key text unique not null,
  application_id uuid not null references pp_applications(id) on delete cascade,
  related_application_id uuid references pp_applications(id),
  finding_type text not null, rule_code text, rule_version int,
  severity text check (severity in ('info','low','medium','high')),
  title text, detail text,
  status text default 'open' check (status in ('open','evidence_requested','resolved','dismissed','auto_closed')),
  is_cross_institution boolean default false,
  first_run_id uuid, last_run_id uuid, created_at timestamptz default now()
);
create table pp_finding_evidence (
  id uuid primary key default gen_random_uuid(),
  finding_id uuid not null references pp_findings(id) on delete cascade,
  document_id uuid references pp_documents(id), page_number int,
  role text check (role in ('A','B','SINGLE')), label text, shown_value text, bbox jsonb
);
create table pp_review_actions (
  id uuid primary key default gen_random_uuid(),
  finding_id uuid references pp_findings(id) on delete cascade,
  actor_id uuid references pp_profiles(user_id), actor_role text,
  action text check (action in ('resolve','dismiss','request_evidence','confirm_field','correct_field')),
  reason text not null, created_at timestamptz default now()
);
create table pp_evidence_requests (
  id uuid primary key default gen_random_uuid(),
  finding_id uuid references pp_findings(id), application_id uuid references pp_applications(id),
  requested_by uuid, message text, due_date date,
  status text default 'open' check (status in ('open','fulfilled','cancelled')),
  fulfilled_by_document_id uuid references pp_documents(id), created_at timestamptz default now()
);
create table pp_verification_checks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references pp_documents(id) on delete cascade,
  method text check (method in ('HASH','SIGNATURE','REGISTRY','METADATA','MANUAL')),
  source text, status text, is_mock boolean default false, response jsonb,
  checked_by uuid, checked_at timestamptz default now()
);
create table pp_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references pp_profiles(user_id), kind text, ref_type text, ref_id text,
  message text, read_at timestamptz, created_at timestamptz default now()
);
create table pp_case_file_snapshots (
  id uuid primary key default gen_random_uuid(),
  application_id uuid references pp_applications(id), generated_by uuid,
  payload jsonb, created_at timestamptz default now()
);
create table pp_priority_weights (key text primary key, weight int not null);
create table pp_settings (key text primary key, value jsonb not null);

create table pp_audit_events (
  id bigint generated always as identity primary key,
  actor_id uuid, actor_role text, event_type text not null,
  entity_type text, entity_id text, application_id uuid, detail jsonb,
  created_at timestamptz not null, prev_hash text not null, event_hash text not null
);
create function pp_audit_block() returns trigger language plpgsql as $$
begin raise exception 'pp_audit_events is append-only'; end; $$;
create trigger pp_audit_no_change before update or delete on pp_audit_events
  for each row execute function pp_audit_block();

create function pp_audit_append(p_actor uuid, p_role text, p_type text, p_entity_type text,
  p_entity_id text, p_app uuid, p_detail jsonb) returns bigint
language plpgsql security definer as $$
declare v_prev text; v_ts timestamptz := clock_timestamp(); v_hash text; v_id bigint;
begin
  perform pg_advisory_xact_lock(7311);
  select event_hash into v_prev from pp_audit_events order by id desc limit 1;
  v_prev := coalesce(v_prev, 'GENESIS');
  v_hash := encode(digest(v_prev || '|' || coalesce(p_actor::text,'') || '|' || coalesce(p_role,'') || '|' || p_type || '|' ||
    coalesce(p_entity_type,'') || '|' || coalesce(p_entity_id,'') || '|' || coalesce(p_app::text,'') || '|' ||
    coalesce(p_detail::text,'') || '|' || to_char(v_ts at time zone 'utc','YYYY-MM-DD"T"HH24:MI:SS.US'), 'sha256'), 'hex');
  insert into pp_audit_events (actor_id, actor_role, event_type, entity_type, entity_id, application_id, detail, created_at, prev_hash, event_hash)
  values (p_actor, p_role, p_type, p_entity_type, p_entity_id, p_app, p_detail, v_ts, v_prev, v_hash) returning id into v_id;
  return v_id;
end; $$;
```

The verifier in `GET /audit/verify` recomputes each hash in order with the same formula and returns the first broken row, if any.

### 5.1 Reference data (`0003_seed_reference.sql`)

Seed categories (for example `new_institution`, `extension_of_approval`), document types (`application_form`, `approval_certificate`, `land_document`, `fire_noc`, `faculty_list`, `affidavit`, `infrastructure_photo`, `floor_plan`), required documents per category, extraction templates, comparison pairs, rules (section 9) and default priority weights (section 7.4). All seeded rules carry the note Illustrative demo rule, not an official AICTE rule.

### 5.2 Row-level security

Create helper SQL functions `pp_role()` and `pp_institution()` reading `pp_profiles` for `auth.uid()`. Policies: an institution user reads and writes only rows tied to their institution's applications; reviewers read everything and write nothing directly; rule admins read everything. Findings of cross-institution type (`is_cross_institution`) are never readable by institution users. No browser role may write to `pp_findings`, `pp_review_actions`, `pp_rules`, `pp_audit_events` or `pp_verification_checks`. The service role bypasses RLS, so the backend MUST do its own checks. Add tests that an institution user cannot read another institution's rows.

## 6. Upload and extraction pipeline

Follow this order. Files are analysed on the backend, so documents never need a browser-side OCR.

1. `POST /applications/{id}/documents/init` with `doc_type`, filename, mime and size. The backend validates extension (PDF, JPEG, PNG), mime and size (`MAX_UPLOAD_MB`), creates a `pp_documents` row (`processing_status = pending`), and returns a signed upload URL for `pp-files` at `{institution_id}/{application_id}/{document_id}-{safe_filename}`.
2. The browser uploads the file straight to that URL.
3. `POST /documents/{id}/finalize`. The backend downloads the file and: checks magic bytes against the claimed type, enforces `MAX_PAGES`, computes SHA-256 into `sha256`, sets `integrity_status` to `passed` or `failed` with a note, writes an audit event, and starts processing in a background task. A failed document is excluded from validation and the uploader sees a clear error.
4. **Text:** for PDFs, PyMuPDF extracts text per page. For a page with fewer than 20 characters and `OCR_ENABLED`, render it at 200 dpi and run Tesseract; store the average word confidence (0 to 1) for OCR, and null for PDF text. For images, run Tesseract directly.
5. **Fields:** apply `pp_extraction_templates` (regex per document type) to each page's text. Store value, page, source method and confidence in `pp_extracted_fields`. A required field with no match, or OCR confidence below the rule threshold (default 0.80), or an ambiguous date, is stored with `review_state = needs_confirmation`.
6. **Photos:** compute a 64-bit perceptual hash (`imagehash.phash`, hash size 8, stored as 16 hex characters), width, height, and EXIF (timestamp, GPS if present) into `pp_media_assets`. The uploader chooses the evidence category.
7. **Faculty lists:** parse one faculty member per line into `pp_faculty` (name, designation, qualification, masked ID, period) using a documented line format, normalise the name, and keep `name_raw`.
8. **Versions:** uploading the same `doc_type` for an application that already has a current document creates version + 1, links `supersedes_id`, and marks the old one `superseded`.
9. Set `processing_status` to `done` or `error`. The frontend polls `GET /documents/{id}`.

**Normalisation (`normalise.py`, unit-tested).** Names: lowercase, remove titles (dr, prof, mr, ms, mrs), remove dots and commas, collapse spaces. Dates: ISO `YYYY-MM-DD`; textual months are unambiguous; a numeric date such as 03/08/2027 where both parts are 12 or less and differ is stored as ambiguous and goes to `needs_confirmation`. Numbers: strip separators and units.

## 7. Validation engine

`POST /applications/{id}/validate` runs `run_validation(application_id, mode)` in `services/validation.py`. Modes: `full` (reviewer, writes findings), `preflight` (institution, returns a list, writes nothing), `dry_run` (rule admin impact preview, writes nothing).

### 7.1 Run steps

1. Create a `pp_validation_runs` row with the as-of date (from settings: today or a fixed date) and the active rule versions it will use.
2. Run each check below in order. Each check yields findings with a stable `finding_key` of the form `TYPE|application_code|discriminator`, written with insert-or-ignore so reviewer actions survive re-runs.
3. Auto-close: open findings from earlier runs whose condition no longer holds become `auto_closed` with an audit event. Findings whose only evidence was a superseded document are re-evaluated against the new one.
4. Compute the four statuses and the priority score. Write an audit event for the run.

### 7.2 Check catalogue

| ID | Finding type | Logic | Severity |
| --- | --- | --- | --- |
| C1 | MISSING\_DOCUMENT | Required documents for the category minus current, integrity-passed documents of that type | high |
| C2 | EXPIRED\_DOCUMENT | Extracted `expiry_date` earlier than the as-of date | high |
| C3 | DATE\_ORDER\_INVALID | `expiry_date` earlier than `issue_date` in the same document | medium |
| C4 | DATE\_CONFLICT, ID\_MISMATCH, COUNT\_CONFLICT | Driven by `pp_comparison_pairs`: same application, two documents, values differ after normalisation | medium |
| C5 | FIELD\_NEEDS\_CONFIRMATION | Required field low-confidence, ambiguous or not found | low (routes to reviewer) |
| C6 | DUPLICATE\_FILE | Two current documents in one application with the same `sha256` | low |
| C7 | REUSED\_IDENTIFIER | Same certificate or reference number in an application of another institution | medium, cross-institution |
| C8 | GHOST\_FACULTY | Section 8 | medium, cross-institution |
| C9 | PHOTO\_REUSE | Section 8 | medium, cross-institution |
| C10 | INFRA\_EVIDENCE\_MISSING | Required evidence categories (lab, classroom, library, floor plan) not all present | high |
| C11 | AREA\_MISMATCH, AREA\_BELOW\_MINIMUM | Sum of room areas against declared total area (tolerance `area_tolerance_pct`, default 1) and against `min_area_sqm` | medium, high |
| C12 | PHOTO\_METADATA | EXIF date older than `max_photo_age_months`; missing EXIF is an info note unless the rule requires it | low |
| C13 | SIGNATURE\_INVALID | Latest SIGNATURE check is invalid or untrusted\_chain; unsigned is a finding only when the document type has `signature_required` | high, medium |
| C14 | METADATA\_ANOMALY | PDF modified after its recorded signing time, or creation date later than modification date | low (indicator only) |
| C15 | REGISTRY\_MISMATCH | Registry check returned fields that differ from the extracted fields | high |

A finding's title and detail MUST say what differs and where, never what it implies. Example: Declared faculty count 24 differs from faculty list total 22 (page 2), candidate for review.

### 7.3 The four statuses (`services/statuses.py`)

Only findings with status `open` or `evidence_requested` are unresolved. Before the first full run all four read Not run yet. Worst state wins, in the order listed.

| Status | Values, worst first |
| --- | --- |
| Integrity | File check failed, Duplicate file detected, Passed |
| Consistency | Conflict detected (C4 findings), Cross-application flag (C7 to C9), Inconclusive (any field `needs_confirmation`), Consistent |
| Authenticity | Signature invalid or Source mismatch, Manual verification pending, Pending (source unavailable), Signature valid or Source verified, Not yet verified |
| Compliance | Review required (missing, expired, area or evidence findings), Not assessable (a mandatory field could not be extracted), Meets configured checks |

Administrative status is separate and always shows Pending (authorised AICTE official). Expose statuses from `GET /applications/{id}/statuses`.

### 7.4 Review priority (`services/priority.py`)

`priority_score = min(100, sum of weights of unresolved findings + 5 per additional unresolved finding beyond the first + deadline bonus)`. Default weights in `pp_priority_weights`: missing document 30, expired document 25, infrastructure evidence missing 25, cross-institution flag 25, conflict 20, area finding 20, signature or registry problem 30, needs confirmation 10, duplicate 10, metadata 5. Deadline bonus: +20 if the review deadline is within 7 days, +10 if within 14 days. Bands: High 60 and above, Medium 30 to 59, Low below 30. The score only orders the queue and never changes a status. The API returns the composition (each term and its contribution) and the UI MUST show it.

## 8. Cross-Institution Engine

Implemented in `services/crossinst.py`, run as part of a full validation. Reviewers only; institution users never receive these results.

- **Ghost faculty (C8).** For each `pp_faculty` row of the application, find rows at a different institution where (`masked_id` is equal) OR (RapidFuzz token-sort ratio of `name_norm` is at or above `params.similarity` times 100, default 0.7, AND the qualification is identical), AND the employment periods overlap (an empty end date means ongoing). Create one finding per pair with key `GHOST_FACULTY|app|other_app|faculty_code`. Text MUST say candidate for review, not proof. Evidence: both rows with their documents.
- **Photo reuse (C9).** Hamming distance between 64-bit perceptual hashes at or below `params.max_hamming` (default 8) between a photo of this application and a photo of another institution. One finding per other application, showing both photos side by side and the distance. A re-encoded or resized copy MUST still match.
- **Reused identifiers (C7).** The same certificate or reference number extracted in an application of another institution.
- **Privacy.** Reviewers see names on the case page; list views show masked IDs only. `GET /cross` lists all open cross-institution flags with both applications.

## 9. Rules registry

Rules are data in `pp_rules`, executed by deterministic code. `check_type` is one of `required_document`, `expiry`, `date_order`, `pair_compare`, `duplicate_file`, `reused_identifier`, `ghost_faculty`, `photo_reuse`, `infra_evidence`, `area_check`, `photo_metadata`, `signature_required`, `metadata_check`. Thresholds live in `params`.

Seed these illustrative rules (all with the note Illustrative demo rule, not an official AICTE rule):

| Rule code | Check type | Params | Severity |
| --- | --- | --- | --- |
| R-DOC-REQ | required\_document | per category in `pp_required_documents` | high |
| R-EXP-01 | expiry | applies to document types with `has_expiry` | high |
| R-DATE-01 | date\_order | none | medium |
| R-PAIR-01 | pair\_compare | uses `pp_comparison_pairs` | medium |
| R-DUP-01 | duplicate\_file | none | low |
| R-ID-REUSE | reused\_identifier | none | medium |
| R-GHOST-01 | ghost\_faculty | similarity 0.7 | medium |
| R-PHOTO-01 | photo\_reuse | max\_hamming 8 | medium |
| R-INFRA-01 | infra\_evidence | required lab, classroom, library, floor\_plan | high |
| R-AREA-01 | area\_check | area\_tolerance\_pct 1, min\_area\_sqm 4000 | medium, high |
| R-PHOTOAGE-01 | photo\_metadata | max\_photo\_age\_months 12 | low |
| R-SIG-01 | signature\_required | document types flagged in `pp_document_types` | medium |
| R-META-01 | metadata\_check | none | low |
| R-OCR-01 | extraction | min\_confidence 0.80 | low |

**Lifecycle.** `draft` (author edits) to `pending_approval` (author submits) to `active` (a different rule\_admin approves; reject the request if approver equals author) to `retired`. The function `rule_ver(code, as_of)` returns the active version valid on the as-of date.

**Impact preview.** `run_validation(application_id, mode='dry_run')` evaluates a draft rule against existing applications and returns the findings that would be created or closed, without writing findings. The Rules screen shows counts per affected application.

**History.** `pp_validation_runs.rule_versions` records the exact versions used. Changing or retiring a rule never edits past findings.

**Optional drafting.** `POST /rules/draft-from-text` sends pasted regulation text to the LLM and saves a structured draft with the source clause cited. It saves as `draft` only and is never active until approved.

## 10. Authenticity layer

Each method writes its own `pp_verification_checks` row and never overrides another.

| Method | Behaviour | Phase |
| --- | --- | --- |
| HASH | Internal integrity and duplicate check | 1 |
| MANUAL | Reviewer records a confirmation with the issuer (contact note, optional attachment); status `manual_pending` or `manual_confirmed` | 4 |
| REGISTRY | `services/registry_adapter.py` calls the enabled adapter. The MOCK adapter returns `unavailable` by default and can be set in settings to return a matching or mismatching record for demos; always `is_mock = true` and labelled MOCK in the UI. A real adapter (for example DigiLocker or API Setu) is future work needing authorisation | 4 |
| SIGNATURE | Verify an embedded PDF signature against certificates in a trust store (use `pyHanko`); results `valid`, `invalid`, `untrusted_chain`, `unsigned`, `unsupported` | 5 |
| METADATA | PDF metadata indicators (C14): modified after signing time, creation later than modification, multiple incremental updates | 5 |

Rules: an unavailable source is Pending, never a failure; unsupported is not invalid; unsigned is a finding only when the document type requires a signature; forensic output is an indicator shown with its evidence.

## 11. API

Base path `/api/v1`. Every route except `GET /demo/accounts` needs a valid bearer token and a role check. Write an audit event for every mutation by calling `pp_audit_append`.

| Method and path | Roles | Purpose |
| --- | --- | --- |
| `GET /demo/accounts` | public | Demo account cards for the welcome page |
| `GET /me` | any | Profile and role |
| `POST /applications`, `GET /applications`, `GET /applications/{id}` | institution (own), reviewer, admin read | Create, list, detail |
| `POST /applications/{id}/submit` | institution | Submit; notifies reviewers |
| `POST /applications/{id}/documents/init` | institution | Validate metadata, return signed upload URL |
| `POST /documents/{id}/finalize` | institution | Hash, check, extract |
| `GET /documents/{id}`, `GET /documents/{id}/signed-url` | scoped | Status and short-lived viewing URL |
| `GET /documents/{id}/fields`, `POST /fields/{id}/confirm`, `POST /fields/{id}/correct` | reviewer | Extracted values; keep the original on correction |
| `POST /applications/{id}/rooms`, `GET /applications/{id}/rooms` | institution, reviewer | Room table for floor-plan arithmetic |
| `POST /applications/{id}/preflight` | institution | Pre-flight list; no cross-institution results, nothing stored |
| `POST /applications/{id}/validate` | reviewer | Full run |
| `GET /applications/{id}/statuses`, `GET /applications/{id}/priority` | reviewer | Four statuses, score composition |
| `GET /applications/{id}/findings`, `GET /findings/{id}` | reviewer, institution (own, limited) | Findings with evidence |
| `POST /findings/{id}/actions` | reviewer | resolve, dismiss, request\_evidence; reason required |
| `GET /evidence-requests`, `POST /evidence-requests/{id}/fulfil` | institution | Open requests and replacement upload |
| `POST /documents/{id}/verify/registry`, `POST /documents/{id}/verify/manual` | reviewer | Authenticity checks |
| `GET /queue` | reviewer | Priority queue with filters |
| `GET /cross` | reviewer | Cross-institution flags |
| `GET /applications/{id}/casefile`, `POST /applications/{id}/casefile/snapshot` | reviewer | Case File data and snapshot |
| `GET /rules`, `POST /rules`, `PUT /rules/{id}`, `POST /rules/{id}/submit`, `/approve`, `/activate`, `/retire`, `GET /rules/{id}/impact` | rule\_admin | Lifecycle and preview |
| `GET and PUT /admin/settings` | rule\_admin | Checklists, templates, weights, adapters, trust store, as-of mode |
| `GET /notifications`, `POST /notifications/{id}/read` | self | In-app notifications |
| `GET /audit`, `GET /audit/verify` | reviewer, rule\_admin | Log and hash-chain check |
| `POST /admin/seed`, `POST /admin/demo/tamper` | rule\_admin | Reseed; red-team demo (section 16) |

## 12. Screens

| Route | Role | Requirements |
| --- | --- | --- |
| `/welcome` | public | One-line purpose, the MOCK and fictional notice, one-click demo login cards per role, a 2-minute guided path with links |
| `/login` | all | Email and password sign-in, redirect by role |
| `/institution` | institution\_user | Own applications with workflow status, open evidence requests with due dates, notifications |
| `/institution/applications/new` | institution\_user | Wizard: details, upload documents by type with live extraction preview and errors, infrastructure evidence and room table, pre-flight results with fix links, submit |
| `/institution/applications/[id]` | institution\_user | Documents list, requests, replace a document (new version), fulfil a request |
| `/review` | scrutiny\_reviewer | Priority queue (score, band, composition), filters by status, institution and finding type, notification bell |
| `/review/[id]` | scrutiny\_reviewer | Case page (below) |
| `/review/[id]/casefile` | scrutiny\_reviewer | Print-friendly Case File and Save snapshot |
| `/review/cross` | scrutiny\_reviewer | All open cross-institution flags with both applications and masked IDs |
| `/admin/rules` | rule\_admin | Rule list with versions, editor, submit, approve (not own), activate, retire, impact preview, optional draft from text |
| `/admin/settings` | rule\_admin | Checklists, document types, extraction templates, priority weights, registry adapter mode, trust store, as-of date mode |
| `/audit` | reviewer, rule\_admin | Searchable log with a hash-chain verified indicator |

**Case page.** Four status cards; Run validation; findings in two groups (Within this application, Across institutions); an evidence viewer with side-by-side values, two photos side by side, and the document opened at the cited page; actions with a required reason; extracted-field table with confirm or correct (original kept); documents table with verification state and Check issuer registry (MOCK); evidence requests; audit trail; rule versions used; priority composition.

**Case File content (MUST).** Application summary; four statuses; findings with rule code, version, evidence and status; documents with verification results; reviewer actions with reasons; rule versions of the latest run; the line Final decision: Pending (authorised AICTE official); and both disclaimers in section 13.

## 13. UI and design constraints

- The owner supplies screenshots in `/design`. Extract colours, fonts, radii, shadows and spacing into `tailwind.config.js` and `globals.css`, and use only those tokens. No hard-coded hex values in components, no default Tailwind palette classes, and no extra gradients, icons or fonts the screenshots do not show. Until the screenshots arrive, use neutral placeholder tokens that are trivial to replace.
- Status meaning MUST never rely on colour alone; always show text.
- A banner on every page: Prototype demo. All institutions, people, documents and photos are fictional. Rules are illustrative, not official AICTE rules.
- Case File closing text: Decision support only. This report does not approve, reject or declare any institution at fault. The final decision rests with the competent authority. And: All data in this report is synthetic. Rules shown are illustrative, not official AICTE rules. The issuer-registry check is a MOCK.
- Every list has loading, empty and error states. Every write button is disabled while pending. Dates are shown in DD/MM/YYYY.
- Judge experience: `/welcome` explains the product, offers one-click role entry, and shows a short guided path; every screen has a one-line description and a Help drawer with a glossary (claim, conflict, status, rule version, pre-flight).

## 14. Seed data and evaluation

A deterministic script (`seed/seed.py`, fixed random seed) creates fictional institutions (include Aarohan Institute of Technology), about 30 applications, generated PDFs (ReportLab) and photos (Pillow, synthetic images), plus `ground_truth.json`: the exact finding keys that MUST appear, lookalike cases that MUST NOT be flagged, and one clean control application. Demo accounts: `institution@proofpath.demo`, `reviewer@proofpath.demo`, `ruleadmin@proofpath.demo`, with the password from `DEMO_PASSWORD`.

| Scenario | What is seeded | Expected |
| --- | --- | --- |
| Date conflict | Declared certificate validity in the form differs from the certificate's expiry | DATE\_CONFLICT with both pages |
| Count conflict | Form declares 24 faculty; faculty list totals 22 | COUNT\_CONFLICT |
| ID mismatch | Institution code differs between form and certificate | ID\_MISMATCH |
| Missing document | Fire NOC absent | MISSING\_DOCUMENT |
| Expired document | Certificate expiry before the as-of date | EXPIRED\_DOCUMENT |
| Duplicate file | Same file uploaded as two document types | DUPLICATE\_FILE |
| Ghost faculty | Same person, name variant, at two institutions with overlapping periods | GHOST\_FACULTY |
| Look-alike | Similar name, different qualification, different institution | Not flagged |
| Photo reuse | Lab photo re-encoded and resized, used at another institution | PHOTO\_REUSE |
| Area mismatch | Room areas sum to less than declared area beyond tolerance | AREA\_MISMATCH |
| Stale photo | EXIF date older than 12 months | PHOTO\_METADATA |
| Low confidence date | A scanned certificate with an ambiguous date | FIELD\_NEEDS\_CONFIRMATION |
| Clean control | An application with no issues | No findings |

`scripts/evaluate.py` runs full validation on every seeded application through the REST API, compares findings with ground truth, and prints TP, FP, FN, precision, recall, F1 and the must-not-flag results. Its output begins: Measured on a synthetic dataset; not validated on real AICTE records.

## 15. Build phases, prompts and acceptance

Commit after every phase. Start each session by pasting the relevant section. Build in this order.

| Phase | Prompt to give | Done when |
| --- | --- | --- |
| 0 Setup | Create the repo layout from section 2, a Next.js app, a FastAPI app with `/health`, `.env.example`, `.gitignore` covering `.env`, README and `ASSUMPTIONS.md`. No features yet. | Both apps run locally and no secret is tracked by git |
| 1 Foundation | Migrations from section 5, RLS, Auth and roles, reference seed, upload pipeline from section 6, document viewer with signed URLs, welcome and login pages. | Each demo role signs in; an institution uploads a PDF and a photo; the reviewer opens them; RLS blocks cross-institution access (tested) |
| 2 Core validation | Validation engine with C1 to C6, statuses, priority, case page, actions with reasons, audit with hash chain, Case File. | Seeded within-application scenarios produce exactly the expected findings; resolve, dismiss and request evidence work and appear in the audit |
| 3 Differentiators | C7 to C9, cross-institution overview, rooms and C10 to C12, needs-confirmation flow, priority queue, notifications, evidence requests, document versions with auto-close. | Ground truth passes with zero false positives and zero false negatives; look-alike and clean control are not flagged |
| 4 Authenticity | MANUAL and REGISTRY (mock) checks, authenticity status, pre-flight wizard. | Each method shows its own state; an unavailable source shows Pending, never failure |
| 5 Governance | Rules lifecycle, four-eyes approval, impact preview, settings screens, signature and metadata checks, optional draft-from-text. | A rule change shows impact, needs a second approver, and old runs keep their rule versions |
| 6 Hardening | Empty and error states, accessibility pass, forbidden-words test, hard-coded-colour test, evaluation run, README with a 15-minute setup, demo path. | Evaluation output saved; full demo path works end to end |
| 7 Wild (optional) | Pick items from section 16 once the owner has chosen. | Each chosen item works on seeded data |

## 16. Wild ideas backlog (the owner decides what is feasible)

Do not build these until asked. Each lists how it could be done, so feasibility can be judged quickly. Effort: S under half a day, M about a day, L more.

| Idea | How it could work | Effort |
| --- | --- | --- |
| Evidence heatmap | PyMuPDF gives word coordinates; store `bbox` with each field and draw an overlay on the PDF page at the cited value | M |
| Explain this finding | LLM receives only the finding, rule text and evidence rows and writes two plain sentences; shown as Draft explanation, never as a conclusion | S |
| Template fingerprinting | Hash the set of fonts and the layout grid per document type; cluster institutions with unusually similar fingerprints and flag as candidates for review | M |
| Copy-move detection | OpenCV ORB feature matching to find a stamp or signature image reused within or across documents | L |
| PDF structure forensics | Count incremental updates and compare producer, creator and modification dates; show as indicators | S |
| Location sanity check | Compare photo GPS to the declared campus coordinates with a haversine distance | S |
| Shared-identity links | Normalise survey numbers, addresses and phone numbers and match across institutions | M |
| Arithmetic sanity checks | Faculty-student ratio and built-up area against declared figures, as rules | S |
| Document version diff | `difflib` over page text between versions, shown as added and removed lines | S |
| Missing-evidence reasoning | For each category list what a complete file contains and what is absent | S |
| Red-team demo button | `POST /admin/demo/tamper` creates a tampered copy of a seeded document and re-runs validation live | M |
| Hindi OCR and bilingual UI | Tesseract Hindi data plus `next-intl` | M |
| Reviewer time estimate | Log time on case page, compare with a manual baseline on the seeded set | S |
| Institution history timeline | A plain timeline of past findings per institution, never a score | S |
| Voice reasons | Browser or API speech-to-text fills the action reason; reviewer edits before saving | M |

## 17. Tests and definition of done

**Required tests:** one passing and one failing case for every check C1 to C15; unit tests for name and date normalisation and the perceptual hash (including a re-encoded copy); an audit test that update and delete are rejected and that `GET /audit/verify` detects a tampered row; RLS tests for every role; a test that an administrative decision can never be set; the forbidden-words search; the hard-coded-colour search; and the evaluation script.

**Security checklist:** private bucket and short-lived signed URLs only; magic-byte, size and page limits enforced server-side; the service-role key only in the backend environment; secrets never logged; rate limiting on login and upload endpoints; CORS limited to `FRONTEND_ORIGIN`; inputs validated with Pydantic; reviewer-only endpoints reject institution tokens.

**Definition of done:** all phases through 6 meet their criteria; the evaluation prints its numbers on the synthetic dataset; every page shows the banner; the four statuses are independent in the UI and in the API; no screen or endpoint can set an administrative decision; no secret is in the repository; and a new developer can run the project from the README in under 15 minutes.
