'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import {
  CATEGORY_LABEL, FINDING_TYPE_LABEL, PHOTO_CATEGORY_LABEL,
  type Application, type ApplicationDetail, type PreflightItem, type PreflightResult, type Reference, type WizardStep,
} from '@/lib/types';
import { DocumentSlot } from '@/components/prepare';
import { RoomTable } from '@/components/rooms';
import { isBeingRead } from '@/components/documents';
import { FileNumber, Loading, Mark, Notice, Tag, btnPrimary, btnQuiet, btnSecondary, formatDate, input, label } from '@/components/ui';

const STEPS: { key: WizardStep; title: string; line: string }[] = [
  { key: 'details', title: 'Details', line: 'What the application is for' },
  { key: 'documents', title: 'Documents', line: 'Upload each document and check what was read' },
  { key: 'evidence', title: 'Infrastructure', line: 'Photos, floor plan and room table' },
  { key: 'preflight', title: 'Pre-flight check', line: 'The same checks a reviewer runs within an application' },
  { key: 'submit', title: 'Submit', line: 'Send it to the reviewers' },
];
const EDITABLE = new Set(['draft', 'awaiting_institution']);
const INFRA_TYPES = new Set(['infrastructure_photo', 'floor_plan']);
const PHOTO_SLOTS = ['lab', 'classroom', 'library'];
const SEVERITY_TONE = { high: 'conflict', medium: 'pending', low: 'neutral', info: 'neutral' } as const;

