# ProofPath AI: project report

**Smart India Hackathon 2026, problem statement SIH26261**
AI-powered application validation, document authentication and regulatory compliance verification for AICTE

Report date: 29/10/2026

| | |
| --- | --- |
| Web application | https://proofpath-frontend.onrender.com/welcome |
| API | https://proofpath-api-bcuv.onrender.com/api/v1 |
| API documentation | https://proofpath-api-bcuv.onrender.com/docs |
| Source code | https://github.com/Aaditya179/aicte-document-verification |
| Demo accounts | `institution@`, `institution2@`, `reviewer@`, `ruleadmin@`, `ruleadmin2@proofpath.demo`, password `password123` |

All institutions, people, documents and photos in the prototype are fictional. Anything simulated, such as the issuer registry, is labelled MOCK.

---

## 1. Problem statement

Every year thousands of technical institutions apply to AICTE for approval, extension of approval, a change in intake or a new programme. Each application carries dozens of documents: the application form, the current approval certificate, a fire safety no objection certificate, land documents, affidavits, faculty lists, floor plans and photographs of laboratories, classrooms and the library.

Scrutiny of these documents today is slow, manual and done one application at a time. That leaves four gaps:

1. **Volume.** A reviewer reads every page by hand. The same particular, such as the faculty count, the certificate validity or the land survey number, appears in several documents and has to be compared by eye.
2. **Applications are checked in isolation.** The same faculty member listed by two institutions for the same period, the same photograph of a laboratory submitted by two colleges, or one land survey number claimed in two applications cannot be seen when each file is read on its own.
3. **Authenticity is hard to establish.** Digital signatures, file metadata and confirmation with the issuing authority are rarely checked systematically.
4. **Traceability.** When something is found, it is hard to show later which document, which page and which rule it came from, who acted on it, and why. Rules change from year to year, and past decisions need to be read against the rules that applied at the time.

Automated "risk scores" do not solve this. A single number does not say what is wrong or where, cannot be checked by the reviewer, and invites decisions the system has no authority to make.

## 2. Our solution

ProofPath AI is an **evidence-first validation layer** that sits beside the AICTE approval workflow. It does not replace the portal and it does not decide anything. It:

