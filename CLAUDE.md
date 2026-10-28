# ProofPath AI

Smart India Hackathon problem statement **SIH26261**. ProofPath AI is an evidence-first validation layer beside the AICTE approval workflow. It reads every document of an application, checks the claims against versioned rules and against each other, compares claims across institutions (the same faculty member, photo, certificate number or land survey number in more than one application), and gives the reviewer a case file in which every finding links to its document, page and value.

Every finding is decision support only. Reviewers resolve, dismiss or request evidence with a reason; the administrative decision always reads "Pending (authorised AICTE official)" and nothing can change it.

## Build spec and plan

- **`ProofPath AI Build Spec for Claude Code.md` is the source of truth.** Section 1.2 (principles) wins over everything, then sections 6 to 10 (logic).
- **`ASSUMPTIONS.md` records every deviation from the spec** (mainly: `proofpath` schema instead of `pp_` tables, roles `institution`/`reviewer`/`rule_admin`, no browser table access, Next 16 and Tailwind 4, Groq only). Read it before building; add to it when choosing anything the spec leaves open.
- **Build one phase at a time (spec section 15) and stop after each one.** Report what was done and how it was verified, then wait. The user verifies and pushes, and says when to start the next phase.

## Sister project: Nirikshan

ProofPath was started on 2026-10-28 from **Nirikshan** (SIH26262, AICTE approval workflow and SLA monitoring) at `~/Desktop/projects/aicte-workflow` (GitHub `Aaditya179/aicte-workflow`). The two share **one Supabase project** and the **same UI**. Look at Nirikshan's code when you need a reference implementation, for example OCR of documents, document field matching across units and spellings (`backend/services/doc_fields.py`), document upload and storage, and the copilot's number guard.

### Rules for the shared Supabase project (do not break)
- **All ProofPath tables are in the `proofpath` schema.** Never create ProofPath tables in `public`, which is Nirikshan's. Backend code goes through `core/db.py`, whose `db.table()` is bound to `settings.SUPABASE_SCHEMA`.
- Only the `service_role` has grants on `proofpath`; RLS is on with no policies. The browser never queries Supabase tables directly. It uses Supabase only for sign-in and MFA, and everything else goes through the API.
- **`auth.users` is shared.** A ProofPath role comes only from `proofpath.members` (`core/security.py`). Never read the role from `app_metadata`, which holds the Nirikshan role. ProofPath accounts must not set an `app_metadata.role`, so they get no Nirikshan access.
- Demo accounts are `@proofpath.demo` only. `seed/demo.py` refuses to touch any other email. Never modify or delete `@demo.sih` (Nirikshan) accounts.
- Documents go in the private bucket `proofpath-documents`, never Nirikshan's `documents`.
- **There is no direct database connection string.** Migrations go in `supabase/migrations/` and the user applies them in the Supabase SQL editor. A new schema also has to be listed under Project Settings → Data API → Exposed schemas.
- The database is live and shared with Nirikshan's deployed demo. Make no destructive changes without asking, and show the scope (a dry run) before any bulk delete.

## Status

**Phase 0 (setup) done on 28/10/2026.** The next step is phase 1 (foundation).

What exists comes from an earlier model, built before the spec. Phase 1 replaces it:
- Migration `0001_proofpath_schema.sql` (cases, facts, checks, patterns). It was **never applied**, so phase 1 rewrites it in place with the spec's tables in the `proofpath` schema. `proofpath` is not yet an exposed schema.
- Backend parts to keep: login with rate limiting and lockout (`routers/auth.py`), `/me`, MFA (`core/security.py`), `services/audit.py` (hash chain), `services/llm.py` (Groq with failsafe key), and `core/config.py`, which has the spec's upload, OCR and as-of date settings.
- Parts to replace: `routers/cases.py`, `seed/demo.py`, and the pages `/dashboard`, `/cases/[id]` and `/patterns`. The welcome, login and MFA pages are reworked.

## Roles

These are the target roles from phase 1 on (spec section 4, `ASSUMPTIONS.md` D5). Until then the code still uses the old five.

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
PYTHONPATH=. .venv/bin/python -m seed.demo     # needs the migration applied first

# Frontend (port 3001)
cd frontend && npm run dev
npx tsc --noEmit && npx eslint . && npm run build
```

The ports differ from Nirikshan's (8000 and 3000) so both run side by side. Demo password: `password123`.

## Tech and conventions

- **Frontend:** Next.js 16 App Router with **Cache Components on**, React 19, TypeScript strict, Tailwind 4, lucide-react.
  - `useParams` and `useSearchParams` must be inside `<Suspense>`.
  - Don't call `new Date()` during render or prerender; it breaks the build. Compute dates in effects or callbacks.
- **Look:** the cream and terracotta palette is intended (`design/README.md`): accent `#C25E26` (hover `#A84A19`), light accent `#FBF0E4`, borders `#E8E2D8`, background `#FAF7F2` with the grid texture, headings in serif. Define colours once as tokens in `globals.css` and use only token names in components, never hex values (spec section 13). Every page shows the prototype banner, and status meaning never relies on colour alone. Reuse `components/ui.tsx` (`PageShell`, `Notice`, `Badge`, `card`, buttons, `formatDate`) and `Brand`.
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
