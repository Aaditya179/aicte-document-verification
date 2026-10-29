'use client';

import React from 'react';
import { CATEGORY_LABEL, WORKFLOW_LABEL, type ApplicationDetail } from '@/lib/types';
import { FileNumber, Tag, formatDate } from './ui';

/** The top of an application, laid out like a file cover. */
export function FileCover({ detail, children }: { detail: ApplicationDetail; children?: React.ReactNode }) {
  const { application: a, institution } = detail;
  return (
    <div className="ledger-rule pb-6">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          <p className="text-sm text-ink-2">File number</p>
          <h1 className="mt-1 text-3xl tracking-[-0.01em] sm:text-[2.6rem]"><FileNumber code={a.code} /></h1>
          <p className="mt-3 text-lg">
            <span className="font-semibold">{institution.name}</span>
            <span className="text-ink-2">, {institution.city}</span>
            {institution.is_fictional && <span className="ml-2 align-middle"><Tag>Fictional</Tag></span>}
          </p>
        </div>
        {/* Set like the decision field stamped on a file cover: the words carry it, and they never change */}
        <p className="max-w-[15rem] rounded-control border border-ink/70 bg-sheet px-4 py-3 text-sm outline outline-1 outline-offset-2 outline-ink/25">
          <span className="block text-xs text-ink-2">Final decision:</span>
          <span className="font-serif font-bold leading-snug">Pending (authorised AICTE official)</span>
        </p>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-3 border-t border-rule pt-4 text-sm sm:grid-cols-4">
        <div><dt className="text-ink-2">Type</dt><dd className="font-semibold">{CATEGORY_LABEL[a.category]}</dd></div>
        <div><dt className="text-ink-2">Academic year</dt><dd className="font-semibold">{a.academic_year}</dd></div>
        <div><dt className="text-ink-2">Status</dt><dd className="font-semibold">{WORKFLOW_LABEL[a.workflow_status]}</dd></div>
        <div><dt className="text-ink-2">Review due</dt><dd className="font-semibold">{formatDate(a.review_deadline)}</dd></div>
      </dl>
      {children}
    </div>
  );
}

/** Which documents the category requires, and which have arrived and passed the file check. */
export function Checklist({ detail }: { detail: ApplicationDetail }) {
  const missing = detail.checklist.filter((c) => !c.present).length;
  return (
    <section aria-labelledby="checklist">
      <h2 id="checklist" className="font-serif text-xl font-bold">Required documents</h2>
      <p className="mt-1 text-sm text-ink-2">
        {missing === 0 ? 'Every required document is here and passed the file check.' : `${missing} of ${detail.checklist.length} still to come.`}
        {' '}Photos needed: lab, classroom and library{detail.photo_categories.length > 0 && `; uploaded so far: ${detail.photo_categories.join(', ')}`}.
      </p>
      <ul className="mt-3 grid gap-x-8 sm:grid-cols-2">
        {detail.checklist.map((c) => (
          <li key={c.doc_type} className="flex items-center justify-between gap-4 border-b border-rule py-2 text-sm">
            <span>{c.label}</span>
            {c.present ? <Tag tone="ok">Received</Tag> : <Tag tone="pending">Not received</Tag>}
          </li>
        ))}
      </ul>
    </section>
  );
}
