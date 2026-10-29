'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import { FINDING_TYPE_LABEL, WORKFLOW_LABEL, type QueueRow, type WorkflowStatus } from '@/lib/types';
import { PriorityLedger } from '@/components/findings';
import { Empty, FileNumber, Notice, PageShell, Placeholder, Skeleton, Tag, btnQuiet, formatDate, formatDateTime, input, label, td, th } from '@/components/ui';

const BAND_TONE = { High: 'conflict', Medium: 'pending', Low: 'neutral' } as const;

function Due({ row }: { row: QueueRow }) {
  const days = row.priority.days_to_deadline;
  return (
    <>
      {formatDate(row.application.review_deadline)}
      {days != null && (
        <p className={`text-xs ${days <= 7 ? 'font-semibold text-conflict' : 'text-ink-2'}`}>
          {days < 0 ? `${-days} day${days === -1 ? '' : 's'} overdue` : days === 0 ? 'due today' : `in ${days} day${days === 1 ? '' : 's'}`}
        </p>
      )}
    </>
  );
}

export default function ReviewQueue() {
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [band, setBand] = useState('');
  const [workflow, setWorkflow] = useState('');
  const [findingType, setFindingType] = useState('');
  const [institution, setInstitution] = useState('');
  const [all, setAll] = useState<QueueRow[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  // The unfiltered queue fills the filter choices; the filtered one is what the table shows
  useEffect(() => {
    fetchApi<QueueRow[]>('/queue').then(({ data }) => data && setAll(data));
  }, []);

  useEffect(() => {
    const q = new URLSearchParams();
    if (band) q.set('band', band);
    if (workflow) q.set('workflow_status', workflow);
    if (findingType) q.set('finding_type', findingType);
    if (institution) q.set('institution_id', institution);
    fetchApi<QueueRow[]>(`/queue${q.size ? `?${q}` : ''}`).then(({ data, error }) => {
      setRows(data);
      setError(error);
    });
  }, [band, workflow, findingType, institution]);

  const institutions = useMemo(() => {
    const seen = new Map<string, string>();
    all.forEach((r) => seen.set(r.institution.id, `${r.institution.name} (${r.institution.code})`));
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [all]);
  const types = useMemo(() => [...new Set(all.flatMap((r) => r.finding_types))].sort(), [all]);
  const filtered = band || workflow || findingType || institution;

  return (
    <PageShell
      wide
      title="Review queue"
      description="Submitted applications, highest review priority first. Priority only orders the queue; open a file to see why."
      actions={<Link href="/review/cross" className={btnQuiet}>Flags across institutions</Link>}
    >
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="search" aria-label="Filter the queue">
        <div>
          <label htmlFor="band" className={label}>Priority</label>
          <select id="band" className={input} value={band} onChange={(e) => setBand(e.target.value)}>
            <option value="">Any</option>
            <option>High</option><option>Medium</option><option>Low</option>
          </select>
        </div>
        <div>
          <label htmlFor="workflow" className={label}>Status</label>
          <select id="workflow" className={input} value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
            <option value="">Any</option>
            {(['submitted', 'under_review', 'awaiting_institution', 'review_complete'] as WorkflowStatus[]).map((w) => (
              <option key={w} value={w}>{WORKFLOW_LABEL[w]}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="type" className={label}>Has a finding of type</label>
          <select id="type" className={input} value={findingType} onChange={(e) => setFindingType(e.target.value)}>
            <option value="">Any</option>
            {types.map((t) => <option key={t} value={t}>{FINDING_TYPE_LABEL[t] ?? t}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="institution" className={label}>Institution</label>
          <select id="institution" className={input} value={institution} onChange={(e) => setInstitution(e.target.value)}>
            <option value="">Any</option>
            {institutions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {!rows && !error && (
        <Skeleton what="Ordering the queue">
          <div className="overflow-hidden rounded-sheet border border-rule bg-sheet" aria-hidden="true">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="grid grid-cols-[6rem_1fr_1fr_6rem] items-center gap-4 border-b border-rule px-3 py-4 last:border-b-0">
                <Placeholder className="h-6 w-14" />
                <div className="space-y-2"><Placeholder className="h-4 w-40" /><Placeholder className="h-3 w-56 max-w-full" /></div>
                <Placeholder className="h-3 w-3/4" />
                <Placeholder className="h-3 w-16" />
              </div>
            ))}
          </div>
        </Skeleton>
      )}
      {rows && rows.length === 0 && (
        <Empty>{filtered ? 'No application matches these filters.' : 'Nothing to review yet. Applications appear here once institutions submit them.'}</Empty>
      )}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-sheet border border-rule bg-sheet shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent)]">
          <table className="w-full min-w-[56rem] border-collapse">
            <caption className="sr-only">Applications ordered by review priority</caption>
            <thead>
              <tr>
                <th className={`${th} w-28`}>Priority</th>
                <th className={th}>File</th>
                <th className={th}>Unresolved findings</th>
                <th className={th}>Review due</th>
                <th className={th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const id = r.application.id;
                return (
                  <React.Fragment key={id}>
                    <tr className="transition-colors hover:bg-paper">
                      <td className={td}>
                        <p className="font-serif text-2xl font-bold leading-none tabular-nums">{r.priority.score}</p>
                        <p className="mt-1"><Tag tone={BAND_TONE[r.priority.band]}>{r.priority.band}</Tag></p>
                        <button className={`${btnQuiet} -ml-2 mt-1 text-xs`} aria-expanded={open === id} aria-controls={`why-${id}`}
                          onClick={() => setOpen(open === id ? null : id)}>
                          {open === id ? 'Hide the sum' : 'Show the sum'}
                        </button>
                      </td>
                      <td className={td}>
                        <Link href={`/review/${id}`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                          <FileNumber code={r.application.code} />
                        </Link>
                        <p className="text-sm">{r.institution.name}<span className="text-ink-2">, {r.institution.city}</span></p>
                      </td>
                      <td className={td}>
                        {!r.last_run_at ? <Tag>Not validated yet</Tag> : r.priority.unresolved === 0 ? (
                          <span className="text-ink-2">None</span>
                        ) : (
                          <>
                            <p className="font-semibold">{r.priority.unresolved}</p>
                            <ul className="mt-1 flex flex-wrap gap-1">
                              {r.finding_types.map((t) => <li key={t}><Tag>{FINDING_TYPE_LABEL[t] ?? t}</Tag></li>)}
                            </ul>
                            {r.cross_flags > 0 && <p className="mt-1 text-xs font-semibold text-conflict">{r.cross_flags} across institutions</p>}
                          </>
                        )}
                        {r.last_run_at && <p className="mt-1 text-xs text-ink-2">Validated {formatDateTime(r.last_run_at)}</p>}
                      </td>
                      <td className={td}><Due row={r} /></td>
                      <td className={td}><Tag tone="active">{WORKFLOW_LABEL[r.application.workflow_status]}</Tag></td>
                    </tr>
                    {open === id && (
                      <tr id={`why-${id}`}>
                        <td colSpan={5} className="border-b border-rule bg-paper px-3 py-3">
                          <div className="max-w-md"><PriorityLedger priority={r.priority} /></div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
