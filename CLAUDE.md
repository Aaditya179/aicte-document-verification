# ProofPath AI

Smart India Hackathon problem statement **SIH26261**. ProofPath AI is an evidence-first validation layer beside the AICTE approval workflow. It reads every document of an application, checks the claims against versioned rules and against each other, compares claims across institutions (the same faculty member, photo, certificate number or land survey number in more than one application), and gives the reviewer a case file in which every finding links to its document, page and value.

Every finding is decision support only. Reviewers resolve, dismiss or request evidence with a reason; the administrative decision always reads "Pending (authorised AICTE official)" and nothing can change it.

## Build spec and plan

- **`ProofPath AI Build Spec for Claude Code.md` is the source of truth.** Section 1.2 (principles) wins over everything, then sections 6 to 10 (logic).
- **`ASSUMPTIONS.md` records every deviation from the spec** (mainly: `proofpath` schema instead of `pp_` tables, roles `institution`/`reviewer`/`rule_admin`, no browser table access, Next 16 and Tailwind 4, Groq only). Read it before building; add to it when choosing anything the spec leaves open.
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

## Roles

Spec section 4, `ASSUMPTIONS.md` D5.

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
- **Look:** ProofPath's own look, not Nirikshan's (`design/README.md`): register paper, blue-black ink, green ink (`officer`) only for what a person did, red pencil (`conflict`), and the highlighter (`mark`, the `Mark` component) on every value cited from a document. Martel headings, Mukta interface. Use only the tokens in `globals.css` (`bg-paper`, `text-ink`, `border-rule`, …), never hex values or default Tailwind palette classes. Every page shows the prototype banner (in `layout.tsx`), every screen has a one-line description (`PageShell`), and status meaning never relies on colour alone. Reuse `components/ui.tsx` (`PageShell`, `Notice`, `Tag`, `Mark`, `Loading`, `Empty`, `FileNumber`, buttons, table classes, `formatDate`), `FileCover` and `documents.tsx`.
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
