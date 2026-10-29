import React from 'react';
import Link from 'next/link';
import Brand from '@/components/Brand';
import DemoAccounts from '@/components/DemoAccounts';
import ServerWakeNote from '@/components/ServerWakeNote';

const DEMO_TEXT = 'Documents are uploaded one by one; each passes the file check and is read. The four statuses are shown separately, and the final decision stays Pending (authorised AICTE official).';

/** An 8-second loop of an application being prepared. Muted and without controls, so it reads as an
 *  illustration; with reduced motion asked for, the last frame is shown still instead. */
function Demo() {
  return (
    <figure className="relative">
      <div className="aspect-video overflow-hidden rounded-sheet border border-rule bg-sheet">
        <video className="h-full w-full object-cover motion-reduce:hidden" src="/media/upload-loop.mp4" poster="/media/upload-loop-poster.jpg"
          autoPlay muted loop playsInline preload="auto" aria-label={DEMO_TEXT} />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="hidden h-full w-full object-cover motion-reduce:block" src="/media/upload-loop-poster.jpg" alt={DEMO_TEXT} />
      </div>
      <figcaption className="mt-4 border-l-2 border-ink pl-3 text-sm text-ink-2">
        Each file is checked and read as it arrives. Four separate statuses, never one score, and the decision stays with the authorised AICTE official.
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
        <Demo />
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