function StepRail({ current, applicationId }: { current: WizardStep; applicationId: string | null }) {
  return (
    <nav aria-label="Steps" className="mb-8">
      <ol className="grid gap-2 sm:grid-cols-5">
        {STEPS.map((s, i) => {
          const here = s.key === current;
          const body = (
            <>
              <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border font-serif text-sm font-bold ${here ? 'border-ink bg-ink text-sheet' : 'border-rule-strong text-ink-2'}`}>{i + 1}</span>
              <span className="min-w-0">
                <span className={`block text-sm ${here ? 'font-bold' : 'font-semibold'}`}>{s.title}</span>
                <span className="block text-xs text-ink-2">{s.line}</span>
              </span>
            </>
          );
          const cls = `flex items-start gap-2 rounded-sheet border px-3 py-2 ${here ? 'border-ink bg-sheet' : 'border-rule'}`;
          return (
            <li key={s.key}>
              {applicationId && !here
                ? <Link href={`?application=${applicationId}&step=${s.key}`} className={`${cls} hover:bg-sheet`}>{body}</Link>
                : <div className={cls} aria-current={here ? 'step' : undefined}>{body}</div>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Details({ onCreated }: { onCreated: (a: Application) => void }) {
  const [category, setCategory] = useState<Application['category']>('extension_of_approval');
  const [year, setYear] = useState('2027-28');
  const [area, setArea] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<Application>('/applications', {
      method: 'POST',
      body: JSON.stringify({ category, academic_year: year, declared_total_area_sqm: area ? Number(area) : null }),
    });
    setBusy(false);
    if (data) onCreated(data);
    else setError(error);
  };

  return (
    <form onSubmit={create} className="max-w-2xl space-y-4 rounded-sheet border border-rule bg-sheet p-5">
      <div>
        <label htmlFor="category" className={label}>Type of application</label>
        <select id="category" className={input} value={category} onChange={(e) => setCategory(e.target.value as Application['category'])}>
          {Object.entries(CATEGORY_LABEL).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
        </select>
        <p className="mt-1 text-xs text-ink-2">The type decides which documents are required.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="year" className={label}>Academic year</label>
          <input id="year" className={input} value={year} onChange={(e) => setYear(e.target.value)} pattern="20\d{2}-\d{2}" required />
        </div>
        <div>
          <label htmlFor="area" className={label}>Declared built-up area (sq m)</label>
          <input id="area" className={input} inputMode="decimal" value={area} onChange={(e) => setArea(e.target.value)} />
          <p className="mt-1 text-xs text-ink-2">The room table should add up to this.</p>
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <button type="submit" className={btnPrimary} disabled={busy}>{busy ? 'Starting…' : 'Start the application'}</button>
    </form>
  );
}

function Preflight({ applicationId, detail, onResult, result }: {
  applicationId: string;
  detail: ApplicationDetail;
  result: PreflightResult | null;
  onResult: (r: PreflightResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reading = detail.documents.some(isBeingRead);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<PreflightResult>(`/applications/${applicationId}/preflight`, { method: 'POST' });
    setBusy(false);
    if (data) onResult(data);
    else setError(error);
  }, [applicationId, onResult]);

  // Run on arrival and after any change (an upload or the room table clears the last result)
  useEffect(() => {
    if (result || reading) return;
    const t = setTimeout(run, 0);
    return () => clearTimeout(t);
  }, [result, reading, run]);

  const docName = (id: string | null) => {
    const d = detail.documents.find((x) => x.id === id);
    return d ? d.original_name : null;
  };
  const fixHref = (i: PreflightItem) => {
    const focus = i.fix.anchor ?? (i.fix.doc_type ? `${i.fix.doc_type}${i.fix.category ? `-${i.fix.category}` : ''}` : '');
    return `?application=${applicationId}&step=${i.fix.step}${focus ? `&focus=${focus}` : ''}`;
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4">
        <button className={btnSecondary} onClick={run} disabled={busy || reading}>{busy ? 'Checking…' : result ? 'Run the check again' : 'Run the check'}</button>
        {result && <p className="text-sm text-ink-2">Checked as of {formatDate(result.as_of_date)}. Nothing from this check is stored or sent to reviewers.</p>}
      </div>
      {reading && <Notice kind="warning">Some documents are still being read. The check runs once they are done.</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {busy && !result && <Loading what="Running the checks" />}
      {result && result.items.length === 0 && (
        <Notice kind="success">Nothing to fix. Every check that can run on this application on its own passed. Reviewers run the full checks after you submit.</Notice>
      )}
      {result && result.items.length > 0 && (
        <>
          <p className="text-sm">
            <span className="font-semibold">{result.items.length} item{result.items.length > 1 ? 's' : ''} to look at</span>
            <span className="text-ink-2">, most important first. You can still submit, and a reviewer will see the same items.</span>
          </p>
          <ol className="space-y-3">
            {result.items.map((i) => (
              <li key={i.key} className="rounded-sheet border border-rule bg-sheet p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag tone={SEVERITY_TONE[i.severity as keyof typeof SEVERITY_TONE] ?? 'neutral'}>{i.severity === 'high' ? 'High' : i.severity === 'medium' ? 'Medium' : 'Low'}</Tag>
                  <span className="text-xs text-ink-2">{FINDING_TYPE_LABEL[i.finding_type] ?? i.finding_type}, rule {i.rule_code}</span>
                </div>
                <p className="mt-2 font-semibold">{i.title}</p>
                <p className="mt-1 text-sm text-ink-2">{i.detail}</p>
                {i.evidence.some((e) => e.shown_value) && (
                  <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    {i.evidence.filter((e) => e.shown_value).map((e, n) => (
                      <li key={n}>
                        <span className="text-ink-2">{e.label}</span> <Mark>{e.shown_value}</Mark>
                        {(docName(e.document_id) || e.page_number) && (
                          <span className="ml-1 text-xs text-ink-2">{[docName(e.document_id), e.page_number ? `page ${e.page_number}` : null].filter(Boolean).join(', ')}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-rule pt-3">
                  <p className="text-sm">{i.fix.hint}</p>
                  <Link href={fixHref(i)} className={btnQuiet}>Go to {STEPS.find((s) => s.key === i.fix.step)?.title.toLowerCase()}</Link>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function Wizard() {
  const params = useSearchParams();
  const router = useRouter();
  const applicationId = params.get('application');
  const step = (STEPS.some((s) => s.key === params.get('step')) ? params.get('step') : applicationId ? 'documents' : 'details') as WizardStep;
  const focus = params.get('focus');

  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [reference, setReference] = useState<Reference | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const load = useCallback(() => { setVersion((v) => v + 1); setPreflight(null); }, []);

  useEffect(() => {
    fetchApi<Reference>('/reference').then(({ data, error }) => (data ? setReference(data) : setError(error)));
  }, []);

  useEffect(() => {
    if (!applicationId) return;
    fetchApi<ApplicationDetail>(`/applications/${applicationId}`).then(({ data, error }) => (data ? setDetail(data) : setError(error)));
  }, [applicationId, version]);

  const reading = detail?.documents.some(isBeingRead) ?? false;
  useEffect(() => {
    if (!reading) return;
    const t = setInterval(() => setVersion((v) => v + 1), 2000);
    return () => clearInterval(t);
  }, [reading]);

  // A fix link lands on the document or table it names
  useEffect(() => {
    if (!focus || !detail) return;
    const el = document.getElementById(focus === 'rooms' ? 'rooms' : `slot-${focus}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [focus, detail, step]);

  const shell = (children: React.ReactNode) => (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <Link href="/institution" className={btnQuiet}>Your applications</Link>
      <div className="mb-6 mt-4 max-w-2xl">
        <h1 className="font-serif text-3xl font-bold leading-tight">
          {detail ? <>Prepare <FileNumber code={detail.application.code} /></> : 'Start a new application'}
        </h1>
        <p className="mt-2 text-ink-2">Five steps, in any order once started. Each file is checked and read as it arrives, and the pre-flight check shows what to fix before you submit.</p>
      </div>
      <StepRail current={step} applicationId={applicationId} />
      {children}
    </div>
  );

  if (error) return shell(<Notice kind="error">{error}</Notice>);
  if (!reference) return shell(<Loading what="Loading" />);
  if (!applicationId) {
    return shell(<Details onCreated={(a) => router.replace(`?application=${a.id}&step=documents`)} />);
  }
  if (!detail) return shell(<Loading what="Opening the application" />);

  const a = detail.application;
  if (!EDITABLE.has(a.workflow_status)) {
    return shell(
      <Notice kind="info">
        This application is with the reviewers, so it can no longer be changed here.{' '}
        <Link href={`/institution/applications/${a.id}`} className="font-semibold underline">Open the application</Link>
      </Notice>,
    );
  }

  const label = (code: string) => reference.document_types.find((t) => t.code === code)?.label ?? code;
  const required = new Set(reference.required_documents.filter((r) => r.category === a.category && r.mandatory).map((r) => r.doc_type));
  const documentTypes = reference.document_types.filter((t) => !INFRA_TYPES.has(t.code))
    .sort((x, y) => Number(required.has(y.code)) - Number(required.has(x.code)));
  const slot = (docType: string, text: string, isRequired: boolean, category?: string) => (
    <DocumentSlot key={`${docType}-${category ?? ''}`} applicationId={a.id} docType={docType} label={text} category={category}
      required={isRequired} documents={detail.documents} focused={focus === `${docType}${category ? `-${category}` : ''}`} onUploaded={load} />
  );
  const missing = detail.checklist.filter((c) => c.mandatory && !c.present);
  const photosMissing = PHOTO_SLOTS.filter((c) => !detail.photo_categories.includes(c));

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    const { error } = await fetchApi(`/applications/${a.id}/submit`, { method: 'POST' });
    setSubmitting(false);
    if (error) setSubmitError(error);
    else router.push(`/institution/applications/${a.id}`);
  };

  const next = (to: WizardStep, text: string) => (
    <div className="mt-8 border-t border-rule pt-5">
      <Link href={`?application=${a.id}&step=${to}`} className={btnPrimary}>{text}</Link>
    </div>
  );

  return shell(
    <>
      {step === 'details' && (
        <div className="max-w-2xl space-y-3 rounded-sheet border border-rule bg-sheet p-5">
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
            <div><dt className="text-ink-2">Type</dt><dd className="font-semibold">{CATEGORY_LABEL[a.category]}</dd></div>
            <div><dt className="text-ink-2">Academic year</dt><dd className="font-semibold">{a.academic_year}</dd></div>
            <div><dt className="text-ink-2">Declared built-up area</dt><dd className="font-semibold">{a.declared_total_area_sqm ? `${a.declared_total_area_sqm.toLocaleString('en-IN')} sq m` : 'Not given'}</dd></div>
          </dl>
          <p className="text-sm text-ink-2">These were set when the application was started. Start a new application if they are wrong.</p>
          {next('documents', 'Next: documents')}
        </div>
      )}

      {step === 'documents' && (
        <section aria-labelledby="docs" className="space-y-4">
          <h2 id="docs" className="font-serif text-xl font-bold">Documents</h2>
          <p className="max-w-2xl text-sm text-ink-2">
            PDF, JPEG or PNG. After each upload, check the values read from it; a value marked unclear or not found means a clearer copy will help.
            A new upload replaces the current one as its next version.
          </p>
          <ul className="space-y-3">{documentTypes.map((t) => slot(t.code, t.label, required.has(t.code)))}</ul>
          {next('evidence', 'Next: infrastructure')}
        </section>
      )}

      {step === 'evidence' && (
        <section aria-labelledby="infra" className="space-y-8">
          <div className="space-y-4">
            <h2 id="infra" className="font-serif text-xl font-bold">Photos and floor plan</h2>
            <p className="max-w-2xl text-sm text-ink-2">A recent photo of a lab, a classroom and the library, and the floor plan. Photos carry the date they were taken in the file.</p>
            <ul className="space-y-3">
              {PHOTO_SLOTS.map((c) => slot('infrastructure_photo', `Photo: ${PHOTO_CATEGORY_LABEL[c].toLowerCase()}`, true, c))}
              {slot('floor_plan', label('floor_plan'), true)}
            </ul>
          </div>
          <div id="rooms" className={`scroll-mt-6 space-y-3 ${focus === 'rooms' ? 'rounded-sheet outline outline-2 outline-offset-4 outline-ink' : ''}`}>
            <h2 className="font-serif text-xl font-bold">Room table</h2>
            <p className="max-w-2xl text-sm text-ink-2">Each room on the floor plan with its length and width. The areas should add up to the declared built-up area.</p>
            <RoomTable applicationId={a.id} canEdit onSaved={() => setPreflight(null)} />
          </div>
          {next('preflight', 'Next: pre-flight check')}
        </section>
      )}

      {step === 'preflight' && (
        <section aria-labelledby="pf" className="space-y-4">
          <h2 id="pf" className="font-serif text-xl font-bold">Pre-flight check</h2>
          <p className="max-w-2xl text-sm text-ink-2">
            The checks a reviewer runs within one application: required documents, dates, values that should agree, duplicates,
            infrastructure evidence and areas. Each item says what differs and where, and links to the step that fixes it.
          </p>
          <Preflight applicationId={a.id} detail={detail} result={preflight} onResult={setPreflight} />
          {next('submit', 'Next: submit')}
        </section>
      )}

      {step === 'submit' && (
        <section aria-labelledby="sub" className="max-w-2xl space-y-4">
          <h2 id="sub" className="font-serif text-xl font-bold">Submit for review</h2>
          <ul className="space-y-2 text-sm">
            <li className="flex flex-wrap items-center gap-2">
              {missing.length === 0 ? <Tag tone="ok">Complete</Tag> : <Tag tone="pending">{missing.length} missing</Tag>}
              Required documents{missing.length > 0 && `: ${missing.map((m) => m.label).join(', ')}`}
            </li>
            <li className="flex flex-wrap items-center gap-2">
              {photosMissing.length === 0 ? <Tag tone="ok">Complete</Tag> : <Tag tone="pending">{photosMissing.length} missing</Tag>}
              Photos{photosMissing.length > 0 && `: ${photosMissing.map((c) => PHOTO_CATEGORY_LABEL[c].toLowerCase()).join(', ')}`}
            </li>
            <li className="flex flex-wrap items-center gap-2">
              {preflight ? (preflight.items.length === 0 ? <Tag tone="ok">Nothing to fix</Tag> : <Tag tone="pending">{preflight.items.length} to look at</Tag>) : <Tag>Not run since the last change</Tag>}
              Pre-flight check{' '}
              <Link href={`?application=${a.id}&step=preflight`} className={btnQuiet}>{preflight ? 'See the items' : 'Run it'}</Link>
            </li>
          </ul>
          <p className="text-sm text-ink-2">
            Submitting sends the application to the scrutiny reviewers. You can no longer change its documents unless a reviewer asks you for more.
            Submitting does not decide anything: the final decision rests with an authorised AICTE official.
          </p>
          {a.workflow_status === 'awaiting_institution' ? (
            <Notice kind="info">This application is waiting for your answers to reviewers&apos; requests. <Link href={`/institution/applications/${a.id}`} className="font-semibold underline">Answer them on the application page</Link>.</Notice>
          ) : (
            <>
              {submitError && <Notice kind="error">{submitError}</Notice>}
              <button className={btnPrimary} onClick={submit} disabled={submitting || reading || detail.documents.length === 0}>
                {submitting ? 'Submitting…' : reading ? 'Wait until every document is read' : 'Submit for review'}
              </button>
            </>
          )}
        </section>
      )}
    </>,
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-5xl px-4 py-8 sm:px-6"><Loading what="Loading" /></div>}>
      <Wizard />
    </Suspense>
  );
}
