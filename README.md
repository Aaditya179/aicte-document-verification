# ProofPath AI

**Traceable case files for AICTE applications** · Smart India Hackathon · Problem statement **SIH26261**

ProofPath AI turns the documents of an AICTE application into one traceable case file that shows what is verified, what conflicts, what is unverified and why. It also catches patterns across institutions that checking one application at a time cannot see.

> Advisory only: final decisions rest with the competent authority.

---

## Relationship to Nirikshan

ProofPath is a sister project of [Nirikshan](../aicte-workflow) (SIH26262). It uses the same Supabase project and the same interface (palette, fonts and components), and keeps its data apart:

| Shared | Kept apart |
| :--- | :--- |
| The Supabase project (URL and keys) | Tables: everything ProofPath owns is in the `proofpath` schema; Nirikshan's are in `public` |
| Sign-in accounts (`auth.users`) | Roles: ProofPath reads roles only from `proofpath.members`. A Nirikshan account has no ProofPath access unless it is added there, and ProofPath accounts set no Nirikshan role |
| The look: palette, fonts, `components/ui.tsx`, the MFA step | Files: the private `proofpath-documents` bucket, separate from Nirikshan's `documents` |
| | Ports: API on 8001 and web on 3001, so both apps run side by side |

The browser never queries the `proofpath` schema directly. Only the API's service role has access to it, and row-level security is on with no policies as a second lock.

---

## Data model

| Table | Holds |
| :--- | :--- |
| `institutions` | Institutions, by AICTE ID |
| `members` | Which shared accounts can use ProofPath, and their role: institution, verifier, analyst, auditor or admin |
| `cases` | One case file per application |
| `documents` | Each uploaded document, with its SHA-256 hash |
| `facts` | Each value read from a document, with the page, the line it came from and the read confidence |
| `checks` | The verdict on each field of a case (verified, conflict or unverified) and the reason, linked to the facts it rests on |
| `patterns` | Findings across institutions, such as the same land parcel declared by two applications |
| `audit_log` | Append-only, SHA-256 hash-chained audit trail |

The schema is in [`supabase/migrations/0001_proofpath_schema.sql`](supabase/migrations/0001_proofpath_schema.sql).

---

## Setup

### 1. Database (once)

1. In the Supabase dashboard, open the **SQL editor** and run `supabase/migrations/0001_proofpath_schema.sql`. It only creates the `proofpath` schema and the `proofpath-documents` bucket; nothing in `public` changes.
2. Go to **Project Settings → Data API → Exposed schemas**, add `proofpath` and save.

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env               # Same SUPABASE_* values as Nirikshan
PYTHONPATH=. .venv/bin/python -m seed.demo   # Demo accounts, 2 case files, 1 pattern
PYTHONPATH=. .venv/bin/uvicorn main:app --reload --port 8001
```

API docs: http://localhost:8001/docs

The seed script creates and updates only `@proofpath.demo` accounts and refuses any other email, so it cannot change a Nirikshan account.

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
| `verifier@proofpath.demo` | Verifier: opens case files, confirms or overrules findings |
| `analyst@proofpath.demo` | Analyst: reviews patterns across institutions |
| `institution@proofpath.demo` | Institution: sees its own case files |
| `auditor@proofpath.demo` | Auditor: read-only |
| `admin@proofpath.demo` | Administrator: accounts only, no case files |

---

## Project structure

```
proofpath-ai/
├── frontend/                Next.js 16, same palette and components as Nirikshan
│   ├── app/                 welcome, login, mfa, dashboard (case files), cases/[id], patterns
│   ├── components/          Brand, Navbar, ui (shared look), ServerWakeNote
│   └── lib/                 API client, Supabase client, types
├── backend/                 FastAPI
│   ├── core/                Settings, schema-bound database client, auth and roles, rate limiting
│   ├── routers/             auth, cases, patterns
│   ├── services/            audit (hash chain), llm (Groq)
│   ├── seed/                Demo data
│   └── tests/
└── supabase/migrations/     The proofpath schema
```

## Tests

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest -q
```