- reads every document in an application and extracts the particulars it states,
- checks those particulars against versioned rules and against each other,
- compares them across all institutions' applications,
- runs the authenticity checks that are actually possible (file integrity, digital signatures, file metadata, the issuer's register),
- and gives the reviewer a **case file** in which every finding links to its document, page and value.

### Principles the system is built on

1. **Decision support only.** The administrative decision always reads "Pending (authorised AICTE official)". No screen or endpoint can change it.
2. **Four separate statuses, never one score.** Integrity, Consistency, Authenticity and Compliance are reported independently. A valid signature does not mean a document is compliant; consistent documents do not mean genuine ones; an unreachable source is not a failure.
3. **Checks are plain code, never an AI model.** Dates, identifiers, counts, file fingerprints, areas and rules are compared by deterministic code, so the same input always gives the same result and every result can be explained.
4. **AI only drafts, and a person decides.** Where an AI model is used, its output is a suggestion or a draft, grounded in the record and labelled as such. It never becomes a finding or a value on its own.
5. **Uncertainty goes to a person.** A value read with low confidence, or a date that can be read two ways (03/08/2025), is marked for a person to confirm, never guessed.
6. **Findings say what differs and where, never what it implies.** "Declared faculty count 24 differs from faculty list total 22 (page 2), candidate for review."
7. **Nothing is deleted from the record.** Every action is in an append-only, hash-chained audit trail, and each validation run records the rule versions it used.
8. **Institutions see only their own data.** Cross-institution results are visible only to reviewers.

## 3. Users and roles

| Role | What they do |
| --- | --- |
| Institution | Prepares and submits its own applications, uploads documents, runs a pre-flight check, answers evidence requests. Sees only its own data; another institution's application reads as "not found" |
| Scrutiny reviewer | Works through the priority queue, runs validation, reads findings with their evidence, resolves or dismisses findings or requests evidence (always with a reason), confirms or corrects values, checks signatures and the issuer registry, saves case file snapshots |
| Rule administrator | Maintains rules, checklists, document types, reading patterns, priority weights, the signature trust store and the regulation clause library. A rule needs a second administrator's approval before it becomes active |

Reviewers and rule administrators sign in with two-factor authentication (an authenticator app code).

## 4. Features

### 4.1 Document intake and reading

- **Signed uploads** straight to a private storage bucket. Each file gets a SHA-256 fingerprint and a check that its contents match its claimed type (a renamed file that is not really a PDF fails and is never read).
- **Versions.** Replacing a document keeps the earlier version; findings are re-evaluated against the new one.
- **Text reading** from PDFs, with OCR for scanned pages. A scanned page that cannot be read yields no values, and its required fields are marked for a person to confirm.
- **Reading patterns** (extraction templates) per document type, maintained as data. They accept the many ways a label is written ("Valid until", "Validity upto", "Date of expiry", "Declared built-up area (sq m)", lettered survey numbers and so on).
- **Value normalisation** across formats and units: dates in any common format, areas in square metres or square feet, numbers with Indian digit grouping, identifiers with varying separators. Ambiguous dates are flagged, not resolved.
- **Faculty list reader** that handles the expected line format, tables with a header row naming the columns, and tables laid out by position on the page, including wrapped rows. Identity numbers are masked to their last four digits on reading.
- **AI suggestions for missing values.** When no reading pattern finds a required value, the document text is sent to an AI model, which names the line the value is on. A suggestion is kept only if that line is really on the named page, the value is inside it and reads as its type, and no other field claims the same line. It is stored as "Suggested by AI", marked for a person to confirm, and no check uses it until a reviewer confirms or corrects it.
- **Photo fingerprints** (perceptual hashes) and photo dates from the file's EXIF data.
- **Room table** for infrastructure: each room with its type and area, entered by the institution.

### 4.2 Validation engine: fifteen checks

Every check is driven by a versioned rule and produces findings with a stable key, so reviewer actions survive re-runs. Findings whose condition no longer holds close automatically, with an audit entry.

| Check | What it finds |
| --- | --- |
| C1 Missing document | A document required for the application's category is absent or failed its file check |
| C2 Expired document | A certificate's validity ended before the as-of date |
| C3 Dates out of order | A document's expiry date falls before its issue date |
| C4 Conflicts between documents | The same particular differs between two documents of one application (dates, identifiers, counts), shown side by side |
| C5 Needs confirmation | A required value was read with low confidence, is ambiguous, was suggested by AI or was not found |
| C6 Duplicate file | The same file uploaded as two different documents |
| C7 Reused identifier | A certificate, NOC, registration or land survey number that also appears in another institution's application |
| C8 Faculty listed elsewhere | A person listed by two institutions for overlapping periods, matched on masked identity number, or on a close name match with the same qualification |
| C9 Photo reuse | An infrastructure photo matching one from another institution, even after resizing or re-encoding |
| C10 Infrastructure evidence missing | No photo of a laboratory, a classroom or the library, or no floor plan |
| C11 Built-up area | The declared area differs from the room table beyond the tolerance, or is below the minimum for the programme |
| C12 Photo age | A photo taken longer ago than the rule allows |
| C13 Signature | A signature that does not verify or does not chain to a trusted issuer, or a missing signature on a document type that requires one |
| C14 File metadata indicators | A PDF modified after it was signed, or with creation and modification dates out of order (shown as indicators only) |
| C15 Issuer registry difference | The issuer's register (MOCK) holds values that differ from the document |

### 4.3 Four statuses and the review priority

- **Integrity, Consistency, Authenticity, Compliance**, each with its value and the reasons behind it, worst state first. "Not run yet" before the first validation. Status meaning is always written in words, never shown by colour alone.
- **Priority score** that orders the reviewer's queue: a weighted sum of unresolved findings plus a bonus for a near deadline, shown with its full composition. The score orders work; it never changes a status.

### 4.4 Cross-institution engine

- Compares each submitted application with every other institution's submitted applications (drafts and the same institution are excluded).
- Reused identifiers (including land survey numbers), faculty listed by two institutions, and photo reuse.
- A dedicated **cross-institution flags** screen lists every open flag with both applications. List views show masked identifiers only.
- Tuned to avoid false matches: name similarity is set high enough that different people sharing a given name are not matched, while spellings of one name are. A deliberate look-alike in the dataset is correctly not flagged.

### 4.5 The reviewer's case page

- Four status cards, **Run validation**, and findings in two groups: within this application, and across institutions.
- **Every cited value is highlighted** and opens the document at the cited page. Conflicting values and matching photos are shown side by side.
- **Actions with a required reason:** resolve, dismiss or request evidence (with a due date). What a person did is shown in green ink, separately from what the system found.
- **Values table** with confirm or correct; the original reading is always kept, and validation reruns after a change.
- **Why this rule:** each finding shows its rule and the regulation clauses behind it, retrieved from the clause library (clauses linked to the rule first, then the closest by keyword search). A reviewer can ask for a **draft explanation** of the finding in two or three sentences. The draft is checked before it is shown: every number in it must appear in the finding, its evidence or the clauses; it may cite only the clauses it was given; and it may not use words that state a conclusion. Otherwise a template built from the record is shown. It is labelled Draft and is not saved on the finding.
- Documents with their verification state, evidence requests, the priority composition, rule versions used, and the application's audit trail with a chain check.

### 4.6 Case file

A printable case file with the application summary, the four statuses, every finding with its rule, version, evidence and status, documents with verification results, reviewer actions with reasons, every check with its answer, the rule versions of the latest run, and the line "Final decision: Pending (authorised AICTE official)". **Snapshots** freeze a copy at a point in time.

### 4.7 Authenticity layer

Each method keeps its own record and never overrides another:

- **File integrity:** SHA-256 fingerprint and type check.
- **Digital signatures:** embedded PDF signatures verified against a configurable trust store (valid, invalid, untrusted chain, unsigned, unsupported). The demo uses a fictional certificate authority.
- **File metadata indicators:** modification after signing, dates out of order, incremental updates.
- **Issuer registry (MOCK):** a lookup for approval certificates, fire NOCs and land records, set by the rule administrator to be unavailable (the default), to answer with a matching record, or to answer with a differing one. An unavailable registry reads "Pending (source unavailable)", never a failure.
- **Manual confirmation:** the reviewer records which issuer was asked, how, and the answer, with an optional copy of the reply.

### 4.8 Institution experience

- **Application wizard:** details, documents by type with a live preview of the values read (and why a value was not found), infrastructure evidence and room table, pre-flight, submit.
- **Pre-flight check:** runs the within-application checks before submission, stores nothing, and links each item to the step and document that fixes it. Cross-institution checks are never shown to an institution.
- **Evidence requests:** the institution sees only findings a reviewer has asked it about, answers with a note and an optional replacement document, and validation reruns automatically.
- **Notifications** in the navigation bar for both sides.

### 4.9 Rules registry

- Rules are data executed by deterministic code, each with a check type, parameters, severity, source reference and clause.
- **Lifecycle:** draft, waiting for approval, active, retired. **Four-eyes approval**: the author of a rule cannot approve it.
- **Impact preview:** a dry run of a draft rule over existing applications, showing the findings it would open or close, writing nothing.
- **Draft a rule from regulation text:** pasted text goes to an AI model, which proposes a check type, parameters and the clause they come from. The draft is used only if the clause is quoted from the text and every number comes from it; otherwise a rule-based reader tries. It is saved as a draft only, never active until a second person approves.
- History is never rewritten: a changed threshold is a new version, and each run records the versions it used.

### 4.10 Settings and the clause library

The as-of date (today, or a fixed date for repeatable demonstrations), priority weights, checklists per category, document types, reading patterns, the signature trust store, the MOCK registry mode and the regulation clause library. Every change is written to the audit trail with the value before and after and a reason. The clause library is seeded with sixteen illustrative clauses, one or more for every rule, and administrators can add clauses with their source.

### 4.11 Audit trail

- Append-only and **hash-chained**: each event's hash covers the previous hash and its own fields, computed inside the database under a lock so the chain cannot fork.
- Database triggers reject any update, delete or truncate.
- A one-click check recomputes the entire chain and reports any break.
- A searchable audit screen with filters by event type.

### 4.12 Security and privacy

- The browser never reads database tables directly. It uses the database provider only for sign-in and two-factor authentication; every other request goes through the API, which checks the role on every route.
- Row-level security is on with no policies, and only the server's service role has access.
- Institutions are isolated: another institution's application, document or finding reads as "not found".
- Identity numbers are masked on reading. Documents are in a private bucket and opened through short-lived signed links.
- Rate limits on sign-in, pre-flight and AI endpoints. No secret reaches the browser or the repository.

### 4.13 Design and accessibility

A distinct look based on a government register: paper, blue-black ink, green ink only for what a person did, red pencil for conflicts, and a highlighter on every value cited from a document. Plain-language, sentence-case writing; dates shown as dd/mm/yyyy; status never shown by colour alone; a one-line description on every screen; the prototype notice on every page; reduced-motion support.

## 5. Technology

| Part | Technology |
| --- | --- |
| Web application | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| API | FastAPI, Pydantic 2, Python 3.12 |
| Database, sign-in, storage | Supabase (PostgreSQL in its own `proofpath` schema, Auth with TOTP, private storage bucket) |
| Document reading | PyMuPDF, Tesseract OCR, Pillow, imagehash, RapidFuzz |
| Signatures | pyHanko |
| AI drafting | Groq (open-weight models), always with a rule-based fallback |
| Hosting | Render |

## 6. Evaluation and testing

**Detection on the synthetic dataset** (44 applications from 30 fictional institutions, as-of date 01/11/2026), scored against a ground truth file:

| Measure | Result |
| --- | --- |
| True positives | 22 |
| False positives | 0 |
| False negatives | 0 |
| Precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Applications that must not be flagged | 23 of 23 not flagged, including the clean control and a deliberate look-alike |

These figures are measured on a dataset we built, with scenarios we designed. They show the checks do what they are meant to; they are not a measurement on real AICTE records.

**Automated tests:** 202 backend tests covering every check, the review flow, role isolation, the rule lifecycle and four-eyes approval, signatures and metadata on real signed PDFs, AI grounding guards (with the model replaced by canned answers), the audit chain's tamper detection, the immutability of the administrative decision, a scan for forbidden words, and a scan that the interface uses only design tokens. The web application type-checks, lints and builds cleanly.

## 7. Benefits

**For AICTE and scrutiny reviewers**
- Hours of page-by-page comparison become a prioritised list of specific findings, each one click from its evidence.
- Problems that cannot be seen within one file (shared faculty, reused photos, reused land survey numbers and certificate numbers) are surfaced automatically.
- The queue puts the applications that most need attention first, and shows why.
- Every action is recorded with its reason, so decisions are consistent and defensible.

**For institutions**
- Pre-flight shows problems before submission, with a link to the fix, so fewer applications come back.
- Evidence requests are specific: what differs, where, and what to send.
- Isolation guarantees no institution sees another's data.

**For governance and the public interest**
- Findings are explainable and reproducible: the same documents and rules always give the same result.
- Rules are transparent, versioned and approved by two people; changing a rule never rewrites the past.
- A tamper-evident audit trail supports review, appeals and audits.
- AI is used where it helps (reading awkward documents, drafting explanations) and kept out of where it would be risky (deciding anything).

## 8. Limitations

**Data and rules**
- All data is synthetic. The evaluation results come from scenarios we designed and do not show performance on real applications.
- The fifteen rules and sixteen regulation clauses are illustrative, written for the prototype; they are not official AICTE norms or text.
- Thresholds (name similarity, photo distance, area tolerance, photo age) are set from the synthetic dataset and would need calibration on real data.

**Reading documents**
- Reading depends on label patterns. New document layouts need new patterns, or fall back to AI suggestions and confirmation by a person.
- OCR is English only, and quality depends on the scan. Handwritten text is not read.
- Complex tables beyond the supported faculty list layouts may not be read.

**Authenticity**
- The issuer registry is a MOCK; no real government register is connected.
- Signature checks rely on the configured trust store; the demo uses a fictional certificate authority.
- There is no image forensics (edited regions, copied stamps or signatures). Metadata checks are indicators only.
- Photo matching by perceptual hash can miss heavily cropped or edited copies.

**Scale and operations**
- Cross-institution comparison loads other applications into memory and compares them in code. This suits a prototype of tens of applications, not a national dataset.
- Notifications are polled in the browser; there is no email or SMS.
- The rate limiter keeps counts in memory per server process.
- Free hosting sleeps when idle, so the first request after a pause is slow.
- Database migrations are applied by hand.

**AI features**
- AI suggestions and draft explanations depend on an external model; without it the system falls back to rules and templates, which are plainer.
- Clause retrieval uses keyword search, which can miss a relevant clause worded very differently from the rule.

**Workflow**
- A resolved or dismissed finding cannot be reopened by hand.
- Application details cannot be edited after creation; the institution starts a new draft instead.
- The interface is in English only.

## 9. Future scope

**Retrieval over the full body of regulation**
- **RAG with embeddings:** ingest the complete AICTE Approval Process Handbooks, regulations, circulars and notifications across years, split into clauses, and retrieve with semantic embeddings combined with keyword search, so a finding finds its clause even when the wording differs completely.
- **Versioned regulation corpus** tied to rule versions, so every finding cites the clause in force on its as-of date, and a change in the handbook shows which rules and past findings it affects.
- **Regulation question answering** for reviewers and institutions ("what does the handbook require for library area for 300 intake?"), always answered with the cited clause and labelled as guidance.
- **Assisted rule authoring at scale:** propose rule drafts and parameter changes directly from each new handbook edition, with the impact preview run automatically, for human approval.
- **Multilingual retrieval** over Hindi and regional-language circulars.

**Real integrations**
- Live issuer registries: DigiLocker and API Setu for certificates, state land records for survey numbers, fire department registers for NOCs, and AICTE's own approval records.
- National faculty identity (with consent), such as AICTE's faculty registry and AISHE, so faculty listed by more than one institution can be confirmed against the source.
- End-to-end integration with the AICTE portal and with Nirikshan, the approval workflow and SLA monitor, so findings flow straight into the official workflow.

**Deeper document and image analysis**
- Image forensics: copy-move and splicing detection, and reused stamps or signatures within and across documents.
- Template fingerprinting: cluster documents from different institutions that share an unusual layout or font set.
- An evidence heatmap that draws the exact region of each cited value on the page.
- Vision-language reading of complex tables, handwritten entries, stamps and seals.
- Multilingual OCR for Hindi and regional languages, and a bilingual interface.
- Document version diff showing what changed between an original and its replacement.

**Physical verification**
- Geo-tagged photos checked against declared campus coordinates, and comparison with satellite imagery of the campus.
- A mobile application for inspection teams: guided capture of rooms, live measurement, and upload straight into the case.
- Video walkthroughs and drone footage as infrastructure evidence, with automatic room recognition.

**Network and pattern analysis**
- A graph of shared people, land parcels, addresses, phone numbers and identifiers across all institutions and years, so groups of linked applications are visible at once.
- Institution history timelines showing past findings and how they were resolved, never as a score.
- Year-on-year comparison of an institution's own claims (faculty, area, intake).

**Learning from reviewers, with people in control**
- Use reviewers' resolutions and dismissals to suggest better thresholds and reading patterns, always as drafts for a rule administrator to approve.
- Reviewer workload balancing and time analytics against a manual baseline.
- Voice-dictated reasons for reviewer actions.

**Continuous compliance**
- Monitoring after approval: reminders before certificates expire, and automatic re-checks when a registry record changes.
- A transparency portal publishing approved institutions' verified particulars.

**Trust and scale**
- Periodic anchoring of the audit chain's hash in an external, public record, so even a database administrator cannot rewrite history unseen.
- National-scale cross-institution matching across every application and every year.
- Formal accessibility and security audits, and offline-capable inspection tools.

## 10. Conclusion

ProofPath AI shows that scrutiny of AICTE applications can be made faster and more thorough without handing any decision to a machine. Every finding states what differs and where, links to the page it came from, and records the rule version behind it. Problems invisible within a single file are surfaced across institutions. Every action a person takes is kept in a tamper-evident record. AI helps where it is safe, by reading awkward documents and drafting explanations that a person checks, and the decision always stays with the authorised AICTE official.
