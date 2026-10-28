# ProofPath AI

Smart India Hackathon problem statement **SIH26261**. ProofPath AI turns the documents of an AICTE application into one traceable case file that shows what is **verified**, what **conflicts** and what is **unverified**, and why. It also catches **patterns across institutions** (the same land parcel, faculty member or document in more than one application) that checking one application at a time cannot see.

Every finding is advisory: officers confirm or overrule it, and the decision stays with them. Each finding must point to the document, page and line it rests on.

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

**Built:**
- Schema `supabase/migrations/0001_proofpath_schema.sql` with institutions, members, cases, documents, facts, checks, patterns, an append-only hash-chained audit_log, and the storage bucket. As of 2026-10-28 it was **not yet applied**, and `proofpath` was not yet an exposed schema.
- Backend:
  - login with rate limiting and lockout (`routers/auth.py`) and `/me`;
  - `GET /cases`, `GET /cases/{id}` (checks with their facts, the documents, a summary count, and patterns that touch the case), and `GET /patterns`;
  - `GET /audit/verify`;
  - `services/llm.py` (Groq `_complete`, failsafe key, JSON schema checking).
- Frontend: welcome, login (one-click demo roles), MFA, `/dashboard` (case files sorted by conflicts), `/cases/[id]` (the case file), `/patterns`.
- Seed: `seed/demo.py` creates 5 demo accounts, 2 institutions, 2 case files (verified, conflict and unverified findings) and 1 `same_land_parcel` pattern on survey no. 112/3.

**Not built yet:** document upload, reading facts from documents (OCR or LLM), the rule engine that turns facts into checks, the job that finds patterns across institutions, officer review (confirming or overruling a finding, with an audit entry), and deployment.

## Roles

| Role | Access |
| :--- | :--- |
| `institution` | Its own case files only (another institution's case reads as 404) |
| `verifier` | All case files and patterns; reviews findings. Needs MFA |
| `analyst` | Patterns and case files. Needs MFA |
| `auditor` | Read-only |
| `admin` | Accounts only, **no case data** |

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
- **Look:** the cream and terracotta palette is intended. Use `#C25E26` (hover `#A84A19`), the light accent `#FBF0E4`, borders `#E8E2D8`, and the background `#FAF7F2` with the grid texture; headings in serif. Reuse `components/ui.tsx` (`PageShell`, `Notice`, `Badge`, `card`, buttons, `formatDate`) and `Brand`.
- **Dates:** shown as dd/mm/yyyy everywhere (`formatDate`, `formatDateTime`).
- **Writing style:** plain language and sentence-case headings, with no jargon or all-caps headings.
- **Backend:** FastAPI, Pydantic 2, and supabase-py with the service role. Use the `require_role([...])` dependency on every route.
- **LLM:** Groq only (`GROQ_API_KEY` and `GROQ_API_KEY_FAILSAFE`). **Do not use the Anthropic API key.** Every AI feature needs a rule-based fallback for when `_complete` returns None, and must not state facts or numbers that aren't in the record.
- **Secrets:** don't read or print values from `backend/.env` or `frontend/.env.local`; both are git-ignored.

## Working with the user

- Commit or push only when asked. Deploy only when asked.
- When the user names the product, it is **ProofPath AI**. The sister product is **Nirikshan** (not "ApprovalTrack").
