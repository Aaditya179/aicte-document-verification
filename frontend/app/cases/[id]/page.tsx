'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, CheckCircle2, AlertTriangle, HelpCircle, FileText, Network, Quote } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { PageShell, Notice, Badge, card, formatDate } from '@/components/ui';
import { type CaseFile, type CheckStatus, type Check, STATUS_META, humanize } from '@/lib/types';

const ICONS: Record<CheckStatus, React.ElementType> = { verified: CheckCircle2, conflict: AlertTriangle, unverified: HelpCircle };
const ORDER: CheckStatus[] = ['conflict', 'unverified', 'verified'];
const BORDER: Record<CheckStatus, string> = {
  verified: 'border-emerald-200', conflict: 'border-red-200', unverified: 'border-amber-200',
};

function CheckCard({ check, docTitle }: { check: Check; docTitle: (id: string | null) => string }) {
  const Icon = ICONS[check.status];
  const meta = STATUS_META[check.status];
  return (
    <li className={`rounded-xl border bg-white p-4 ${BORDER[check.status]}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-stone-900">
          <Icon className="h-4 w-4" aria-hidden="true" /> {humanize(check.field)}
        </h3>
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </div>
      <p className="mt-1.5 text-sm text-stone-700">{check.reason}</p>
      {check.facts.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {check.facts.map((f) => (
            <li key={f.id} className="rounded-lg bg-[#FAF7F2] border border-[#F0EBE3] px-3 py-2 text-xs">
              <p className="font-semibold text-stone-900">{f.value_text}</p>
              <p className="mt-0.5 text-stone-600">
                {docTitle(f.document_id)}{f.page ? `, page ${f.page}` : ''}
                {f.confidence != null && ` · read with ${Math.round(f.confidence * 100)}% confidence`}
              </p>
              {f.source_quote && (
                <p className="mt-1 flex gap-1 text-stone-500"><Quote className="h-3 w-3 mt-0.5 shrink-0" aria-hidden="true" /> {f.source_quote}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      {check.reviewed_at && (
        <p className="mt-2 text-xs text-stone-500">Reviewed {formatDate(check.reviewed_at)}{check.review_note ? `: ${check.review_note}` : ''}</p>
      )}
    </li>
  );
}

function CaseFileContent() {
  const { id } = useParams<{ id: string }>();
  const [file, setFile] = useState<CaseFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<CaseFile>(`/cases/${id}`).then(({ data, error }) => {
      setFile(data);
      setError(data ? null : error);
    });
  }, [id]);

  if (error) return <PageShell title="Case file"><Notice kind="error">{error}</Notice></PageShell>;
  if (!file) return <PageShell title="Case file"><div className={`${card} h-48 animate-pulse`} aria-label="Loading case file" /></PageShell>;

  const { case: c, documents, checks, summary, patterns } = file;
  const docTitle = (docId: string | null) => documents.find((d) => d.id === docId)?.title || 'Entered by hand';

  return (
    <PageShell
      title={`${c.case_no} · ${c.institutions.name}`}
      subtitle={`${humanize(c.application_type)} for ${c.academic_year}. Every finding shows the document, page and line it rests on.`}
      actions={<Link href="/dashboard" className="flex items-center gap-1 text-sm font-medium text-[#C25E26] hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> All case files</Link>}
    >
      <div className="grid grid-cols-3 gap-3">
        {ORDER.map((s) => {
          const Icon = ICONS[s];
          return (
            <div key={s} className={card}>
              <p className="flex items-center gap-1.5 text-xs font-semibold text-stone-600"><Icon className="h-4 w-4" aria-hidden="true" /> {STATUS_META[s].label}</p>
              <p className="mt-1 text-3xl font-bold text-stone-900">{summary[s]}</p>
              <p className="mt-1 hidden text-xs text-stone-500 sm:block">{STATUS_META[s].blurb}</p>
            </div>
          );
        })}
      </div>

      {patterns.length > 0 && (
        <div className="mt-6">
          <Notice kind="warning">
            <span className="flex items-start gap-2">
              <Network className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
              <span>
                <strong>Seen in other applications too.</strong>{' '}
                {patterns.map((p) => p.summary).join(' ')}{' '}
                <Link href="/patterns" className="underline">See patterns</Link>
              </span>
            </span>
          </Notice>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-6" aria-label="Findings">
          {checks.length === 0 && <Notice>No findings yet. They appear once the documents have been read.</Notice>}
          {ORDER.map((s) => {
            const group = checks.filter((ch) => ch.status === s);
            if (!group.length) return null;
            return (
              <div key={s}>
                <h2 className="mb-2 text-base font-serif font-bold text-[#1C1917]">{STATUS_META[s].label} ({group.length})</h2>
                <ul className="space-y-3">{group.map((ch) => <CheckCard key={ch.id} check={ch} docTitle={docTitle} />)}</ul>
              </div>
            );
          })}
        </section>

        <aside className={`${card} h-fit`} aria-label="Documents">
          <h2 className="text-base font-serif font-bold text-[#1C1917]">Documents ({documents.length})</h2>
          <ul className="mt-3 space-y-2">
            {documents.map((d) => (
              <li key={d.id} className="flex items-start gap-2 text-sm">
                <FileText className="h-4 w-4 mt-0.5 shrink-0 text-[#C25E26]" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block text-stone-900">{d.title}</span>
                  <span className="block text-xs text-stone-500">
                    {humanize(d.doc_type)}{d.page_count ? ` · ${d.page_count} pages` : ''} · {formatDate(d.uploaded_at)}
                  </span>
                  {d.sha256 && <span className="block truncate font-mono text-[10px] text-stone-400" title={d.sha256}>SHA-256 {d.sha256.slice(0, 16)}…</span>}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </PageShell>
  );
}

export default function CaseFilePage() {
  return (
    <Suspense fallback={<PageShell title="Case file"><div className={`${card} h-48 animate-pulse`} /></PageShell>}>
      <CaseFileContent />
    </Suspense>
  );
}
