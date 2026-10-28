# ProofPath AI

**Evidence-first review of AICTE applications** · Smart India Hackathon · Problem statement **SIH26261**

ProofPath AI reads every document in an AICTE application, checks the values against versioned
(illustrative) rules and against each other, compares them across institutions, and gives the
reviewer a case file in which every finding points to the document and page it came from.

> Decision support only. The final decision always reads "Pending (authorised AICTE official)" and
> nothing in ProofPath can change it. All institutions, people, documents and photos are fictional;
> all rules are illustrative, not official AICTE rules.

The product is built phase by phase from
[`ProofPath AI Build Spec for Claude Code.md`](ProofPath%20AI%20Build%20Spec%20for%20Claude%20Code.md).
Every deviation from the spec, mostly to keep the shared Supabase project safe for Nirikshan, is in
[`ASSUMPTIONS.md`](ASSUMPTIONS.md). **Done so far:** phase 0 (setup) and phase 1 (foundation: schema,
roles, upload and reading pipeline, document viewer, welcome and sign-in).

---

## Relationship to Nirikshan

ProofPath is a sister project of Nirikshan (SIH26262). It uses the same Supabase project and keeps its
data apart:

| Shared | Kept apart |
| :--- | :--- |
| The Supabase project (URL and keys) | Tables: everything ProofPath owns is in the `proofpath` schema; Nirikshan's are in `public` |
| Sign-in accounts (`auth.users`) | Roles: ProofPath reads roles only from `proofpath.members`, never from `app_metadata` (Nirikshan's role) |
| | Files: the private `proofpath-documents` bucket, separate from Nirikshan's `documents` |
| | Ports: API on 8001 and web on 3001, so both apps run side by side |

The browser never queries the `proofpath` schema. Only the API's service role can reach it; row-level
security is on with no policies and browser roles have no grants. The API enforces each role's access.

---

## Setup

### 1. Database (once)

In the Supabase dashboard, open the **SQL editor** and run, in order:

1. `supabase/migrations/0001_proofpath_schema.sql`: the `proofpath` schema, its tables, the audit hash chain and the `proofpath-documents` bucket. Nothing in `public` changes.
2. `supabase/migrations/0002_rls.sql`: locks the schema to the API. It stops with an error if anything is still open to a browser role.
3. `supabase/migrations/0003_seed_reference.sql`: categories, document types, checklists, extraction templates and the illustrative rules.

Then go to **Project Settings → Data API → Exposed schemas**, add `proofpath` and save.

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                           # Same SUPABASE_* values as Nirikshan
PYTHONPATH=. .venv/bin/python -m seed.demo     # Demo accounts, 2 institutions, 2 draft applications
PYTHONPATH=. .venv/bin/python -m seed.samples  # Synthetic files to upload, in seed/samples/
PYTHONPATH=. .venv/bin/uvicorn main:app --reload --port 8001
```

API docs: http://localhost:8001/docs. Scanned pages are read only with Tesseract installed
(`brew install tesseract`) and `OCR_ENABLED=true`; without it their values go to a reviewer to confirm.

The seed script creates and updates only `@proofpath.demo` accounts and refuses any other email, so it
cannot change a Nirikshan account.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # Same Supabase URL and anon key as Nirikshan
npm run dev                         # http://localhost:3001
```

### Demo accounts

Password for all: `password123`

| Email | Role |
| :--- | :--- |
| `institution@proofpath.demo` | Institution: Aarohan Institute of Technology. Uploads documents |
| `institution2@proofpath.demo` | Institution: Vindhya College of Engineering. Shows that institutions never see each other's files |
| `reviewer@proofpath.demo` | Scrutiny reviewer: opens any application and its documents |
| `ruleadmin@proofpath.demo` | Rule administrator |
| `ruleadmin2@proofpath.demo` | Second rule administrator, for four-eyes approval of rule changes |

---

## Project structure

```
proofpath-ai/
├── frontend/                Next.js 16, Tailwind 4 (tokens in app/globals.css)
│   ├── app/                 welcome, login, mfa, institution/*, review/*, admin/rules
│   ├── components/          ui, FileCover, documents, DemoAccounts, Navbar, Brand
│   └── lib/                 API client, upload flow, Supabase client, types
├── backend/                 FastAPI
│   ├── core/                settings, schema-bound database, roles, access rules, as-of date, rate limits
│   ├── routers/             auth, applications, documents, reference
│   ├── services/            pipeline, extraction, normalise, audit, llm (Groq)
│   ├── schemas/             request bodies
│   ├── seed/                demo accounts, sample files
│   └── tests/
├── supabase/migrations/     0001 schema, 0002 lockdown, 0003 reference data
├── design/                  the design tokens
└── ASSUMPTIONS.md
```

## Tests

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest -q
cd frontend && npx tsc --noEmit && npx eslint . && npm run build
```
