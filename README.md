# ProofPath AI

> **Smart India Hackathon 2026**, problem statement **SIH26261**: AI-powered application validation, document authentication and regulatory compliance verification for AICTE.

ProofPath AI is an evidence-first validation layer beside the AICTE approval workflow. It reads every document in an application, checks the values against versioned rules and against each other, compares them across institutions, and gives the reviewer a case file in which every finding links to its document, page and value. The decision always stays with the authorised AICTE official.

- **Full report** (problem statement, every feature, benefits, limitations, future scope): [`PROJECT_REPORT.md`](PROJECT_REPORT.md)
- **Developer notes, assumptions and the build spec:** [`CLAUDE.md`](CLAUDE.md)

## Live deployment

| Service | Link |
| :--- | :--- |
| Web application | [proofpath-frontend.onrender.com/welcome](https://proofpath-frontend.onrender.com/welcome) |
| API | [proofpath-api-bcuv.onrender.com/api/v1](https://proofpath-api-bcuv.onrender.com/api/v1) |
| API documentation | [proofpath-api-bcuv.onrender.com/docs](https://proofpath-api-bcuv.onrender.com/docs) |
| Health check | [proofpath-api-bcuv.onrender.com/api/v1/health](https://proofpath-api-bcuv.onrender.com/api/v1/health) |

The free hosting sleeps when idle, so the first request after a pause can take up to a minute.

---

## 1. Why it is built this way

Scrutiny of AICTE applications is manual, slow and done one file at a time. The same particular appears in several documents and is compared by eye; a faculty member, photo or land survey number reused by two institutions cannot be seen within one file; and it is hard to show later which page and which rule a decision rested on. A single risk score does not help, because it does not say what is wrong or where.

ProofPath follows a few fixed principles:

1. **Decision support only.** The administrative decision always reads "Pending (authorised AICTE official)"; nothing can change it.
2. **Four separate statuses, never one score:** Integrity, Consistency, Authenticity, Compliance.
3. **Checks are plain code, never an AI model.** The same documents and rules always give the same result.
4. **AI only drafts or suggests, and a person decides.** Every AI output is grounded in the record, labelled, and has a rule-based fallback.
5. **Uncertain values go to a person**, never guessed.
6. **Findings say what differs and where**, never what it implies.
7. **Nothing is deleted.** Every action is in a hash-chained audit trail.
8. **Institutions see only their own data.**

## 2. Features

**Reading documents**
- Signed uploads to a private bucket, a SHA-256 fingerprint and a file type check for every file, and versions when a document is replaced.
- Text from PDFs, OCR for scans, and reading patterns per document type that accept the many ways a label is written.
- Values normalised across date formats, units (sq m and sq ft) and Indian digit grouping. Ambiguous dates such as 03/08/2025 are marked for a person.
- A faculty list reader for line, headed-table and positional-table layouts, masking identity numbers to the last four digits.
- **AI suggestions for missing values:** when no pattern finds a required value, an AI model names the line it is on. It is kept only if that line is really on the page and the value reads as its type, and it waits for a person to confirm it.

**Checking**
- Fifteen deterministic checks (below), driven by versioned rules. Findings have stable keys, so reviewer actions survive re-runs, and they close automatically when the condition no longer holds.
- **Cross-institution engine:** reused certificate, NOC and land survey numbers; faculty listed by two institutions for overlapping periods; photos reused across institutions, even after resizing.
- **Authenticity:** PDF signatures verified against a trust store, file metadata indicators, a MOCK issuer registry, and manual confirmation with the issuer. Each method keeps its own record.

**Reviewing**
- A priority queue that shows the sum behind each score.
- A case page with four status cards, findings within and across institutions, every cited value highlighted and opening the document at its page, conflicting values and photos side by side, and resolve, dismiss or request evidence, always with a reason.
- Confirm or correct any value read; the original is kept and validation reruns.
- **Why this rule:** each finding shows its rule and the regulation clauses behind it (clauses linked to the rule first, then the closest by keyword search). A reviewer can ask for a **draft explanation** of two or three sentences. It is checked before it is shown: every number must come from the record, only the retrieved clauses may be cited, and no wording may state a conclusion. Otherwise a template from the record is shown. It is labelled Draft and is not saved.
- A printable case file with snapshots, and a searchable audit log with a one-click chain check.

**For institutions**
- An application wizard with a live preview of the values read from each document.
- A pre-flight check before submitting, linking each item to its fix. It stores nothing and never shows cross-institution results.
- Evidence requests answered with a note and a replacement document, after which validation reruns.

**Governance**
- Rules as data with a draft, approval, active and retired lifecycle. **Four-eyes approval:** the author cannot approve their own rule.
- An impact preview of a draft rule over existing applications, writing nothing.
- Draft a rule from pasted regulation text (AI, grounded in the quoted clause, with a rule-based fallback). It is saved as a draft only.
- Audited settings: the as-of date, priority weights, checklists, document types, reading patterns, the signature trust store, the MOCK registry mode and the regulation clause library.

## 3. Check catalogue

| Check | Finding | Severity | What it finds |
| :---: | :--- | :---: | :--- |
| C1 | `MISSING_DOCUMENT` | High | A document required for the category is missing or failed its file check |
| C2 | `EXPIRED_DOCUMENT` | High | Validity ended before the as-of date |
| C3 | `DATE_ORDER_INVALID` | Medium | Expiry date before issue date in one document |
| C4 | `DATE_CONFLICT`, `ID_MISMATCH`, `COUNT_CONFLICT` | Medium | The same particular differs between two documents of one application |
| C5 | `FIELD_NEEDS_CONFIRMATION` | Low | A required value is low-confidence, ambiguous, suggested by AI or not found |
| C6 | `DUPLICATE_FILE` | Low | The same file uploaded as two documents |
| C7 | `REUSED_IDENTIFIER` | Medium | A certificate, NOC or land survey number also in another institution's application |
| C8 | `GHOST_FACULTY` | Medium | A person listed by two institutions for overlapping periods (masked ID, or name similarity of at least 0.90 with the same qualification) |
| C9 | `PHOTO_REUSE` | Medium | Perceptual hash distance of 8 or less to a photo from another institution |
| C10 | `INFRA_EVIDENCE_MISSING` | High | No laboratory, classroom or library photo, or no floor plan |
| C11 | `AREA_MISMATCH`, `AREA_BELOW_MINIMUM` | Medium, high | Room table against declared area (tolerance) and the minimum area |
| C12 | `PHOTO_METADATA` | Low | Photo taken longer before the as-of date than the rule allows |
| C13 | `SIGNATURE_INVALID` | High, medium | Signature invalid or untrusted, or missing where the document type requires one |
| C14 | `METADATA_ANOMALY` | Low | Modified after signing, or created after it was modified (indicator only) |
| C15 | `REGISTRY_MISMATCH` | High | The issuer registry (MOCK) differs from the document |

## 4. Evaluation

On the synthetic dataset (`backend/seed/ground_truth.json`): **44 applications from 30 fictional institutions**, as-of date 01/11/2026.

```
True positives:  22
False positives: 0
False negatives: 0
Precision 1.000   Recall 1.000   F1 1.000
Must not be flagged: 23 of 23, including the clean control and a look-alike faculty pair
```

These figures come from scenarios we designed. They show the checks behave as intended; they are not a measurement on real AICTE records. Full output: `backend/evaluation.txt`. To run it (with the API running):

```bash
cd backend && PYTHONPATH=. .venv/bin/python -m scripts.evaluate
```

## 5. Two-minute demo

Open [the welcome page](https://proofpath-frontend.onrender.com/welcome) and click a demo account. Every account uses the password **`password123`**.

| Role | Email | Use it to |
| :--- | :--- | :--- |
| Institution | `institution@proofpath.demo` | Prepare and submit an application for Aarohan Institute of Technology, run pre-flight, answer requests |
| Second institution | `institution2@proofpath.demo` | See that institutions never see each other's data |
| Scrutiny reviewer | `reviewer@proofpath.demo` | Work the queue, read findings and evidence, act on findings |
| Rule administrator | `ruleadmin@proofpath.demo` | Write rules, preview their impact, change settings, add clauses |
| Second rule administrator | `ruleadmin2@proofpath.demo` | Approve a rule the first one wrote (four-eyes) |

1. **Institution:** open the wizard (`/institution/applications/new`), upload documents and watch the values being read, enter the room table, and run pre-flight.
2. **Reviewer:** open the queue (`/review`) and an application. Look at the four statuses, click a highlighted value to open its page, compare conflicting values and photos side by side, and open **Why this rule** on a finding, then **Draft an explanation**.
3. **Reviewer:** confirm or correct a value marked for confirmation, resolve or dismiss a finding with a reason, check a document in the MOCK issuer registry, and open the case file.
4. **Rule administrator:** draft a rule, run its impact preview, and submit it; then approve it as the second administrator.
5. **Audit** (`/audit`): search the log and click **Check audit chain**.

## 6. Technology

| Part | Technology |
| :--- | :--- |
| Web application | Next.js 16 (App Router, Cache Components), React 19, TypeScript, Tailwind CSS 4 |
| API | FastAPI, Pydantic 2, Python 3.12 |
| Database, sign-in, storage | Supabase: PostgreSQL in its own `proofpath` schema, Auth with TOTP, private bucket `proofpath-documents` |
| Documents | PyMuPDF, Tesseract (pytesseract), Pillow, imagehash, RapidFuzz |
| Signatures | pyHanko |
| AI drafting | Groq, always with a rule-based fallback |
| Hosting | Render (`render.yaml`) |

The look is ProofPath's own: register paper, blue-black ink, green ink only for what a person did, red pencil for conflicts and a highlighter on every value cited from a document, with Martel and Mukta type. The tokens are in `frontend/app/globals.css` and described in `CLAUDE.md` (Design).

## 7. Local setup

### Database (Supabase)

There is no direct database connection; run each migration in the Supabase SQL editor, in order:

| Migration | What it adds |
| :--- | :--- |
| `0001_proofpath_schema.sql` | Schema, tables, audit append and verify functions |
| `0002_rls.sql` | Lockdown: row-level security on, no browser access |
| `0003_seed_reference.sql` | Categories, document types, checklists, reading patterns, illustrative rules |
| `0004_phase3.sql` | R-GHOST-01 version 2 (name similarity 0.90) |
| `0005_phase4.sql` | R-REG-01, the issuer registry check |
| `0006_label_variants.sql`, `0007_label_variants_2.sql` | More ways a label can be written |
| `0008_ai_suggested_values.sql` | Allows values suggested by AI |
| `0009_regulation_clauses.sql` | The regulation clause library and its illustrative clauses |

Then add `proofpath` under **Project Settings → Data API → Exposed schemas**.

### Backend (port 8001)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in Supabase and Groq values

PYTHONPATH=. python -m seed.demo      # five demo accounts (@proofpath.demo only)
PYTHONPATH=. python -m seed.samples   # sample files to upload by hand
PYTHONPATH=. python -m seed.seed      # the 44-application dataset

PYTHONPATH=. uvicorn main:app --reload --port 8001
```

### Frontend (port 3001)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3001. The ports differ from Nirikshan's (8000 and 3000), so both run side by side.

## 8. Tests

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest -q          # 202 tests
cd frontend && npx tsc --noEmit && npx eslint . && npm run build
```

| File | Covers |
| :--- | :--- |
| `test_access.py` | Isolation between institutions and roles |
| `test_upload_pipeline.py` | File checks, fingerprints, reading, versions |
| `test_normalise_extraction.py`, `test_label_variants.py`, `test_faculty_tables.py` | Value normalisation, label variants, faculty tables |
| `test_validation.py`, `test_review_flow.py` | Checks C1 to C6, statuses, priority, reviewer actions |
| `test_phase3.py` | Cross-institution checks, infrastructure and area, evidence requests |
| `test_phase4.py` | MOCK registry, C15, manual checks, pre-flight |
| `test_phase5.py` | Signatures and metadata on real signed PDFs, rule lifecycle and four-eyes approval, impact preview, rule drafting, settings |
| `test_suggest.py`, `test_clauses.py` | AI suggestions and draft explanations: only grounded output gets through |
| `test_phase6.py` | Forbidden words, design tokens only, the decision stays pending, audit tamper detection, every check present |
| `test_repo_secrets.py`, `test_health.py` | No secrets in the repository, health endpoint |

## 9. Deployment

Both services are defined in `render.yaml` as a Render Blueprint: `proofpath-api` (Python, `uvicorn main:app`, health check `/api/v1/health`) and `proofpath-frontend` (Node, `next start`). Connect the repository as a Blueprint and supply the Supabase and Groq values when asked. Pushes to `main` deploy automatically.

## 10. Disclaimer

This prototype was built for the Smart India Hackathon 2026 (SIH26261). Every institution, person, document and photo in it is fictional. The rules and regulation clauses are illustrative and are not official AICTE norms or text. The issuer registry is a MOCK. ProofPath AI gives preliminary decision-support indicators only; the decision on every application rests with the authorised AICTE official.
