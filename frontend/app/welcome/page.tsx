import React from 'react';
import Link from 'next/link';
import Brand from '@/components/Brand';
import DemoAccounts from '@/components/DemoAccounts';
import ServerWakeNote from '@/components/ServerWakeNote';

/** Two documents of one application disagree; the specimen shows how a finding cites both. */
function Specimen() {
  return (
    <figure aria-label="Example: a finding that cites two documents" className="relative">
      <div className="ruled rounded-sheet border border-rule bg-sheet px-6 pb-3 pt-4">
        <p className="text-xs text-ink-2">Approval certificate, page 1</p>
        <p className="mt-3 leading-8">Certificate number: AICTE-SYN/2025/77810</p>
        <p className="leading-8">Valid until: <span className="mark font-semibold">31 March 2028</span></p>
      </div>
      <div className="ruled relative -mt-2 ml-6 rounded-sheet border border-rule bg-sheet px-6 pb-3 pt-4 sm:ml-12">
        <p className="text-xs text-ink-2">Application form, page 1</p>
        <p className="mt-3 leading-8">Institution code: INST-1001</p>
        <p className="leading-8">Approval valid until: <span className="mark font-semibold">31 March 2029</span></p>
      </div>
      <figcaption className="ml-6 mt-4 border-l-2 border-conflict pl-3 text-sm text-conflict sm:ml-12">
        The two dates differ by one year. Candidate for review under rule R-PAIR-01, version 1.
      </figcaption>
    </figure>
  );
}

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

      <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-16 pt-12 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div>
          <h1 className="font-serif text-4xl font-extrabold leading-[1.15] sm:text-5xl">
            Every finding on an AICTE application points to the page it came from.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-ink-2">
            ProofPath reads each document in an application, checks the values against illustrative rules and against
            each other, and compares them across institutions. A reviewer sees what was found, where, and why. The
            decision stays with the authorised AICTE official.
          </p>
          <p className="mt-4 max-w-xl text-sm text-ink-2">
            SIH26261 prototype. Every institution, person, document and photo here is fictional, and anything simulated,
            such as the issuer registry, is labelled MOCK.
          </p>
        </div>
        <Specimen />
      </section>

      <section className="border-t border-rule bg-sheet">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 className="font-serif text-2xl font-bold">Try it with a demo account</h2>
            <p className="mt-2 text-ink-2">One click signs you in. Every demo account uses the password password123.</p>
            <ServerWakeNote className="mt-4" />
            <div className="mt-6"><DemoAccounts /></div>
          </div>
          <div>
            <h2 className="font-serif text-2xl font-bold">A two-minute path</h2>
            <ol className="mt-6 space-y-5">
              {PATH.map((step, i) => (
                <li key={step.title} className="grid grid-cols-[2rem_1fr] gap-x-2">
                  <span className="font-serif text-xl font-bold leading-6 text-ink-3">{i + 1}</span>
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
