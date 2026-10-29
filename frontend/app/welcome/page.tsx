import React from 'react';
import Link from 'next/link';
import Brand from '@/components/Brand';
import DemoAccounts from '@/components/DemoAccounts';
import ServerWakeNote from '@/components/ServerWakeNote';
import { StatusCards } from '@/components/findings';
import { Tag } from '@/components/ui';
import { btnPrimary, btnSecondary } from '@/components/styles';
import type { StatusCard } from '@/lib/types';

const DEMO_TEXT = 'Documents are uploaded one by one; each passes the file check and is read. The four statuses are shown separately, and the final decision stays Pending (authorised AICTE official).';

/** An 8-second loop of an application being prepared. Muted and without controls, so it reads as an
 *  illustration; with reduced motion asked for, the last frame is shown still instead. */
function Demo() {
  return (
    <figure className="relative">
      <div className="aspect-video overflow-hidden rounded-sheet border border-rule bg-sheet shadow-[0_18px_40px_-24px_color-mix(in_srgb,var(--color-ink)_45%,transparent)]">
        <video className="h-full w-full object-cover motion-reduce:hidden" src="/media/upload-loop.mp4" poster="/media/upload-loop-poster.jpg"
          autoPlay muted loop playsInline preload="auto" aria-label={DEMO_TEXT} />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="hidden h-full w-full object-cover motion-reduce:block" src="/media/upload-loop-poster.jpg" alt={DEMO_TEXT} />
      </div>
      <figcaption className="mt-4 text-sm text-ink-2">
        Each file is checked and read as it arrives. Four separate statuses, never one score, and the decision stays with the authorised AICTE official.
      </figcaption>
    </figure>
  );
}

/** A value cited from a document. On this page the highlighter is drawn on as the specimen scrolls into view. */
function Cited({ children }: { children: React.ReactNode }) {
  return <span className="mark mark-draw font-semibold">{children}</span>;
}

