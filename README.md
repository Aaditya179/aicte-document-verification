# ProofPath AI: Trust-Calibrated Document Verification & Regulatory Compliance

> **Smart India Hackathon 2026** · Problem Statement **SIH26261**  
> **Theme:** AI-Powered Application Validation, Document Authentication, and Regulatory Compliance Verification for AICTE.  
> **Core Architecture:** Evidence-First Validation Layer · 4 Trust-Calibrated Statuses · Deterministic Rule Engine · Cross-Institution Linkage · Cryptographic Audit Trail.

---

### 🌐 Live Deployment

| Service | Live Link | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | **[proofpath-frontend.onrender.com/welcome](https://proofpath-frontend.onrender.com/welcome)** | Interactive Next.js 16 Web Application with role-based guided paths |
| **Backend REST API** | **[proofpath-api-bcuv.onrender.com](https://proofpath-api-bcuv.onrender.com)** | FastAPI service running deterministic verification engine & PyMuPDF forensics |
| **API Documentation** | **[proofpath-api-bcuv.onrender.com/docs](https://proofpath-api-bcuv.onrender.com/docs)** | Interactive Swagger / OpenAPI Specification |
| **Health Check** | **[proofpath-api-bcuv.onrender.com/api/v1/health](https://proofpath-api-bcuv.onrender.com/api/v1/health)** | Live system status & database connectivity check |

---

## 1. Executive Summary & Problem Context

Every year, thousands of technical institutions submit regulatory approval applications to AICTE accompanied by tens of thousands of scanned certificates, land records, fire NOCs, affidavits, faculty rolls, floor plans, and geo-tagged infrastructure photos. Traditional validation methods face three major vulnerabilities:
1. **Opaque "Fraud Scores":** Black-box ML models output ambiguous risk numbers without pointing to exact textual or structural evidence.
2. **Siloed Inspection:** Applications are validated in isolation, allowing **ghost faculty** (professors listed simultaneously across multiple colleges), **reused campus photos** (same lab or classroom submitted under different college codes), and **reused land survey numbers** to slip past unnoticed.
3. **Audit Vulnerability:** Scrutiny actions and rule exceptions lack a tamper-evident, cryptographically verifiable paper trail.

### The ProofPath AI Solution
ProofPath AI operates as an **evidence-first scrutiny acceleration layer** alongside the AICTE approval workflow. It extracts claims from every document, checks them against versioned deterministic rules and against each other, compares claims across all institutions in the registry, verifies digital signatures and PDF metadata, and compiles a comprehensive **Case File** where every finding links directly to the cited page and highlighted text.

> **Decision Support Only:** The administrative decision field is strictly constrained to `"Pending (authorised AICTE official)"` at the database level. ProofPath AI surfaces verifiable evidence and preliminary indicators—the final administrative determination always remains with authorised human officials.

---

## 2. Key Architectural Differentiators

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 ProofPath AI                                    │
│                                                                                 │
│   ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐   │
│   │   Integrity Layer   │   │  Consistency Engine │   │ Authenticity Layer  │   │
│   │ Magic-byte, SHA-256 │   │ Cross-Document Pair │   │ pyHanko Trust Store │   │
│   │ Duplicate file hash │   │ Cross-Institution   │   │ MOCK Issuer Registry│   │
│   └──────────┬──────────┘   └──────────┬──────────┘   └──────────┬──────────┘   │
│              │                         │                         │              │
│              └─────────────────┬───────┴─────────────────────────┘              │
│                                │                                                │
│                 ┌──────────────▼──────────────┐                                 │
│                 │   4 Independent Statuses    │                                 │
│                 │  • Integrity                │                                 │
│                 │  • Consistency              │                                 │
│                 │  • Authenticity             │                                 │
│                 │  • Compliance               │                                 │
│                 └──────────────┬──────────────┘                                 │
│                                │                                                │
│                 ┌──────────────▼──────────────┐                                 │
│                 │  Append-Only Audit Chain    │                                 │
│                 │  SHA-256 Hash Chain Trigger │                                 │
│                 │  Tamper-Evident Genesis Log │                                 │
│                 └─────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

1. **Four Trust-Calibrated Statuses (Never a Single Fraud Score):**
   - **Integrity:** Magic-byte validation, PDF parsing integrity, document page limits, SHA-256 duplicate detection.
   - **Consistency:** Intra-application comparison pairs (e.g. form declared count vs faculty list), date chronological order, and cross-institution flags.
   - **Authenticity:** Cryptographic PDF digital signature verification (PKI trust store), PDF incremental revision metadata forensics, and issuer registry matching.
   - **Compliance:** Statutory document completeness, active validity on the as-of date, built-up area floor plan arithmetic, and campus photo evidence.
2. **Cross-Institution Verification Engine:**
   - **Ghost Faculty Detection (C8):** Identifies identical personnel claimed across institutions using RapidFuzz token-sort name similarity ($\ge 0.90$), masked government identifier matching, identical qualifications, and overlapping employment periods.
   - **Photo Reuse Detection (C9):** Computes a 64-bit perceptual hash (`imagehash.phash`) for infrastructure photos, detecting reused or resized/re-encoded lab and classroom photos across institutions with Hamming distance $\le 8$.
   - **Reused Identifier Tracking (C7):** Flags duplicate fire NOC numbers, approval certificates, and land survey parcels used in more than one application.
3. **Deterministic Rules as Versioned Data:**
   - Pure Python execution—never delegated to an LLM. Thresholds, parameters, and clauses live in database tables with a full lifecycle (`draft` $\to$ `pending_approval` $\to$ `active` $\to$ `retired`).
   - **Mandatory Four-Eyes Approval:** A rule author cannot approve their own rule.
   - **Impact Preview:** Dry-run simulation of draft rules against active applications before activation.
4. **Append-Only Cryptographic Audit Trail:**
   - Every validation run, field confirmation, reviewer action, rule modification, and configuration change is hashed in sequence (`SHA-256(prev_hash | fields | timestamp)`).
   - Database triggers strictly block `UPDATE`, `DELETE`, and `TRUNCATE` operations on `audit_events`.
   - Built-in one-click verification endpoint (`GET /audit/verify`) re-evaluates the entire hash chain from the genesis block.

---

## 3. Complete Verification Check Catalogue (C1 to C15)

Every check runs deterministically without hallucinations:

| Check ID | Finding Key | Severity | Logic & Verification Method |
| :---: | :--- | :---: | :--- |
| **C1** | `MISSING_DOCUMENT` | High | Required category documents minus uploaded, integrity-passed documents. |
| **C2** | `EXPIRED_DOCUMENT` | High | Document `expiry_date` prior to the configured as-of review date. |
| **C3** | `DATE_ORDER_INVALID` | Medium | Document `expiry_date` earlier than its recorded `issue_date`. |
| **C4** | `DATE_CONFLICT`, `ID_MISMATCH`, `COUNT_CONFLICT` | Medium | Intra-application discrepancy across document pairs (e.g., Form vs Certificate). |
| **C5** | `FIELD_NEEDS_CONFIRMATION` | Low | Low OCR confidence ($< 0.80$), ambiguous dates (`03/08/2026`), or missing fields. |
| **C6** | `DUPLICATE_FILE` | Low | Distinct documents within the same application sharing identical SHA-256 hashes. |
| **C7** | `REUSED_IDENTIFIER` | Medium | Reused certificate number, fire NOC, or land survey parcel across institutions. |
| **C8** | `GHOST_FACULTY` | Medium | RapidFuzz token-sort similarity $\ge 0.90$ + identical qualification + overlapping tenure. |
| **C9** | `PHOTO_REUSE` | Medium | 64-bit perceptual hash Hamming distance $\le 8$ across distinct institutions. |
| **C10** | `INFRA_EVIDENCE_MISSING` | High | Missing mandatory photo evidence categories (lab, classroom, library, floor plan). |
| **C11** | `AREA_MISMATCH`, `AREA_BELOW_MINIMUM` | Medium/High | Sum of room table dimensions vs declared area (tolerance 1%) and statutory minimum. |
| **C12** | `PHOTO_METADATA` | Low | Photo EXIF capture date older than 12 months relative to review deadline. |
| **C13** | `SIGNATURE_INVALID` | High/Medium | Digital signature validation via pyHanko (`valid`, `invalid`, `untrusted_chain`, `unsigned`). |
| **C14** | `METADATA_ANOMALY` | Low | Incremental revision added after signature, or creation date later than modification date. |
| **C15** | `REGISTRY_MISMATCH` | High | Direct discrepancy between extracted values and the issuer registry record. |

---

## 4. Benchmark Evaluation Results

Evaluated against the synthetic ground truth dataset (`seed/ground_truth.json`) with fixed as-of date `01/11/2026` across **44 submitted applications from 30 fictional institutions**:

```
Measured on a synthetic dataset; not validated on real AICTE records.

Ground truth: 44 applications, as-of date 2026-11-01.

True positives:  22
False positives: 0
False negatives: 0
Precision 1.000   Recall 1.000   F1 1.000

By finding type (True Positives / False Positives / False Negatives):
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

Run evaluation locally:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -m scripts.evaluate
```

---

## 5. Quick Guided Demo Walkthrough (2-Minute Evaluator Path)

Access the live web app: **[proofpath-frontend.onrender.com/welcome](https://proofpath-frontend.onrender.com/welcome)**

Password for all seeded demo accounts: **`password123`**

| Role | Email | Scope & Purpose |
| :--- | :--- | :--- |
| **Institution User** | `institution@proofpath.demo` | **Aarohan Institute of Technology:** uploads documents, manages room dimensions, runs self-service pre-flight checks. |
| **Second Institution** | `institution2@proofpath.demo` | **Vindhya College of Engineering:** proves strict tenant data isolation (institutions never see another's files). |
| **Scrutiny Reviewer** | `reviewer@proofpath.demo` | **AICTE Scrutiny Officer:** reviews prioritized queue, examines cited document pages, confirms/corrects OCR fields, acts on findings. |
| **Rule Administrator 1** | `ruleadmin@proofpath.demo` | **Regulatory Policy Admin:** authors rules, triggers dry-run impact previews, modifies extraction templates. |
| **Rule Administrator 2** | `ruleadmin2@proofpath.demo` | **Second Regulatory Officer:** satisfies mandatory four-eyes approval for rule activation. |

### Step-by-Step Walkthrough:

1. **Step 1: Welcome Screen (`/welcome`)**
   - Click any role badge to log in instantly, or test sign-in via email/password.
2. **Step 2: Applicant Wizard (`/institution/applications/new`)**
   - Walk through the preparation wizard: upload documents with live extraction feedback, enter room dimensions, run pre-flight check, and submit.
3. **Step 3: Reviewer Queue & Case File (`/review`)**
   - Open the prioritized queue sorted by transparent risk composition and statutory deadlines.
   - Click into an application (`/review/[id]`) to view:
     - The **4 Status Cards** (Integrity, Consistency, Authenticity, Compliance).
     - **Side-by-side evidence:** Compare conflicting values with the PDF document opened directly to the cited page and line.
     - **Across-institution matches:** Inspect ghost faculty with overlapping tenure and photo perceptual hash matches side by side.
     - **Issuer Verification:** Test the MOCK issuer registry and verify digital signature chains.
     - **Action Log:** Resolve or dismiss findings with mandatory recorded justifications.
   - Click **Print / Save Case File** (`/review/[id]/casefile`) for an official snapshot with hash verification.
4. **Step 4: Governance & Impact Preview (`/admin/rules`)**
   - View illustrative rules and version history.
   - Create a rule draft and execute an **Impact Preview** to see exactly how many open applications would be affected *before* activating the rule.
   - Test four-eyes approval: sign in as `ruleadmin2` to approve a rule created by `ruleadmin`.
5. **Step 5: Cryptographic Audit Explorer (`/audit`)**
   - Search the system-wide audit log by actor, entity, or event type.
   - Click **Check audit chain** to verify all SHA-256 hashes against genesis.

---

## 6. Technology Stack & Design System

- **Frontend:** Next.js 16 (App Router, Turbopack, Cache Components, React 19, TypeScript Strict).
- **Styling:** Tailwind CSS 4 with ProofPath's bespoke institutional paper-and-ink design tokens:
  - Register Paper (`bg-paper`), Blue-Black Ink (`text-ink`), Red Pencil Conflict (`text-conflict`), Officer Action Green (`text-officer`), Highlighter Evidence (`bg-mark`).
  - Typography: **Martel** (headings) & **Mukta** (interface), supporting Latin and Devanagari.
- **Backend:** FastAPI, Python 3.12, Uvicorn, Pydantic v2.
- **Document Processing & Forensics:**
  - `PyMuPDF`: Vector text extraction, coordinate bounding boxes, incremental revision parsing.
  - `pytesseract` & `Pillow`: Optical character recognition fallback for scanned records.
  - `imagehash`: 64-bit perceptual hashing (`pHash`) and Hamming distance calculation.
  - `rapidfuzz`: Token-sort ratio fuzzy matching for name deduplication.
  - `pyHanko`: X.509 PKI trust store certificate chain validation for PDF digital signatures.
- **Platform & Database:** Supabase Postgres (`proofpath` schema isolation, `pgcrypto`), Supabase Auth, Private Storage (`proofpath-documents`).

---

## 7. Local Development Setup (15 Minutes)

### 1. Database Setup (Supabase)
In your Supabase project's SQL editor, execute the migrations in order:
1. `supabase/migrations/0001_proofpath_schema.sql` (schema, tables, audit append/verify functions)
2. `supabase/migrations/0002_rls.sql` (lockdown: denies direct browser table access)
3. `supabase/migrations/0003_seed_reference.sql` (document types, checklists, illustrative rules C1–C14)
4. `supabase/migrations/0004_phase3.sql` (R-GHOST-01 v2 similarity 0.90)
5. `supabase/migrations/0005_phase4.sql` (R-REG-01 issuer registry check)

*Under **Project Settings → Data API → Exposed schemas**, add `proofpath` and save.*

### 2. Backend Setup

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Seed accounts, sample files, and 44 test applications
python -m seed.demo
python -m seed.samples
python -m seed.seed

# Run the 148 automated tests
PYTHONPATH=. pytest -q

# Start the API server on port 8001
uvicorn main:app --reload --port 8001
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local

# Run TypeScript check and production build
npx tsc --noEmit && npm run build

# Start the Next.js development server on port 3001
npm run dev
```

Visit `http://localhost:3001` in your browser.

---

## 8. Automated Test Suite

ProofPath AI includes a comprehensive test suite of **148 automated tests** covering all 15 checks, role-based access, security constraints, and data integrity:

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest -v
```

Tests include:
- `test_access.py`: Verifies multi-tenant isolation (institutions cannot read another's files or cross-institution findings).
- `test_upload_pipeline.py`: Validates magic bytes, SHA-256 hashing, PyMuPDF extraction, and version supersession.
- `test_validation.py`: Tests passing and failing conditions for checks C1 to C12.
- `test_phase3.py`: Validates cross-institution ghost faculty, photo reuse, and room area checks.
- `test_phase4.py`: Tests mock registry adapter states (`unavailable`, `match`, `mismatch`) and check C15.
- `test_phase5.py`: Tests digital signature validation (pyHanko), PDF metadata forensics (C13, C14), and four-eyes rule approvals.
- `test_phase6.py`: Enforces non-negotiable guardrails:
  - **Forbidden Words Test:** Confirms `fraud`, `forged`, and `fake` never appear in code, UI, or findings.
  - **Design Token Compliance:** Verifies components strictly use the defined theme tokens.
  - **Administrative Immutability:** Asserts `admin_status` cannot be altered from `'pending'`.
  - **Audit Tamper Detection:** Verifies `audit.verify_chain()` detects any altered hash link.

---

## 9. Render Deployment Architecture

Both services are configured via **`render.yaml`** (Render Blueprint):
- **Backend Web Service (`proofpath-api`):** Python 3.12 native runtime running `uvicorn main:app --host 0.0.0.0 --port $PORT` with healthcheck `/api/v1/health`.
- **Frontend Web Service (`proofpath-frontend`):** Node 20 runtime running `next start` on `$PORT`.

To deploy:
1. Connect this repository to **[Render](https://dashboard.render.com/)** as a **Blueprint**.
2. Supply your Supabase and Groq credentials in the prompted environment variables.
3. Render automatically provisions, builds, and deploys both services with zero manual configuration.

---

## 10. Disclaimer

*This prototype is developed for the Smart India Hackathon 2026 (Problem Statement SIH26261). All institutions, individual names, academic records, and photos in the test dataset are synthetic and fictional. All regulatory rules implemented are illustrative and do not represent official AICTE regulations. Issuer registry checks are simulated via a mock adapter. ProofPath AI provides preliminary decision-support indicators only; final administrative decisions rest exclusively with authorised AICTE officials.*
