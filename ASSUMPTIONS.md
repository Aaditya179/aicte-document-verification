# Assumptions and deviations from the build spec

The build spec (`ProofPath AI Build Spec for Claude Code.md`) is the source of truth. This file records
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
| D8 | Neutral placeholder tokens until screenshots arrive in `/design` | The **cream and terracotta palette shared with Nirikshan** is treated as the owner's design (see `design/README.md`). Its colours become named tokens in `globals.css` so that components hold no hex values, as section 13 requires | The owner chose the same look as Nirikshan. Screenshots added to `/design` later still override it |
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
| A6 | Faculty list line format | Documented in `services/extraction.py` when phase 1 builds it |
| A7 | Python dependencies | Added in the phase that first needs them, not all up front |
