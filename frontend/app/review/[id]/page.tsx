'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import {
  PHOTO_CATEGORY_LABEL, humanize,
  type ApplicationDetail, type DocumentRow, type ExtractedField, type FacultyRow, type Finding, type Priority,
  type Reference, type StatusView, type ValidateResult,
} from '@/lib/types';
import { Checklist, FileCover } from '@/components/FileCover';
import { FileCheckTag, ReadingTag, documentLink, isBeingRead } from '@/components/documents';
import { AuditTrail, CitedPage, FindingCard, PriorityLedger, StatusCards, type Citation } from '@/components/findings';
import { Empty, Loading, Mark, Notice, Tag, btnPrimary, btnQuiet, formatDate, formatDateTime, td, th, useMe } from '@/components/ui';

type View = { url: string; mime: string; page: number | null };

function howRead(f: ExtractedField) {
  if (f.source_method === 'OCR') return f.confidence != null ? `OCR, ${Math.round(f.confidence * 100)}% confidence` : 'OCR';
  if (f.source_method === 'PDF_TEXT') return 'PDF text';
  if (f.source_method === 'MANUAL') return 'Entered by a reviewer';
  return '—';
}

/** The values read from one document. A highlighted value opens the page it was read from. */
function Values({ fields, faculty, onPage }: { fields: ExtractedField[]; faculty: FacultyRow[]; onPage: (page: number) => void }) {
  if (fields.length === 0 && faculty.length === 0) {
    return <Empty>No values are read from this kind of document.</Empty>;
  }
  return (
    <div className="space-y-8">
      {fields.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[38rem] border-collapse">
            <thead>
              <tr>
                <th className={th}>Value</th>
                <th className={th}>As read</th>
                <th className={th}>Page</th>
                <th className={th}>How it was read</th>
                <th className={th}>State</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.id}>
                  <td className={`${td} font-semibold`}>{humanize(f.field_name)}</td>
                  <td className={td}>
                    {f.original_value
                      ? <Mark onClick={f.page_number ? () => onPage(f.page_number!) : undefined} title={f.page_number ? `Show page ${f.page_number}` : undefined}>{f.original_value}</Mark>
                      : <span className="text-ink-3">Not found</span>}
                    {f.field_value && f.field_value !== f.original_value && <p className="mt-1 text-xs text-ink-2">Compared as {f.field_value}</p>}
                  </td>
                  <td className={td}>{f.page_number ?? '—'}</td>
                  <td className={td}>{howRead(f)}</td>
                  <td className={td}>
                    {f.review_state === 'needs_confirmation' ? <Tag tone="pending">Needs confirmation</Tag>
                      : f.review_state === 'confirmed' ? <Tag tone="ok">Confirmed</Tag>
                      : f.review_state === 'corrected' ? <Tag tone="ok">Corrected</Tag>
                      : <Tag>Read</Tag>}
                    {f.review_reason && <p className="mt-1 max-w-64 text-xs text-ink-2">{f.review_reason}</p>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {faculty.length > 0 && (
        <div>
          <h3 className="mb-2 font-semibold">Faculty listed ({faculty.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] border-collapse">
              <thead>
                <tr>
                  <th className={th}>Code</th>
                  <th className={th}>Name</th>
                  <th className={th}>Designation</th>
                  <th className={th}>Qualification</th>
                  <th className={th}>ID</th>
                  <th className={th}>Period</th>
                </tr>
              </thead>
              <tbody>
                {faculty.map((p) => (
                  <tr key={p.id}>
                    <td className={td}>{p.faculty_code}</td>
                    <td className={td}><Mark onClick={p.page_number ? () => onPage(p.page_number!) : undefined}>{p.name_raw}</Mark></td>
                    <td className={td}>{p.designation}</td>
                    <td className={td}>{p.qualification}</td>
                    <td className={`${td} tabular-nums`}>{p.masked_id}</td>
                    <td className={td}>{formatDate(p.period_start)} to {p.period_end ? formatDate(p.period_end) : 'now'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function PhotoDetails({ doc }: { doc: DocumentRow }) {
  if (!doc.photo) return null;
  const p = doc.photo;
  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-4">
      <div><dt className="text-ink-2">Shows</dt><dd className="font-semibold">{PHOTO_CATEGORY_LABEL[doc.photo_category ?? ''] ?? '—'}</dd></div>
      <div><dt className="text-ink-2">Taken</dt><dd className="font-semibold">{p.taken_at ? formatDateTime(p.taken_at) : 'No date in the file'}</dd></div>
      <div><dt className="text-ink-2">Size</dt><dd className="font-semibold">{p.width} × {p.height} px</dd></div>
      <div><dt className="text-ink-2">Visual fingerprint</dt><dd className="font-semibold tabular-nums">{p.phash ?? '—'}</dd></div>
      {p.gps && <div><dt className="text-ink-2">Location in the file</dt><dd className="font-semibold">{p.gps.lat}, {p.gps.lon}</dd></div>}
    </dl>
  );
}

const CLOSED = new Set(['resolved', 'dismissed', 'auto_closed']);

function FindingGroup({ title, id, findings, empty, onChange, ...card }: {
  title: string;
  id: string;
  findings: Finding[];
  empty: string;
  docLabel: (t: string) => string;
  onCite: (c: Citation) => void;
  onChange: (f: Finding) => void;
  canAct: boolean;
}) {
  const [showClosed, setShowClosed] = useState(false);
  // A finding the reviewer just closed stays where it was, so they see their action recorded
  const [justActed, setJustActed] = useState<Set<string>>(new Set());
  const inPlace = (f: Finding) => !CLOSED.has(f.status) || justActed.has(f.id);
  const open = findings.filter(inPlace);
  const closed = findings.filter((f) => !inPlace(f));
  const unresolved = findings.filter((f) => !CLOSED.has(f.status)).length;
  const acted = (f: Finding) => { setJustActed((s) => new Set(s).add(f.id)); onChange(f); };
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h3 id={id} className="font-serif text-lg font-bold">
        {title} <span className="font-sans text-base font-normal text-ink-2">({unresolved} unresolved)</span>
      </h3>
      {open.length === 0 && <p className="text-sm text-ink-2">{empty}</p>}
      {open.map((f) => <FindingCard key={f.id} finding={f} onChange={acted} {...card} />)}
      {closed.length > 0 && (
        <button className={btnQuiet} onClick={() => setShowClosed((v) => !v)} aria-expanded={showClosed}>
          {showClosed ? 'Hide' : 'Show'} {closed.length} closed finding{closed.length > 1 ? 's' : ''}
        </button>
      )}
      {showClosed && closed.map((f) => <FindingCard key={f.id} finding={f} onChange={acted} {...card} />)}
    </section>
  );
}

function ReviewApplication() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [types, setTypes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<DocumentRow | null>(null);
  const [values, setValues] = useState<{ fields: ExtractedField[]; faculty: FacultyRow[] } | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [viewError, setViewError] = useState<string | null>(null);
  const [showOld, setShowOld] = useState(false);
  const { me } = useMe();

  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [statusView, setStatusView] = useState<StatusView | null>(null);
  const [priority, setPriority] = useState<Priority | null>(null);
  const [citation, setCitation] = useState<Citation | null>(null);
  const [running, setRunning] = useState(false);
  const [runNote, setRunNote] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);
  // Bumped after validation or a reviewer action: statuses, priority, findings and the audit trail reload
  const [review, setReview] = useState(0);

  useEffect(() => {
    fetchApi<ApplicationDetail>(`/applications/${id}`).then(({ data, error }) => (data ? setDetail(data) : setError(error)));
  }, [id, version, review]);

  useEffect(() => {
    fetchApi<Finding[]>(`/applications/${id}/findings`).then(({ data }) => setFindings(data ?? []));
    fetchApi<StatusView>(`/applications/${id}/statuses`).then(({ data }) => data && setStatusView(data));
    fetchApi<Priority>(`/applications/${id}/priority`).then(({ data }) => data && setPriority(data));
  }, [id, review]);

  const runValidation = async () => {
    setRunning(true);
    setRunNote(null);
    const { data, error } = await fetchApi<ValidateResult>(`/applications/${id}/validate`, { method: 'POST' });
    setRunning(false);
    if (!data) return setRunNote({ kind: 'error', text: error ?? 'Validation could not run' });
    const s = data.summary;
    setRunNote({
      kind: 'success',
      text: `Validation finished: ${s.findings} finding${s.findings === 1 ? '' : 's'}, ${s.created} new, ${s.still_open} still open, ${s.auto_closed} closed because the condition no longer holds.`,
    });
    setReview((v) => v + 1);
  };

  const onChange = (f: Finding) => {
    setFindings((all) => all?.map((x) => (x.id === f.id ? f : x)) ?? null);
    setReview((v) => v + 1);
  };

  const cite = (c: Citation) => {
    setCitation(c);
    // On a narrow screen the viewer sits below the findings
    if (window.matchMedia('(max-width: 1023px)').matches) document.getElementById('cited-page')?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    fetchApi<Reference>('/reference').then(({ data }) => data && setTypes(Object.fromEntries(data.document_types.map((t) => [t.code, t.label]))));
  }, []);

  // Links expire after a few minutes, so every page jump asks for a fresh one
  const show = useCallback(async (doc: DocumentRow, page: number | null) => {
    setViewError(null);
    const { url, mime, error } = await documentLink(doc.id);
    if (url) setView({ url, mime: mime ?? doc.mime, page });
    else setViewError(error);
  }, []);

  const select = useCallback(async (doc: DocumentRow) => {
    setSelected(doc);
    setValues(null);
    setView(null);
    if (doc.integrity_status === 'pending') return;
    show(doc, 1);
    const [fields, full] = await Promise.all([
      fetchApi<{ fields: ExtractedField[]; faculty: FacultyRow[] }>(`/documents/${doc.id}/fields`),
      fetchApi<DocumentRow>(`/documents/${doc.id}`),
    ]);
    setValues(fields.data ?? { fields: [], faculty: [] });
    if (full.data) setSelected(full.data);
  }, [show]);

  if (error) return <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><Notice kind="error">{error}</Notice></div>;
  if (!detail) return <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><Loading what="Opening the application" /></div>;

  const docLabel = (t: string) => types[t] ?? humanize(t);
  const canAct = me?.role === 'reviewer';
  const lastRun = statusView?.last_run ?? null;
  const documents = detail.documents.filter((d) => showOld || d.status === 'current');
  const superseded = detail.documents.length - detail.documents.filter((d) => d.status === 'current').length;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-10 px-4 py-8 sm:px-6">
      <div>
        <Link href="/review" className={btnQuiet}>Applications</Link>
        <div className="mt-4">
          <FileCover detail={detail}>
            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
              {canAct && (
                <button className={btnPrimary} onClick={runValidation} disabled={running || detail.application.workflow_status === 'draft'}>
                  {running ? 'Running validation…' : lastRun ? 'Run validation again' : 'Run validation'}
                </button>
              )}
              <p className="text-sm text-ink-2">
                {detail.application.workflow_status === 'draft' ? 'The institution has not submitted this application yet.'
                  : lastRun ? `Last run ${formatDateTime(lastRun.started_at)}, checked as of ${formatDate(lastRun.as_of_date)}.`
                  : 'Validation has not run on this application yet.'}
              </p>
              {canAct && <Link href={`/review/${id}/casefile`} className={btnQuiet}>Case File</Link>}
            </div>
            {runNote && <div className="mt-3"><Notice kind={runNote.kind}>{runNote.text}</Notice></div>}
          </FileCover>
        </div>
      </div>

      <section aria-labelledby="statuses" className="space-y-3">
        <h2 id="statuses" className="font-serif text-xl font-bold">Where this application stands</h2>
        <p className="text-sm text-ink-2">Four separate statuses. They are never added together, and none of them is the decision.</p>
        {statusView ? <StatusCards statuses={statusView.statuses} /> : <Loading what="Loading statuses" />}
      </section>

      <section aria-labelledby="findings" className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="min-w-0 space-y-8">
          <div>
            <h2 id="findings" className="font-serif text-xl font-bold">Findings</h2>
            <p className="mt-1 text-sm text-ink-2">Each finding says what differs and where. Choose a highlighted value to open its page.</p>
          </div>
          {!findings ? <Loading what="Loading findings" /> : !lastRun && findings.length === 0 ? (
            <Empty>No findings yet. Run validation to check the documents against the rules and against each other.</Empty>
          ) : (
            <>
              <FindingGroup id="within" title="Within this application" empty="Nothing unresolved within this application."
                findings={findings.filter((f) => !f.is_cross_institution)} docLabel={docLabel} onCite={cite} onChange={onChange} canAct={canAct} />
              <FindingGroup id="across" title="Across institutions" empty="No flags across institutions. These checks are not part of this build yet."
                findings={findings.filter((f) => f.is_cross_institution)} docLabel={docLabel} onCite={cite} onChange={onChange} canAct={canAct} />
            </>
          )}
        </div>
        <aside className="space-y-8 lg:sticky lg:top-4 lg:self-start">
          <div id="cited-page" className="scroll-mt-4">
            <h3 className="mb-2 font-serif text-lg font-bold">Cited page</h3>
            <CitedPage citation={citation} />
          </div>
          <div>
            <h3 className="mb-2 font-serif text-lg font-bold">Review priority</h3>
            {priority ? <PriorityLedger priority={priority} /> : <Loading what="Loading priority" />}
          </div>
          {lastRun?.rule_versions && (
            <div>
              <h3 className="mb-2 font-serif text-lg font-bold">Rules used in the last run</h3>
              <ul className="flex flex-wrap gap-1.5">
                {Object.entries(lastRun.rule_versions).sort(([a], [b]) => a.localeCompare(b)).map(([code, v]) => <li key={code}><Tag>{code} v{v}</Tag></li>)}
              </ul>
            </div>
          )}
        </aside>
      </section>

      <Checklist detail={detail} />

      <section aria-labelledby="documents" className="grid gap-8 lg:grid-cols-[20rem_1fr]">
        <div>
          <h2 id="documents" className="font-serif text-xl font-bold">Documents</h2>
          {detail.documents.some(isBeingRead) && (
            <p className="mt-1 text-sm text-pending">Some documents are still being read. <button className={btnQuiet} onClick={load}>Refresh</button></p>
          )}
          {documents.length === 0 ? (
            <div className="mt-3"><Empty>The institution has not uploaded any documents yet.</Empty></div>
          ) : (
            <ul className="mt-3 border-t border-rule">
              {documents.map((d) => (
                <li key={d.id}>
                  <button onClick={() => select(d)} aria-current={selected?.id === d.id ? 'true' : undefined}
                    className={`w-full border-b border-rule px-3 py-3 text-left ${selected?.id === d.id ? 'bg-ink-wash' : 'hover:bg-sheet'}`}>
                    <span className="block font-semibold">
                      {types[d.doc_type] ?? humanize(d.doc_type)}
                      {d.photo_category && <span className="font-normal">, {PHOTO_CATEGORY_LABEL[d.photo_category] ?? d.photo_category}</span>}
                    </span>
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      <FileCheckTag doc={d} />
                      <ReadingTag doc={d} />
                      {d.version > 1 && <Tag>Version {d.version}</Tag>}
                      {d.status === 'superseded' && <Tag>Replaced</Tag>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {superseded > 0 && (
            <button className={`${btnQuiet} mt-3`} onClick={() => setShowOld((v) => !v)}>
              {showOld ? 'Hide replaced versions' : `Show ${superseded} replaced version${superseded > 1 ? 's' : ''}`}
            </button>
          )}
        </div>

        <div className="min-w-0">
          {!selected ? (
            <Empty>Choose a document to see it beside the values read from it.</Empty>
          ) : (
            <div className="space-y-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div>
                  <h3 className="font-serif text-lg font-bold">{types[selected.doc_type] ?? humanize(selected.doc_type)}</h3>
                  <p className="text-sm text-ink-2">
                    {selected.original_name}, version {selected.version}, uploaded {formatDateTime(selected.uploaded_at)}
                  </p>
                </div>
                {view && <a href={view.url} target="_blank" rel="noreferrer" className={btnQuiet}>Open in a new tab</a>}
              </div>

              {selected.integrity_status === 'failed' && (
                <Notice kind="error">This file failed the file check, so it is not read or used: {selected.integrity_note}</Notice>
              )}
              {selected.sha256 && (
                <p className="text-xs text-ink-2">SHA-256 fingerprint <span className="break-all tabular-nums text-ink">{selected.sha256}</span></p>
              )}

              {viewError && <Notice kind="error">{viewError}</Notice>}
              {view && (
                <div className="overflow-hidden rounded-sheet border border-rule-strong bg-sheet">
                  {view.mime === 'application/pdf' ? (
                    <iframe key={`${view.url}#${view.page}`} src={`${view.url}#page=${view.page ?? 1}`}
                      title={`${selected.original_name}, page ${view.page ?? 1}`} className="h-[36rem] w-full" />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={view.url} alt={`${types[selected.doc_type] ?? 'Document'} uploaded by the institution`} className="max-h-[36rem] w-full object-contain" />
                  )}
                </div>
              )}
              {view?.page && view.mime === 'application/pdf' && <p className="text-sm text-ink-2">Showing page {view.page}.</p>}

              <PhotoDetails doc={selected} />

              {selected.integrity_status === 'passed' && (
                <div>
                  <h3 className="mb-3 font-serif text-lg font-bold">Values read from this document</h3>
                  {selected.processing_status === 'error' && <Notice kind="warning">{selected.processing_note}</Notice>}
                  {!values ? <Loading what="Loading values" /> : <Values {...values} onPage={(page) => show(selected, page)} />}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section aria-labelledby="audit" className="space-y-3">
        <h2 id="audit" className="font-serif text-xl font-bold">Audit trail</h2>
        <p className="text-sm text-ink-2">Every step on this application, newest first. Each event is chained to the one before it by a hash, so a changed event shows up.</p>
        <AuditTrail applicationId={id} version={review} />
      </section>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><Loading what="Opening the application" /></div>}>
      <ReviewApplication />
    </Suspense>
  );
}