/** The look of a button inside a specimen. It is a picture of the control, so it is not focusable. */
function Control({ primary = false, children }: { primary?: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex rounded-control border px-3 py-1.5 text-sm font-semibold ${primary ? 'border-ink bg-ink text-sheet' : 'border-ink text-ink'}`}>
      {children}
    </span>
  );
}

function Evidence({ doc, page, label, children }: { doc: string; page: number; label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-sheet border border-rule bg-paper px-3 py-2.5">
      <p className="text-xs text-ink-2">{doc}, page {page}</p>
      <p className="mt-1 text-sm">{label}: <Cited>{children}</Cited></p>
    </div>
  );
}

const STATUSES: StatusCard[] = [
  { key: 'integrity', label: 'Integrity', value: 'Passed', tone: 'ok', reasons: [] },
  { key: 'consistency', label: 'Consistency', value: 'Conflict detected', tone: 'conflict', reasons: ['Faculty count differs between the form and the faculty list'] },
  { key: 'authenticity', label: 'Authenticity', value: 'Pending (source unavailable)', tone: 'pending', reasons: ['Issuer registry (MOCK) could not be reached; not a failed check'] },
  { key: 'compliance', label: 'Compliance', value: 'Meets configured checks', tone: 'ok', reasons: [] },
];

function FindingSpecimen() {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-serif text-base font-bold leading-snug">Declared faculty count 24 differs from faculty list total 22</p>
        <Tag tone="conflict">Open</Tag>
      </div>
      <p className="-mt-1 text-xs text-ink-2">Count conflict, rule R-PAIR-01 version 1, medium severity</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Evidence doc="Application form" page={1} label="Faculty in position">24</Evidence>
        <Evidence doc="Faculty list" page={2} label="Members listed">22</Evidence>
      </div>
      <div className="flex flex-wrap gap-2 pt-1"><Control>Resolve</Control><Control>Dismiss</Control><Control>Ask for evidence</Control></div>
    </div>
  );
}

function CrossSpecimen() {
  const side = (inst: string, city: string, period: string) => (
    <div className="rounded-sheet border border-rule bg-paper px-3 py-2.5 text-sm">
      <p className="font-semibold">{inst}<span className="font-normal text-ink-2">, {city}</span></p>
      <p className="mt-1">Dr Kavita Rao, assistant professor, M.Tech</p>
      <p className="mt-1 text-ink-2">ID <Cited>XXXX-XXXX-4821</Cited></p>
      <p className="text-ink-2">Employed <Cited>{period}</Cited></p>
    </div>
  );
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-serif text-base font-bold leading-snug">Faculty member listed by another institution for an overlapping period</p>
        <Tag tone="conflict">Across institutions</Tag>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {side('Narmada Institute of Technology', 'Jabalpur', '07/2024 to now')}
        {side('Tapti College of Engineering', 'Surat', '01/2025 to now')}
      </div>
      <p className="text-xs text-ink-2">Candidate for review. Reused photos and reused certificate or land survey numbers are flagged the same way.</p>
    </div>
  );
}

function AuthenticitySpecimen() {
  const rows: [string, string, React.ReactNode][] = [
    ['Fire NOC', 'Signature', <span key="s" className="font-semibold">Valid, signed by a trusted issuer</span>],
    ['Approval certificate', 'Issuer registry', <span key="r" className="flex flex-wrap items-center gap-2"><Tag tone="pending">MOCK</Tag><span className="font-semibold text-pending">Pending (source unavailable)</span></span>],
    ['Land document', 'Manual check', <span key="m" className="font-semibold text-officer">Confirmed with the sub-registrar by the reviewer</span>],
    ['Affidavit', 'File metadata', <span key="f" className="text-ink-2">Modified after it was signed (indicator only)</span>],
  ];
  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">Authenticity checks, one row per document and method</caption>
      <tbody>
        {rows.map(([doc, method, result]) => (
          <tr key={doc} className="border-b border-rule last:border-b-0">
            <th scope="row" className="py-2.5 pr-4 text-left font-semibold">{doc}</th>
            <td className="py-2.5 pr-4 text-ink-2">{method}</td>
            <td className="py-2.5">{result}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AiSpecimen() {
  return (
    <div className="space-y-4">
      <div className="rounded-sheet border border-rule bg-paper px-3 py-2.5 text-sm">
        <p className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">Fire NOC, valid until</span> <Cited>14/06/2027</Cited> <Tag tone="pending">Suggested by AI</Tag>
        </p>
        <p className="mt-1 text-ink-2">From the line &ldquo;This certificate remains in force until 14 June 2027.&rdquo; on page 1. No check uses it until a person confirms it.</p>
        <div className="mt-2 flex flex-wrap gap-2"><Control primary>Record as confirmed</Control><Control>Correct it</Control></div>
      </div>
      <div className="rounded-sheet border border-rule bg-paper px-3 py-2.5 text-sm">
        <p className="flex items-center gap-2 text-xs font-semibold"><Tag tone="pending">Draft</Tag> Suggested by AI</p>
        <p className="mt-1.5">The Fire NOC on page 1 was valid until 31/03/2026, before the as-of date. Clause ILL-1.2 asks that a certificate be in force when the application is examined.</p>
        <p className="mt-1.5 text-xs text-ink-2">Every number in a draft is checked against the record. It is not a conclusion and is not saved on the finding.</p>
      </div>
    </div>
  );
}

function RuleSpecimen() {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p><span className="font-serif text-base font-bold">R-AREA-01</span> <span className="text-ink-2">version 3, built-up area tolerance</span> <Cited>2%</Cited></p>
        <Tag tone="pending">Waiting for approval</Tag>
      </div>
      <p className="text-ink-2">Written by the first rule administrator. Another administrator approves it; the author cannot.</p>
      <div className="rounded-sheet border border-rule bg-paper px-3 py-2.5">
        <p className="font-semibold">Impact preview</p>
        <p className="mt-0.5 text-ink-2">Across the submitted applications this version would open 2 findings and close 1. Nothing is written until it is active.</p>
      </div>
    </div>
  );
}

function AuditSpecimen() {
  const events: [string, string, string, string][] = [
    ['29/10/2026, 11:42 am', 'Finding dismissed', 'Scrutiny reviewer', 'a41f…9c20'],
    ['29/10/2026, 11:40 am', 'Value corrected', 'Scrutiny reviewer', '7e0b…31d4'],
    ['29/10/2026, 11:31 am', 'Validation run', 'Scrutiny reviewer', 'c95a…e817'],
  ];
  return (
    <div className="space-y-3 text-sm">
      <ol className="space-y-0">
        {events.map(([when, what, who, hash]) => (
          <li key={hash} className="grid grid-cols-[1fr_auto] gap-x-4 border-b border-rule py-2 last:border-b-0 sm:grid-cols-[11rem_1fr_auto]">
            <span className="text-ink-2 tabular-nums">{when}</span>
            <span className="font-semibold"><span className={what === 'Validation run' ? '' : 'text-officer'}>{what}</span><span className="font-normal text-ink-2">, {who}</span></span>
            <span className="text-xs text-ink-3 tabular-nums">{hash}</span>
          </li>
        ))}
      </ol>
      <p className="flex flex-wrap items-center gap-2"><Tag tone="active">Chain intact</Tag><span className="text-ink-2">Each event&apos;s hash covers the one before it, so a changed or deleted event shows up.</span></p>
    </div>
  );
}

const SPECIMENS: { title: string; note: string; body: React.ReactNode }[] = [
  {
    title: 'Every value points to its page',
    note: 'A finding says what differs and where, with the rule and version behind it. Each highlighted value opens the document at the page it was read from.',
    body: <FindingSpecimen />,
  },
  {
    title: 'Four statuses, never one score',
    note: 'Integrity, consistency, authenticity and compliance are kept apart. A valid signature does not make a file compliant, and an unreachable source is not a failure.',
    body: <StatusCards statuses={STATUSES} columns={2} />,
  },
  {
    title: 'What one file cannot show',
    note: 'Every submitted application is compared with every other institution’s: the same faculty member, photo, certificate number or land survey number. Only reviewers see these flags.',
    body: <CrossSpecimen />,
  },
  {
    title: 'Each check keeps its own record',
    note: 'Digital signatures against a trust store, file metadata, the issuer’s register (a MOCK here) and a reviewer’s own confirmation. One never overrides another.',
    body: <AuthenticitySpecimen />,
  },
  {
    title: 'AI drafts, a person decides',
    note: 'AI reads values the patterns missed and drafts explanations from the regulation clauses. Every suggestion quotes its source and waits for a person.',
    body: <AiSpecimen />,
  },
  {
    title: 'Rules are data, and need two people',
    note: 'Thresholds live in versioned rules. A new version is previewed on real applications first, and its author cannot approve it.',
    body: <RuleSpecimen />,
  },
  {
    title: 'Nothing is quietly changed',
    note: 'Every action, with its reason, goes into a hash-chained audit trail. One click recomputes the whole chain.',
    body: <AuditSpecimen />,
  },
];

const ALSO: [string, string][] = [
  ['Pre-flight before submitting', 'Institutions run the checks on their own draft, with a link to the step that fixes each item. Nothing is stored.'],
  ['Evidence requests', 'A reviewer asks for a specific document by a date; the answer reruns validation and can close the finding.'],
  ['A queue that shows its sum', 'Applications are ordered by priority, and every score comes with the terms that add up to it.'],
  ['Area and infrastructure', 'The room table is added up against the declared built-up area, and missing laboratory, classroom or library photos are listed.'],
  ['Dates read two ways', 'A date such as 03/08/2025 could be 3 August or 8 March. It goes to a person, never guessed.'],
  ['Case file and snapshots', 'A printable record of every finding, check and action, frozen at a point in time when saved.'],
];

const PATH = [
  { title: 'Upload as the institution', text: 'Sign in as Aarohan Institute, open its draft application and upload the sample files from backend/seed/samples.' },
  { title: 'Watch each file being checked', text: 'Every file gets a fingerprint (SHA-256) and a type check. The renamed file not_really_a_pdf.pdf fails it and is never read.' },
  { title: 'Open the file as the reviewer', text: 'Sign in as the scrutiny reviewer and open the same application. Click any highlighted value to see the page it was read from.' },
  { title: 'Find what needs a person', text: 'The certificate’s issue date, 03/08/2025, could be 3 August or 8 March. It is marked for a person to confirm, not guessed.' },
];

export default function WelcomePage() {
  return (
    <div>
      <header className="ledger-rule">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Brand />
          <Link href="/login" className="text-sm font-semibold underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
            Sign in
          </Link>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:items-center">
        <div>
          <h1 className="font-serif text-[2.5rem] font-extrabold leading-[1.1] tracking-[-0.02em] sm:text-[3.4rem]">
            Every finding on an AICTE application points to the page it came from.
          </h1>
          <p className="mt-6 max-w-[58ch] text-lg text-ink-2">
            ProofPath reads each document in an application, checks the values against illustrative rules and against
            each other, and compares them across institutions. A reviewer sees what was found, where, and why. The
            decision stays with the authorised AICTE official.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a href={`/login?demo=${encodeURIComponent('reviewer@proofpath.demo')}`} className={`${btnPrimary} px-5 py-2.5`}>Open the reviewer&apos;s view</a>
            <a href="#demo" className={`${btnSecondary} px-5 py-2.5`}>See every demo account</a>
          </div>
          <p className="mt-6 max-w-[58ch] text-sm text-ink-2">
            SIH26261 prototype. Every institution, person, document and photo here is fictional, and anything simulated,
            such as the issuer registry, is labelled MOCK.
          </p>
        </div>
        <Demo />
      </section>

      <section aria-labelledby="specimens" className="border-t border-rule bg-paper">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="max-w-[60ch]">
            <h2 id="specimens" className="font-serif text-3xl font-extrabold leading-tight tracking-[-0.01em] sm:text-[2.4rem]">What a reviewer opens</h2>
            <p className="mt-3 text-lg text-ink-2">
              Parts of the real screens, shown with synthetic data. Sign in with a demo account to use each of them on the
              44 fictional applications.
            </p>
          </div>

          <ol className="mt-12">
            {SPECIMENS.map((s, i) => {
              const first = i === 0;
              const last = i === SPECIMENS.length - 1;
              return (
                <li key={s.title} className="grid lg:grid-cols-[minmax(0,1fr)_17rem] lg:gap-x-12">
                  <div className={[
                    'margin-rule border-x border-rule bg-sheet py-8 pl-10 pr-5 sm:pl-12 sm:pr-8',
                    'max-lg:mb-10 max-lg:rounded-sheet max-lg:border-y',
                    first ? 'lg:rounded-t-sheet lg:border-t' : '',
                    last ? 'lg:rounded-b-sheet lg:border-b' : 'lg:border-b lg:border-b-rule/70 lg:[border-bottom-style:dashed]',
                    'shadow-[0_1px_0_color-mix(in_srgb,var(--color-ink)_4%,transparent)]',
                  ].join(' ')}>
                    {s.body}
                  </div>
                  <div className="relative max-lg:order-first max-lg:mb-3 lg:pt-8">
                    {/* A pencil line from the note to the sheet, as a reviewer writes in the margin */}
                    <span aria-hidden="true" className="absolute -left-12 top-[2.35rem] hidden w-9 border-t border-ink-3 lg:block" />
                    <span aria-hidden="true" className="absolute -left-[0.95rem] top-[2.1rem] hidden size-1.5 rounded-full bg-ink-3 lg:block" />
                    <h3 className="font-serif text-lg font-bold leading-snug">{s.title}</h3>
                    <p className="mt-1.5 text-sm text-ink-2">{s.note}</p>
                  </div>
                </li>
              );
            })}
          </ol>

          <div className="mt-16 border-t border-rule pt-10">
            <h3 className="font-serif text-xl font-bold">Also in the prototype</h3>
            <dl className="mt-6 grid gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
              {ALSO.map(([term, text]) => (
                <div key={term}>
                  <dt className="font-semibold">{term}</dt>
                  <dd className="mt-1 text-sm text-ink-2">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      <section id="demo" aria-labelledby="try" className="scroll-mt-4 border-t border-rule bg-sheet">
        <div className="mx-auto grid max-w-6xl gap-14 px-4 py-20 sm:px-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 id="try" className="font-serif text-2xl font-extrabold sm:text-3xl">Try it with a demo account</h2>
            <p className="mt-2 text-ink-2">One click signs you in. Every demo account uses the password password123.</p>
            <ServerWakeNote className="mt-4" />
            <div className="mt-6"><DemoAccounts /></div>
          </div>
          <div>
            <h2 className="font-serif text-2xl font-extrabold sm:text-3xl">A two-minute path</h2>
            <ol className="mt-6 space-y-6">
              {PATH.map((step, i) => (
                <li key={step.title} className="grid grid-cols-[2.25rem_1fr] gap-x-2">
                  <span className="font-serif text-2xl font-bold leading-7 text-ink-3">{i + 1}</span>
                  <div>
                    <p className="font-semibold">{step.title}</p>
                    <p className="mt-0.5 text-sm text-ink-2">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}
