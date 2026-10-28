# ProofPath AI

**Evidence-first review of AICTE applications** · Smart India Hackathon · Problem statement **SIH26261**

ProofPath AI reads every document in an AICTE application, checks the extracted values against versioned (illustrative) rules and against each other, compares them across institutions, and gives the reviewer a comprehensive case file where every finding links directly to the cited document and page.

> **Decision support only.** The final decision always reads *"Pending (authorised AICTE official)"* and nothing in ProofPath can alter it. All institutions, people, documents and photos are fictional; all rules are illustrative, not official AICTE rules.

---

## Evaluation Benchmark

Measured on the synthetic dataset (`seed/ground_truth.json`, as-of date `01/11/2026`) across 44 submitted applications from 30 fictional institutions:

```
True positives:  22
False positives: 0
False negatives: 0
Precision 1.000   Recall 1.000   F1 1.000

By finding type (TP / FP / FN):
  AREA_MISMATCH                  1 /   0 /   0
  COUNT_CONFLICT                 1 /   0 /   0
  DATE_CONFLICT                  1 /   0 /   0
  DATE_ORDER_INVALID             1 /   0 /   0
  DUPLICATE_FILE                 1 /   0 /   0
  EXPIRED_DOCUMENT               1 /   0 /   0
  FIELD_NEEDS_CONFIRMATION       1 /   0 /   0
  GHOST_FACULTY                  2 /   0 /   0
  ID_MISMATCH                    1 /   0 /   0
  INFRA_EVIDENCE_MISSING         1 /   0 /   0
  METADATA_ANOMALY               2 /   0 /   0
  MISSING_DOCUMENT               1 /   0 /   0
  PHOTO_METADATA                 1 /   0 /   0
  PHOTO_REUSE                    2 /   0 /   0
  REUSED_IDENTIFIER              2 /   0 /   0
  SIGNATURE_INVALID              3 /   0 /   0

Must not be flagged: 23 of 23 clean applications had zero findings.
  INST-1001-2026-27-01 (clean control): not flagged
  INST-2018-2027-28-01 (lookalike faculty): not flagged
```

Run with: `PYTHONPATH=. .venv/bin/python -m scripts.evaluate` (output saved in `backend/evaluation.txt`).

---

## 15-Minute Setup

### Prerequisites
- Python 3.12
- Node.js 20+
- A Supabase project (shared with Nirikshan or standalone)
- Optional: `tesseract` (`brew install tesseract` on macOS / `apt-get install tesseract-ocr` on Linux) for OCR of low-text images.

### 1. Database Migrations
In the Supabase SQL Editor, run the migrations in order:
1. `supabase/migrations/0001_proofpath_schema.sql` (schema, tables, hash-chained audit trail)
2. `supabase/migrations/0002_rls.sql` (schema lockdown: browser denied direct table access)
3. `supabase/migrations/0003_seed_reference.sql` (document types, checklist, illustrative rules C1–C14)
4. `supabase/migrations/0004_phase3.sql` (R-GHOST-01 v2 similarity 0.90)
5. `supabase/migrations/0005_phase4.sql` (R-REG-01 issuer registry check)

Under **Project Settings → Data API → Exposed schemas**, add `proofpath` and save.

### 2. Backend (Port 8001)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Seed demo users, synthetic files, and 44 test applications
python -m seed.demo
python -m seed.samples
python -m seed.seed

# Start backend server
uvicorn main:app --reload --port 8001
```

### 3. Frontend (Port 3001)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3001` in your browser.

---

## 2-Minute Judge / Evaluator Demo Path

1. **Welcome (`/welcome`):**
   - Click one-click demo login cards or sign in with password `password123`.

2. **Institution Experience (`institution@proofpath.demo`):**
   - See own applications and workflow status (`/institution`).
   - Click **Prepare application** (`/institution/applications/new`) to view the multi-step preparation wizard with live extraction preview, room arithmetic, and instant pre-flight checks.
   - Cross-institution findings are isolated and never visible to the institution.

3. **Scrutiny Reviewer Experience (`reviewer@proofpath.demo`):**
   - Open **Review Queue** (`/review`) sorted by Trust-Calibrated review priority.
   - Open **Across Institutions** (`/review/cross`) to inspect Ghost Faculty candidates (token-sort similarity), photo perceptual hash reuse (Hamming distance $\le 8$), and reused land survey numbers across institutions.
   - Open a Case Page (`/review/[id]`):
     - View the 4 independent Trust-Calibrated statuses (Integrity, Consistency, Authenticity, Compliance).
     - Inspect cited page document viewer with highlighted values.
     - Confirm or correct OCR fields (preserves original extraction).
     - Test MOCK issuer registry and verify digital signature chain.
     - Resolve or dismiss findings with mandatory recorded reasons.
   - Click **Print / Save Case File** (`/review/[id]/casefile`) to view the printable evidence report and save an immutable snapshot.

4. **Rule Administrator Experience (`ruleadmin@proofpath.demo`):**
   - Manage rules and view lifecycle (`draft` → `pending_approval` → `active` → `retired`) at `/admin/rules`.
   - Four-eyes approval: a rule must be approved by a different administrator (`ruleadmin2@proofpath.demo`).
   - Run **Impact Preview** on any rule to dry-run changes against applications without altering existing findings.
   - Configure checklists, document types, weights, certificate trust store, and issuer registry mode at `/admin/settings`.

5. **Audit Trail (`/audit`):**
   - Searchable, append-only log of every run, action, rule change, and setting update.
   - Click **Check audit chain** to verify cryptographic SHA-256 integrity from genesis.

---

## Demo Accounts

Password for all accounts: `password123`

| Email | Role | Scope |
| :--- | :--- | :--- |
| `institution@proofpath.demo` | Institution | Aarohan Institute of Technology (own drafts & evidence requests) |
| `institution2@proofpath.demo` | Institution | Vindhya College of Engineering (demonstrates data isolation) |
| `reviewer@proofpath.demo` | Scrutiny Reviewer | Case file scrutiny, cross-institution flags, validation runs |
| `ruleadmin@proofpath.demo` | Rule Administrator | Rule lifecycle authoring, impact preview, system settings |
| `ruleadmin2@proofpath.demo` | Rule Administrator | Second rule administrator for mandatory four-eyes approvals |

---

## Architecture & Principles

1. **Decision Support Only:** Administrative status is strictly `'pending'`. No UI element or endpoint can approve or reject an application.
2. **Four Independent Statuses:** Integrity, Consistency, Authenticity, and Compliance are evaluated separately and never collapsed into a single composite score.
3. **Deterministic Logic:** All 15 checks (C1 to C15) execute as pure Python rules. LLMs are strictly optional and only used for drafting rule text from regulations, with guaranteed deterministic fallback.
4. **Append-Only Cryptographic Audit Chain:** Backed by database triggers preventing update or delete, with hash verification (`GET /audit/verify`).
5. **Wording Guardrail:** Output never claims "fraud", "forged", or "fake". System outputs report mismatches, conflicts, and candidates for review.

---

## Test Suite

```bash
# Backend (148 unit and integration tests)
cd backend && PYTHONPATH=. .venv/bin/pytest -q

# Evaluation benchmark (100% precision, recall, and F1)
PYTHONPATH=. .venv/bin/python -m scripts.evaluate

# Frontend (TypeScript strict check + production compile)
cd frontend && npx tsc --noEmit && npm run build
```
