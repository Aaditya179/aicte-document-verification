# ProofPath AI

Smart India Hackathon problem statement **SIH26261**. ProofPath AI is an evidence-first validation layer beside the AICTE approval workflow. It reads every document of an application, checks the claims against versioned rules and against each other, compares claims across institutions (the same faculty member, photo, certificate number or land survey number in more than one application), and gives the reviewer a case file in which every finding links to its document, page and value.

Every finding is decision support only. Reviewers resolve, dismiss or request evidence with a reason; the administrative decision always reads "Pending (authorised AICTE official)" and nothing can change it.

This file holds every project document except `README.md` (setup and demo for readers) and `PROJECT_REPORT.md` (the report for judges):

- **Part 1:** working notes (this part): status, roles, running, conventions and the design tokens.
- **Part 2:** assumptions and deviations from the build spec (formerly `ASSUMPTIONS.md`).
- **Part 3:** the build spec (formerly `ProofPath AI Build Spec for Claude Code.md`).

## Build spec and plan

- **The build spec (Part 3 of this file) is the source of truth.** Section 1.2 (principles) wins over everything, then sections 6 to 10 (logic).
- **Assumptions and deviations (Part 2 of this file) record every deviation from the spec** (mainly: `proofpath` schema instead of `pp_` tables, roles `institution`/`reviewer`/`rule_admin`, no browser table access, Next 16 and Tailwind 4, Groq only). Read it before building; add to it when choosing anything the spec leaves open.
- **Build one phase at a time (spec section 15) and stop after each one.** Report what was done and how it was verified, then wait. The user verifies and pushes, and says when to start the next phase.

## Sister project: Nirikshan

ProofPath was started on 2026-10-28 from **Nirikshan** (SIH26262, AICTE approval workflow and SLA monitoring) at `~/Desktop/projects/aicte-workflow` (GitHub `Aaditya179/aicte-workflow`). The two share **one Supabase project**; since phase 1 ProofPath has its own look. ProofPath's own repository is GitHub `Aaditya179/aicte-document-verification`. Look at Nirikshan's code when you need a reference implementation, for example OCR of documents, document field matching across units and spellings (`backend/services/doc_fields.py`), document upload and storage, and the copilot's number guard.

### Rules for the shared Supabase project (do not break)
- **All ProofPath tables are in the `proofpath` schema.** Never create ProofPath tables in `public`, which is Nirikshan's. Backend code goes through `core/db.py`, whose `db.table()` is bound to `settings.SUPABASE_SCHEMA`.
- Only the `service_role` has grants on `proofpath`; RLS is on with no policies. The browser never queries Supabase tables directly. It uses Supabase only for sign-in and MFA, and everything else goes through the API.
- **`auth.users` is shared.** A ProofPath role comes only from `proofpath.members` (`core/security.py`). Never read the role from `app_metadata`, which holds the Nirikshan role. ProofPath accounts must not set an `app_metadata.role`, so they get no Nirikshan access.
- Demo accounts are `@proofpath.demo` only. `seed/demo.py` refuses to touch any other email. Never modify or delete `@demo.sih` (Nirikshan) accounts.
- Documents go in the private bucket `proofpath-documents`, never Nirikshan's `documents`.
- **There is no direct database connection string.** Migrations go in `supabase/migrations/` and the user applies them in the Supabase SQL editor. A new schema also has to be listed under Project Settings → Data API → Exposed schemas.
- The database is live and shared with Nirikshan's deployed demo. Make no destructive changes without asking, and show the scope (a dry run) before any bulk delete.

## Status

**Phases 0 to 6 completed on 28/10/2026.** All criteria met; live evaluation yields 100% precision, recall, and F1 (22 TP, 0 FP, 0 FN); forbidden words and color tests pass; all 148 backend tests pass; Next.js builds cleanly with 18 routes.

