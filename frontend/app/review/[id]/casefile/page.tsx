'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { CATEGORY_LABEL, FINDING_STATUS_LABEL, WORKFLOW_LABEL, humanize, type CaseFile } from '@/lib/types';
import { Empty, FileNumber, Loading, Mark, Notice, Tag, btnPrimary, btnQuiet, btnSecondary, formatDate, formatDateTime, td, th } from '@/components/ui';

type Snapshot = { id: string; created_at: string };

const VERIFY_LABEL: Record<string, string> = { SIGNATURE: 'Signature', REGISTRY: 'Issuer registry', MANUAL: 'Manual check' };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="break-inside-avoid-page space-y-3">
      <h2 className="border-b border-rule-strong pb-1 font-serif text-lg font-bold">{title}</h2>
      {children}
    </section>
  );
}

function CaseFileView() {
  const { id } = useParams<{ id: string }>();
  const [file, setFile] = useState<CaseFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    fetchApi<CaseFile>(`/applications/${id}/casefile`).then(({ data, error }) => (data ? setFile(data) : setError(error)));
  }, [id]);

  useEffect(() => {
    fetchApi<Snapshot[]>(`/applications/${id}/casefile/snapshots`).then(({ data }) => data && setSnapshots(data));
  }, [id, version]);

  const save = async () => {
    setSaving(true);
    setSaved(null);
    const { data, error } = await fetchApi<Snapshot>(`/applications/${id}/casefile/snapshot`, { method: 'POST' });
    setSaving(false);
    if (data) { setSaved(`Snapshot saved ${formatDateTime(data.created_at)}. It is kept unchanged and noted in the audit trail.`); setVersion((v) => v + 1); }
    else setError(error);
  };

  if (error && !file) return <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6"><Notice kind="error">{error}</Notice></div>;
  if (!file) return <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6"><Loading what="Putting the Case File together" /></div>;

  const { application: a, institution, latest_run: run } = file;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 py-8 sm:px-6 print:max-w-none print:px-0 print:py-0">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href={`/review/${id}`} className={btnQuiet}>Back to the case</Link>
        <div className="flex flex-wrap gap-2">
          <button className={btnSecondary} onClick={() => window.print()}>Print</button>
          <button className={btnPrimary} onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save snapshot'}</button>
        </div>
      </div>
      <div className="print:hidden space-y-2">
        {saved && <Notice kind="success">{saved}</Notice>}
        {error && <Notice kind="error">{error}</Notice>}
        {snapshots.length > 0 && (
          <p className="text-sm text-ink-2">
            {snapshots.length} snapshot{snapshots.length > 1 ? 's' : ''} saved, latest {formatDateTime(snapshots[0].created_at)}.
          </p>
        )}
      </div>

      <header className="ledger-rule pb-5">
        <p className="text-sm text-ink-2">Case File</p>
        <h1 className="mt-1 text-3xl"><FileNumber code={a.code} /></h1>
        <p className="mt-2 text-lg"><span className="font-semibold">{institution.name}</span><span className="text-ink-2">, {institution.city}</span></p>
        <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
          <div><dt className="text-ink-2">Type</dt><dd className="font-semibold">{CATEGORY_LABEL[a.category]}</dd></div>
          <div><dt className="text-ink-2">Academic year</dt><dd className="font-semibold">{a.academic_year}</dd></div>
          <div><dt className="text-ink-2">Workflow</dt><dd className="font-semibold">{WORKFLOW_LABEL[a.workflow_status]}</dd></div>
          <div><dt className="text-ink-2">Submitted</dt><dd className="font-semibold">{formatDate(a.submitted_at)}</dd></div>
          <div><dt className="text-ink-2">Review due</dt><dd className="font-semibold">{formatDate(a.review_deadline)}</dd></div>
          <div><dt className="text-ink-2">Last validation</dt><dd className="font-semibold">{run ? formatDateTime(run.started_at) : 'Not run yet'}</dd></div>
          <div><dt className="text-ink-2">Checked as of</dt><dd className="font-semibold">{run ? formatDate(run.as_of_date) : '—'}</dd></div>
          <div><dt className="text-ink-2">Priority</dt><dd className="font-semibold">{file.priority.band}, {file.priority.score} of 100</dd></div>
        </dl>
      </header>

      <Section title="Statuses">
        <table className="w-full border-collapse">
          <tbody>
            {file.statuses.statuses.map((s) => (
              <tr key={s.key}>
                <td className={`${td} w-40 font-semibold`}>{s.label}</td>
                <td className={td}>
                  <span className={s.tone === 'conflict' ? 'font-semibold text-conflict' : s.tone === 'pending' ? 'font-semibold text-pending' : 'font-semibold'}>{s.value}</span>
                  {s.reasons.length > 0 && <ul className="mt-1 list-disc pl-5 text-ink-2">{s.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
                </td>
              </tr>
            ))}
            <tr>
              <td className={`${td} font-semibold`}>Administrative</td>
              <td className={`${td} font-semibold`}>{file.statuses.administrative}</td>
            </tr>
          </tbody>
        </table>
      </Section>

      <Section title={`Findings (${file.findings.length})`}>
        {file.findings.length === 0 ? <Empty>No findings.</Empty> : (
          <ol className="space-y-4">
            {file.findings.map((f) => (
              <li key={f.id} className="break-inside-avoid border-b border-rule pb-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-semibold">{f.title}</h3>
                  <Tag tone={f.status === 'open' ? 'conflict' : f.status === 'evidence_requested' ? 'pending' : 'neutral'}>{FINDING_STATUS_LABEL[f.status]}</Tag>
                </div>
                <p className="text-xs text-ink-2">
                  Rule {f.rule_code} version {f.rule_version ?? '—'}, {humanize(f.finding_type.toLowerCase())}
                  {f.is_cross_institution && ', across institutions'}
                </p>
                <p className="mt-1 text-sm">{f.detail}</p>
                {f.evidence.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm">
                    {f.evidence.map((e) => (
                      <li key={e.id}>
                        <span className="text-ink-2">{e.label}: </span>
                        {e.shown_value ? <Mark>{e.shown_value}</Mark> : '—'}
                        {e.document && <span className="text-ink-2"> ({e.document.original_name}, version {e.document.version}{e.page_number ? `, page ${e.page_number}` : ''})</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Documents and verification">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead><tr><th className={th}>Document</th><th className={th}>Version</th><th className={th}>File check</th><th className={th}>Verification</th><th className={th}>SHA-256</th></tr></thead>
            <tbody>
              {file.documents.map((d) => (
                <tr key={d.id} className={d.status === 'superseded' ? 'text-ink-2' : ''}>
                  <td className={td}>{d.label}<span className="block text-xs text-ink-2">{d.original_name}</span></td>
                  <td className={td}>{d.version}{d.status === 'superseded' && ', replaced'}</td>
                  <td className={td}>{d.integrity_status === 'passed' ? 'Passed' : d.integrity_status === 'failed' ? `Failed: ${d.integrity_note ?? ''}` : 'Not checked'}</td>
                  <td className={td}>
                    {d.verification.length === 0 ? 'Not yet verified' : d.verification.map((v, i) => (
                      <span key={i} className="block">{VERIFY_LABEL[v.method] ?? humanize(v.method.toLowerCase())}: {humanize(v.status)}{v.is_mock && ' (MOCK)'}</span>
                    ))}
                  </td>
                  <td className={`${td} max-w-40 break-all text-xs tabular-nums`}>{d.sha256 ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Reviewer actions">
        {file.reviewer_actions.length === 0 ? <p className="text-sm text-ink-2">No reviewer actions yet.</p> : (
          <ol className="space-y-2 text-sm">
            {file.reviewer_actions.map((x) => (
              <li key={x.id} className="border-l-2 border-officer pl-3">
                <span className="font-semibold text-officer">{x.action_label}</span>
                <span className="text-ink-2"> by {x.actor_name ?? 'a reviewer'}, {formatDateTime(x.created_at)}, on {x.finding_title}</span>
                <p>Reason: {x.reason}</p>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Rule versions of the latest run">
        {file.rule_versions.length === 0 ? <p className="text-sm text-ink-2">Validation has not run yet.</p> : (
          <table className="w-full border-collapse">
            <tbody>
              {file.rule_versions.map((r) => (
                <tr key={r.rule_code}>
                  <td className={`${td} w-32 font-semibold`}>{r.rule_code}</td>
                  <td className={`${td} w-24`}>Version {r.version}</td>
                  <td className={td}>{r.title}{r.note && <span className="block text-xs text-ink-2">{r.note}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <footer className="space-y-3 border-t-[3px] border-double border-rule-strong pt-4">
        <p className="font-serif text-lg font-bold">{file.final_decision}</p>
        {file.disclaimers.map((d) => <p key={d} className="text-sm text-ink-2">{d}</p>)}
      </footer>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl px-4 py-8 sm:px-6"><Loading what="Putting the Case File together" /></div>}>
      <CaseFileView />
    </Suspense>
  );
}
