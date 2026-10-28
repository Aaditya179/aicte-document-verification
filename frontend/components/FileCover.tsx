'use client';

import React from 'react';
import { CATEGORY_LABEL, WORKFLOW_LABEL, type ApplicationDetail } from '@/lib/types';
import { FileNumber, Tag, formatDate } from './ui';

/** The top of an application, laid out like a file cover. */
export function FileCover({ detail, children }: { detail: ApplicationDetail; children?: React.ReactNode }) {
  const { application: a, institution } = detail;
  return (
    <div className="ledger-rule pb-6">
      <p className="text-sm text-ink-2">File number</p>
      <h1 className="mt-1 text-3xl sm:text-4xl"><FileNumber code={a.code} /></h1>
      <p className="mt-3 text-lg">
        <span className="font-semibold">{institution.name}</span>
        <span className="text-ink-2">, {institution.city}</span>
        {institution.is_fictional && <span className="ml-2 align-middle"><Tag>Fictional</Tag></span>}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-4">
        <div><dt className="text-ink-2">Type</dt><dd className="font-semibold">{CATEGORY_LABEL[a.category]}</dd></div>
        <div><dt className="text-ink-2">Academic year</dt><dd className="font-semibold">{a.academic_year}</dd></div>
        <div><dt className="text-ink-2">Status</dt><dd className="font-semibold">{WORKFLOW_LABEL[a.workflow_status]}</dd></div>
        <div><dt className="text-ink-2">Review due</dt><dd className="font-semibold">{formatDate(a.review_deadline)}</dd></div>
      </dl>
      <p className="mt-4 text-sm">
        <span className="text-ink-2">Final decision: </span>
        <span className="font-semibold">Pending (authorised AICTE official)</span>
      </p>
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