Phase 1 built:
- Migrations `0001_proofpath_schema.sql` (spec tables in the `proofpath` schema, audit functions `audit_append`, `audit_verify`, `rule_ver`), `0002_rls.sql` (lockdown), `0003_seed_reference.sql` (categories, document types, checklists, extraction templates, comparison pairs, the 14 illustrative rules, priority weights). Applied on 28/10/2026; `proofpath` is an exposed schema.
- Backend: `core/access.py` (another institution's application reads as 404), `services/pipeline.py` (signed upload, file check, versions, background reading), `services/extraction.py`, `services/normalise.py`, `services/audit.py`. Routes: applications, documents, `/reference`, `/demo/accounts`, `/rules` (read-only), `/audit/verify`.
- Frontend: welcome, login, MFA, `/institution`, `/institution/applications/[id]`, `/review`, `/review/[id]`, `/admin/rules` (read-only).
- Seed: `seed/demo.py` (5 accounts), `seed/samples.py`.

Phase 2 built:
- `services/validation.py` (checks C1 to C6, modes full, preflight and dry_run, stable finding keys, auto-close), `statuses.py` (the four statuses), `priority.py` (score with its composition), `reviews.py` (resolve, dismiss, request evidence, each with a reason), `casefile.py`. Routes in `routers/findings.py`: validate, statuses, priority, findings, actions, Case File and snapshots, `/audit`.
- Frontend: the case page `/review/[id]` (status cards, Run validation, findings within and across institutions with A and B side by side, cited page viewer, priority ledger, actions, audit trail with chain check) and the printable `/review/[id]/casefile` with Save snapshot. Components in `components/findings.tsx`.
- Seed: `seed/seed.py` (16 institutions, 30 applications, 8 scenarios, `ground_truth.json`, as-of 01/11/2026), ran live. `scripts/evaluate.py` gave 8 true positives, 0 false positives, 0 false negatives.
- Speed: `core/db.py` keeps one pooled HTTP/1.1 PostgREST client (`client.schema()` used to open a new connection per query) and `parallel()` runs independent queries at once; sign-ins are cached for 30 seconds; route handlers are plain `def`. One Supabase round trip is about 0.2s, so keep sequential queries few.
- Tests: `tests/test_validation.py`, `tests/test_review_flow.py` (71 tests in all).

Phase 3 built:
- `services/crossinst.py` (C7 reused identifiers, C8 faculty listed elsewhere, C9 photo reuse; reviewers only, drafts and the same institution excluded) and C10 to C12 in `validation.py`. R-GHOST-01 version 2 (similarity 0.9, `0004_phase3.sql`, ASSUMPTIONS A20).
- `routers/workflow.py`: room table, `POST /fields/{id}/confirm` and `/correct` (original kept, validation reruns), evidence requests and `/fulfil`, notifications. `GET /queue` and `GET /cross` in `routers/findings.py`. A document read into a validated application starts a system run (`pipeline.revalidate_after_replacement`).
- Frontend: `/review` is the priority queue (filters, the sum behind each score), `/review/cross`, notification panel in the navbar (polled), value checks inside findings and in the document explorer, photos side by side, room table (`components/rooms.tsx`), evidence requests on the institution pages (`components/requests.tsx`).
- Seed: 10 more applications at INST-2016 to INST-2025 (shared faculty pair, look-alike, photo reuse pair, reused survey number pair, area mismatch, stale photo, missing library photo) and room tables for all. Live evaluation over 40 applications: 17 true positives, 0 false positives, 0 false negatives; clean control and look-alike not flagged.
- `core/db.py` resends reads, updates and deletes once after a dropped connection or a gateway 502 (never inserts). The seed reports applications left incomplete by an interrupted upload.
- Tests: `tests/test_phase3.py` (97 tests in all).

Phase 4 built:
- `services/registry_adapter.py` (MOCK issuer registry: modes unavailable (default), match, mismatch; ASSUMPTIONS A30, A31), `routers/verification.py` (`POST /documents/{id}/verify/registry` and `/verify/manual` with an optional attachment, `GET /documents/{id}/verification`, attachment link, `GET` and `PUT /admin/settings/registry`), check C15 (`R-REG-01`, `0005_phase4.sql`), Authenticity with reasons per document and method (`statuses.py`).
- `services/preflight.py` and `POST /applications/{id}/preflight` (institution only, nothing stored, no cross or C15, fix links). Institutions may read the values read from their own documents (A36).
- Frontend: `components/verification.tsx` (one row per method on the case page), the wizard `/institution/applications/new` with `components/prepare.tsx` (details, documents with values read, infrastructure and room table, pre-flight, submit), `/admin/settings` (registry mode). The Case File lists every check with its answer.
- Tests: `tests/test_phase4.py` (108 tests in all).

Phase 5 built:
- `services/rules.py` & `routers/rules.py` (rules lifecycle draft -> pending_approval -> active -> retired, four-eyes approval check, impact preview dry run on existing applications, text-to-rule drafting via Groq with deterministic fallback).
- `services/forensics.py` & `seed/signing.py` (check C13 signature validation using pyHanko and demo PKI trust store, check C14 PDF metadata anomaly detection).
- `routers/settings.py` & `/admin/settings` page (audited settings for checklists, document types, templates, weights, registry mode, trust store, as-of date).
- Tests: `tests/test_phase5.py` (143 tests in all).

Phase 6 built:
- Standalone `/audit` screen (`frontend/app/audit/page.tsx`) with search, event type filtering, details breakdown, and cryptographic hash chain verification badge.
- Added `/audit` navigation link in `Navbar.tsx` for `reviewer` and `rule_admin`.
- Automated hardening tests (`tests/test_phase6.py`):
  - Forbidden words test (greps frontend and API for fraud, forged, fake, and unapproved conclusions).
  - Hard-coded color test (verifies strict adherence to design tokens in `globals.css`).
  - Administrative decision immutability test (ensures `admin_status` is locked to 'pending').
  - Cryptographic audit chain tamper detection test.
  - Complete check catalog coverage test (C1 to C15).
- Full dataset evaluation benchmark (`scripts/evaluate.py` output in `evaluation.txt`): 22 true positives, 0 false positives, 0 false negatives, precision 1.000, recall 1.000, F1 1.000 across 44 applications.
- Updated `README.md` with 15-minute setup and 2-minute judge/evaluator demo path.
- Total test suite: 148 passed pytest tests; Next.js frontend builds cleanly with 18 routes.

After phase 6 (29/10/2026):
- Bug fixes: Authenticity reads "Signature missing" for an open unsigned finding (A38); a 401 signs the browser out and sends it to `/login?next=`; the evidence request form follows the newest document; audit event labels match the backend.
- Reading: label variants for all 20 templates (`0006_label_variants.sql`, `0007_label_variants_2.sql`); the faculty reader also reads headed `|` tables and tables laid out by word position (`tests/test_faculty_tables.py`).
- AI suggestions for missing values (`services/suggest.py`, `0008_ai_suggested_values.sql`, A40): grounded in a quoted line, stored as `AI_SUGGESTED` and `needs_confirmation`.
- Regulation clauses and draft explanations (`services/clauses.py`, `routers/clauses.py`, `0009_regulation_clauses.sql`, A41): "Why this rule" on each finding, BM25 retrieval, a guarded Groq draft with a template fallback, and a clause library in Settings.
- Landing page video (`frontend/public/media/upload-loop.mp4`), prototype notice moved to the footer (A39), `PROJECT_REPORT.md`.
- 202 backend tests pass.

## Roles

Spec section 4, assumption D5.

| Role | Access |
| :--- | :--- |
| `institution` | Its own institution's applications and documents. Sees only its own `evidence_requested` findings, never cross-institution ones. Another institution's application reads as 404 |
| `reviewer` | All applications, findings and cross-institution flags. Runs validation; resolves, dismisses or requests evidence. Needs MFA |
| `rule_admin` | Rules, checklists and settings; reads everything else. The approver of a rule must differ from its author. Needs MFA |

MFA is TOTP (aal2). `DEMO_MFA_BYPASS=true` in the local `.env` skips it for demo accounts.

## Running

```bash
# Backend (port 8001)
cd backend && PYTHONPATH=. .venv/bin/uvicorn main:app --reload --port 8001
PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/python -m seed.demo     # needs migrations 0001-0003 applied first
PYTHONPATH=. .venv/bin/python -m seed.samples  # synthetic files to upload by hand
PYTHONPATH=. .venv/bin/python -m seed.seed     # the 40-application dataset; --reset is a dry run without --yes
PYTHONPATH=. .venv/bin/python -m scripts.evaluate  # with the API running: scores against seed/ground_truth.json

# Frontend (port 3001)
cd frontend && npm run dev
npx tsc --noEmit && npx eslint . && npm run build
```

The ports differ from Nirikshan's (8000 and 3000) so both run side by side. Demo password: `password123`.

## Tech and conventions

- **Frontend:** Next.js 16 App Router with **Cache Components on**, React 19, TypeScript strict, Tailwind 4, lucide-react.
  - `useParams` and `useSearchParams` must be inside `<Suspense>`.
  - Don't call `new Date()` during render or prerender; it breaks the build. Compute dates in effects or callbacks.
- **Look:** ProofPath's own look, not Nirikshan's (Design, at the end of Part 1): register paper, blue-black ink, green ink (`officer`) only for what a person did, red pencil (`conflict`), and the highlighter (`mark`, the `Mark` component) on every value cited from a document. Martel headings, Mukta interface. Use only the tokens in `globals.css` (`bg-paper`, `text-ink`, `border-rule`, …), never hex values or default Tailwind palette classes. Every page shows the prototype notice (in the footer in `layout.tsx`, ASSUMPTIONS A39), every screen has a one-line description (`PageShell`), and status meaning never relies on colour alone. Reuse `components/ui.tsx` (`PageShell`, `Notice`, `Tag`, `Mark`, `Loading`, `Empty`, `FileNumber`, buttons, table classes, `formatDate`), `FileCover` and `documents.tsx`.
- **Dates:** shown as dd/mm/yyyy everywhere (`formatDate`, `formatDateTime`).
- **Writing style:** plain language and sentence-case headings, with no jargon or all-caps headings.
- **Words:** never state fraud, forged or fake, and never use approve or reject about an institution or application. Say conflict, mismatch, flag or candidate for review. Findings say what differs and where, never what it implies.
- **Checks are plain Python, never an LLM** (dates, IDs, counts, hashes, areas, rules). Low-confidence or ambiguous values go to `needs_confirmation`, never resolved silently. Everything simulated is labelled MOCK; all data is synthetic.
- **Backend:** FastAPI, Pydantic 2, and supabase-py with the service role. Use the `require_role([...])` dependency on every route.
- **LLM:** Groq only (`GROQ_API_KEY` and `GROQ_API_KEY_FAILSAFE`). **Do not use the Anthropic API key.** Every AI feature needs a rule-based fallback for when `_complete` returns None, and must not state facts or numbers that aren't in the record.
- **Secrets:** don't read or print values from `backend/.env` or `frontend/.env.local`; both are git-ignored.

## Working with the user

- Commit or push only when asked. Deploy only when asked.
- When the user names the product, it is **ProofPath AI**. The sister product is **Nirikshan** (not "ApprovalTrack").

## Design

ProofPath's look comes from Indian government file practice. Screenshots placed in a `design/`
folder override it (build spec, section 13). The tokens are defined once in `frontend/app/globals.css`;
components use only the token names, never hex values.

| Token | Value | Meaning |
| --- | --- | --- |
| `paper` | `#F3F4EF` | The page: cool register paper |
| `sheet` | `#FCFCFA` | A sheet laid on the page (tables, forms) |
| `ink` | `#1E2A44` | Blue-black ink: text and primary actions |
| `ink-2`, `ink-3` | `#4F5B73`, `#636D85` | Secondary and quiet text |
| `rule`, `rule-strong` | `#CDD3CC`, `#A3ADA5` | Ruled lines and borders |
| `officer` | `#1F6A4A` | Green ink, used only for what a person confirmed or did |
| `conflict` | `#B42318` | Red pencil: a conflict or a failed check |
| `pending` | `#7A4E00` | Waiting for a person |
| `mark` | `#F6E36A` | Highlighter on a value cited from a document |

- **Type:** Martel for headings and file numbers, Mukta for the interface. Both are from Indian type
  foundries and carry Devanagari, for a later Hindi interface.
- **The one bold element** is the highlighter: every value read from a document is marked and links
  to its page. Everything else stays quiet: ruled lines, a double ledger rule under the header and the
  file cover, 3 to 4 px radii, no gradients, no shadows, no pills.
- Status meaning never relies on colour alone; every status is also written out.

---

# Part 2: Assumptions and deviations from the build spec

The build spec (Part 3 below) is the source of truth. This part records
every place the build deviates from it, and every choice the spec leaves open. Each deviation is there
because the spec conflicts with the rules for the Supabase project ProofPath shares with Nirikshan
(SIH26262), or with the code that already existed when the spec arrived. Recorded on 28/10/2026.

## Deviations

| # | Spec says | We do | Why |
| --- | --- | --- | --- |
| D1 | Tables in `public` with a `pp_` prefix | Tables in the **`proofpath` schema**, without the prefix (`proofpath.applications`, `proofpath.findings`, …). SQL functions also live in `proofpath` (`proofpath.audit_append`, `proofpath.rule_ver`) | `public` belongs to Nirikshan's live demo. A separate schema isolates ProofPath more strongly than a prefix does, and `core/db.py` already binds every query to it |
| D2 | Storage bucket `pp-files` | Private bucket **`proofpath-documents`** | Already created by the existing migration and documented; it is still separate from Nirikshan's `documents` bucket |
| D3 | `pp_profiles` holds the role | **`proofpath.members`** holds the role, with the spec's `pp_profiles` columns (full name, role, institution) | Sign-in accounts are shared with Nirikshan. The role must never come from `app_metadata`, which holds the Nirikshan role |
| D4 | RLS policies so the browser can read some tables; Realtime on notifications | **The browser never reads `proofpath` tables.** Only `service_role` has grants and RLS is on with no policies. `0002_rls.sql` states and checks this lockdown instead of adding policies. Notifications are **polled** (every 30 s), not streamed | Stricter than the spec and simpler to reason about. Every access rule is enforced once, in FastAPI, and covered by tests per role (spec 5.2 already says the backend MUST do its own checks). The browser uses Supabase only for sign-in, MFA and uploading to signed URLs |
| D5 | Roles `institution_user`, `scrutiny_reviewer`, `rule_admin` | Roles **`institution`, `reviewer`, `rule_admin`** with exactly the spec's permissions (section 4). The earlier `verifier`, `analyst`, `auditor` and `admin` roles are dropped | Shorter names, same meaning. The spec gives reviewers cross-institution flags and audit access, which covers what the analyst and auditor roles did |
| D6 | No MFA | **TOTP MFA (aal2) kept for `reviewer` and `rule_admin`**, with `DEMO_MFA_BYPASS` for demo accounts | These roles see every institution's data or change rules. It costs nothing and was already built |
| D7 | Next.js 14, Tailwind 3.4, `@tanstack/react-query` | **Next.js 16** (App Router, Cache Components), React 19, **Tailwind 4**, and the existing `lib/api.ts` fetch client instead of react-query | Already set up and shared with Nirikshan. Tailwind 4 keeps theme tokens in CSS (`@theme` in `globals.css`), not `tailwind.config.js` |
| D8 | Neutral placeholder tokens until screenshots arrive in `/design` | A **ProofPath look of its own** (Part 1, Design), chosen on 28/10/2026 at the owner's request instead of Nirikshan's cream and terracotta: register paper, blue-black ink, green ink for officer actions, red pencil for conflicts, a highlighter on cited values; Martel and Mukta type. Colours are named tokens in `globals.css`; components hold no hex values, as section 13 requires | The owner asked for a distinctive theme that fits the subject. Screenshots added to `/design` later still override it |
| D9 | Optional Anthropic SDK, `LLM_API_KEY` | **Groq only** (`GROQ_API_KEY`, `GROQ_API_KEY_FAILSAFE`), through `services/llm.py`. Every LLM feature has a rule-based fallback | Owner's instruction. The LLM still only drafts text, never findings (principle 4) |
| D10 | Layout `backend/app/{core,routers,services}`, Python 3.11, API on port 8000 | Layout **`backend/{core,routers,services,schemas,seed,scripts,tests}`**, **Python 3.12**, API on **8001** and web on **3001** | Already in place. The ports differ from Nirikshan's (8000 and 3000) so both run side by side |
| D11 | Backend verifies tokens itself with `SUPABASE_JWT_SECRET` (HS256) | The token is checked with Supabase Auth (`auth.get_user`), then the role is loaded from `proofpath.members` | Also works with Supabase's asymmetric signing keys, and a signed-out session is rejected at once |
| D12 | `pp_audit_append` uses advisory lock key 7311 | `proofpath.audit_append` takes its lock on `hashtext('proofpath.audit_log')` | Avoids sharing a lock key with anything else in the shared database. Otherwise the hash formula is the spec's |
| D13 | The forbidden-words test greps for fraud, forged, fake, approve and reject | **fraud, forged and fake are always forbidden.** approve and reject are allowed only (a) in the rule lifecycle (`approved_by`, `/rules/{id}/approve`), which is governance and not a conclusion about an institution, and (b) in the mandatory Case File disclaimer ("does not approve, reject…"). The test keeps an explicit allow-list for these | The spec itself requires both uses, so a blanket ban cannot pass |
| D14 | Dates as DD/MM/YYYY | Same, written dd/mm/yyyy via `formatDate` and `formatDateTime` | Same rule |

## Choices the spec leaves open

| # | Topic | Choice |
| --- | --- | --- |
| A1 | Survey numbers (land) | Treated as a **reused identifier (C7)**: the same normalised survey number in applications from two institutions is flagged. This is the land-parcel case the problem statement cares about |
| A2 | OCR | Tesseract through `pytesseract`, as specified, behind `OCR_ENABLED`. When OCR is off or Tesseract is missing, a scanned page yields no text, its required fields become `needs_confirmation`, and nothing is guessed. Install with `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` |
| A3 | Demo accounts | `institution@`, `institution2@`, `reviewer@`, `ruleadmin@` and `ruleadmin2@proofpath.demo`. A second institution account is needed to test isolation, and a second rule admin to show four-eyes approval. `seed/demo.py` still refuses any other email domain |
| A4 | Existing case file code | The earlier model (`cases`, `facts`, `checks`, `patterns`) and its routes and pages are replaced in phase 1. Migration `0001` was never applied, so it is rewritten in place rather than migrated |
| A5 | API base path | `/api/v1`, as specified |
| A7 | Python dependencies | Added in the phase that first needs them, not all up front |
| A8 | Trigram index on faculty names | Not created. Name matching (C8) runs in Python with RapidFuzz, and `pg_trgm` may sit in a different schema in the shared project |
| A9 | Document viewer | The browser's own PDF viewer in an iframe, opened at a page with `#page=N`, instead of `pdfjs-dist`. A fresh signed link is fetched for each page jump, since links last 5 minutes |
| A10 | Sample files | `seed/samples.py` writes a few synthetic PDFs and a photo with PyMuPDF and Pillow for trying uploads by hand. The full dataset (spec 14) is `seed/seed.py`, which builds its PDFs with PyMuPDF rather than ReportLab, so no new dependency is needed |
| A11 | Review deadline | Set to the as-of date plus 30 days when an institution submits |
| A12 | Extracted values | Visible to reviewers and rule admins. Institutions see the file check and reading status of their documents, not the values, until the pre-flight check in phase 4 |
| A13 | Faculty list line format | `code \| name \| designation \| qualification \| masked ID \| period start \| period end`, documented in `services/extraction.py` |
| A14 | Date order (C3) in the statuses | A `DATE_ORDER_INVALID` finding counts under **Consistency** (Conflict detected), with the other conflicts between values. Spec 7.3 does not place it |
| A15 | As-of date | Read first from the `as_of` row in `proofpath.settings` (`{"mode": "fixed", "date": "2026-11-01"}`, set by `seed/seed.py`), then from `AS_OF_DATE_MODE` and `AS_OF_DATE`. Every reviewer and every run then sees the same date as the seeded dataset |
| A16 | Identifier templates | The extraction regexes for codes and numbers capture `[A-Z0-9][A-Z0-9/ .-]*?` up to the end of the line, so a value such as `FIRE/NASH/2026/1101` is read whole. Changed in `0003` and in the live rows |
| A17 | Sign-in cache | A verified token and its member row are kept for 30 seconds (never past the token's expiry), so each request does not make two extra round trips to Supabase. A signed-out token or a changed role therefore takes effect within 30 seconds |
| A18 | Reopening a finding | A resolved or dismissed finding stays closed when a later run finds the same condition; only open findings are updated or closed automatically. Reopening by hand is not in phase 2 |
| A19 | Cross-institution group | The case page has shown the "Across institutions" group since phase 2; checks C7 to C9 fill it from phase 3 |
| A20 | Faculty name similarity (C8) | R-GHOST-01 **version 2** asks for 0.9, not the spec's default 0.7. At 0.7 different people who share a given name match ("aditi agarkar" and "aditi rangan" score 72; unrelated pairs in the dataset reach 85), while spellings of one name score 94 or more. Version 1 is retired, not edited, so runs that recorded it keep it. Migration `0004_phase3.sql` |
| A21 | What C7 to C9 compare against | Current, file-checked documents of submitted (not draft) applications of *other* institutions. An institution's own applications in other years are not compared with each other |
| A22 | Cross matching at scale | Each run reads every other application's identifiers, faculty rows and photo fingerprints (five queries) and compares them in Python. Right for a prototype of a few dozen applications; a real deployment would index the normalised identifier and the name, and compare photo fingerprints in SQL |
| A23 | C10 and C11 | C10 does not report a category C1 already reports as a missing required document (the floor plan, or every photo when none is uploaded). C11 compares the room table with the declared total only when a room table exists; without one, Compliance reads Not assessable. The minimum area is checked against the declared total. The declared total comes from the application form, or the application record when the form has none |
| A24 | Photos with no EXIF date (C12) | No finding unless the rule's parameters set `require_exif: true` (the spec's "info note unless the rule requires it") |
| A25 | Automatic runs | A full run is started by the system, recorded with no person as the actor, when a document is read into an application that has been validated before (usually a replacement for an evidence request), and when a reviewer confirms or corrects a value. The audit event says which (`trigger`). This is how findings close automatically when a document is replaced |
| A26 | Answering an evidence request | The institution's note is kept in the audit trail and in the reviewer's notification. `evidence_requests` has no column for it, and adding one would need a migration for little gain |
| A27 | Dataset size | 40 applications rather than "about 30": the 30 from phase 2 are kept unchanged and 10 phase 3 scenarios are added at new institutions, so reviewer actions on the earlier ones survive. Every seeded application also gets a room table that adds up to its declared area |
| A28 | Dropped connections | Supabase closes idle connections and its gateway now and then answers 502. Reads, updates and deletes are sent once more; inserts never are, so nothing is stored twice |
| A29 | Queue filters | "Status" in the queue filters means the workflow status. The four review statuses need every document's values, which is too heavy for a list |
| A30 | Issuer registry and C15 | The spec lists check C15 but no rule for it, so **R-REG-01** (`registry_match`, high) switches it on (`0005_phase4.sql`). A registry holds three document types, each looked up by one number: approval certificate (certificate number; compares institution code, issue and expiry dates), fire NOC (NOC number; issue and expiry dates) and land document (survey number; registration number, land area). Kept in `services/registry_adapter.py` for now |
| A31 | MOCK registry modes | One setting, `registry_adapter_mode`: `unavailable` (default, as the spec says), `match` (the record repeats the values read) or `mismatch` (the record differs in one value, the last one compared). A rule administrator changes it on a small Settings page, with a reason kept in the audit trail. The full settings screen is phase 5 |
| A32 | Manual checks | The reviewer records the issuer asked, how they were asked, and the answer, with an optional copy of the reply (PDF, JPEG or PNG up to 5 MB, sent through the API and kept in the private bucket under `verification/`). Besides the spec's `manual_pending` and `manual_confirmed` there is `manual_not_confirmed`, for an issuer who does not confirm the document; it reads as Source mismatch. It opens no finding, since the reviewer recorded it themselves |
| A33 | When C15 runs | C15 uses the comparison stored with the latest lookup, so Authenticity and the finding always agree. A corrected value needs a new lookup; a replaced document has no lookup yet, so its finding closes. A lookup on a validated application runs validation again (`trigger: registry_checked`). Lookups and manual checks are only for submitted applications, and only reviewers make them |
| A34 | Authenticity wording | The status names what it found (Source mismatch, Signature invalid, or both), lists each document and method in its reasons, and adds "(MOCK source)" when every check behind it is a MOCK. When some sources are verified, documents a registry holds that no method has checked are listed as "Not checked yet". Before the first full run it still reads Not run yet (spec 7.3), though the document panel shows each check |
| A35 | Pre-flight | `POST /applications/{id}/preflight` runs C1 to C6 and C10 to C12 and stores nothing (no run, finding or audit event). Cross-institution checks and C15, which come from a reviewer's work, are never included. Only for an application the institution can still change (draft, or waiting for its answers), and rate-limited. Each item names the wizard step and document that fix it |
| A36 | Values for the institution | The spec lists `GET /documents/{id}/fields` for reviewers. The wizard's live extraction preview needs the institution to see what was read from its own files, so it may read them, without the reviewer's side: no normalised value, and a confirmed or corrected value shows as read. Another institution's document reads as 404 |
| A37 | Wizard | `/institution/applications/new` creates the draft at the first step, so uploads have somewhere to go; steps are open in any order after that. Type, year and area cannot be edited later (no update endpoint): starting again is the way to change them. Submitting is allowed with pre-flight items open, and reviewers see the same items |
| A38 | Unsigned documents in Authenticity | An open C13 finding always counts in Authenticity, even when the latest signature check is `unsigned` rather than invalid. When no check is invalid or mismatched and the only problem is an unsigned document whose type requires a signature, the value reads **Signature missing** (not in the spec's list, which has no value for it), with the finding as its reason. Dismissing or resolving the finding removes it. Before this, a valid signature on another document made Authenticity read Signature valid next to the open finding |
| A39 | Prototype notice | The spec asks for a banner on every page (section 13). It was a strip above the navigation; at the owner's request it is now a line in the footer of every page, with the same words, next to "Final decision: Pending (authorised AICTE official)". Every page still carries it (principle 7) |
| A40 | AI suggestions for missing values | When no extraction template finds a field, the page text goes to Groq in one call per document (`services/suggest.py`). A suggestion is kept only if the line it quotes is on the page it names, the value is inside that line and reads as its type, and no other field claims the same line and value. It is stored with `source_method = AI_SUGGESTED` (migration `0008`) and `needs_confirmation`, with the line in the reason, so no check uses it until a reviewer confirms or corrects it (principles 4 and 6). A label found with a value that does not parse is left as read, not replaced. With no Groq key, or when Groq fails, reading is unchanged; if `0008` is not applied, suggestions are dropped and the values read are stored as before |
| A41 | Regulation clauses and draft explanations | A library of regulation clauses in `proofpath.regulation_clauses` (migration `0009`), seeded with 16 ILLUSTRATIVE clauses written for this prototype, not official AICTE text, and labelled so on screen. For each finding, `services/clauses.py` returns the clauses its rule is linked to, then the closest by BM25 keyword search in plain Python (Groq has no embeddings; the same finding always gets the same clauses), at most three. A reviewer or rule administrator can ask for a draft explanation: Groq writes at most three sentences from the finding, its evidence, the rule and those clauses only, and the draft is used only if every number in it appears in that material, it cites only the clauses given and it has none of the words a finding must not use (fraud, forged, approve, reject and the like). Otherwise, or without Groq, a template from the finding's own text and the clause's first sentence is shown. The draft is labelled Draft, is not saved on the finding (principle 4), and the audit trail records that it was drafted, how and from which clauses. A rule administrator adds clauses with a source and a reason (audited); clauses are added, not edited. Without `0009` the clause routes answer 503 and nothing else changes |

---

# Part 3: ProofPath AI: Build Spec for Claude Code

> Kept as written. Where it mentions `ASSUMPTIONS.md` it now means Part 2, and `/design` means the Design section of Part 1. Where it disagrees with Part 2 (for example the `pp_` prefix or role names), Part 2 records what was built.

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
