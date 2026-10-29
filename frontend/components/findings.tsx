'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { CircleAlert, CircleCheck, CircleDashed, Clock } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import {
  FINDING_STATUS_LABEL, SEVERITY_LABEL, humanize,
  type AuditEvent, type ExtractedField, type Finding, type FindingClauses, type FindingEvidence, type Priority, type ReviewActionKind, type StatusCard,
} from '@/lib/types';
import { documentLink } from './documents';
import { Empty, Loading, Mark, Notice, Placeholder, Skeleton, Tag, btnQuiet, btnSecondary, formatDate, formatDateInWords, formatDateTime, input, label, sheet, td, th } from './ui';

// Green ink is kept for what a person did, so a passed status is written in plain ink
const STATUS_TONE = {
  ok: { bar: 'border-t-ink', text: 'text-ink', Icon: CircleCheck },
  conflict: { bar: 'border-t-conflict', text: 'text-conflict', Icon: CircleAlert },
  pending: { bar: 'border-t-pending', text: 'text-pending', Icon: Clock },
  neutral: { bar: 'border-t-rule-strong', text: 'text-ink-3', Icon: CircleDashed },
} as const;

/** The four statuses, side by side and never added together (build spec 7.3). */
export function StatusCards({ statuses, columns = 4 }: { statuses: StatusCard[]; columns?: 2 | 4 }) {
  return (
    <ul className={`grid items-start gap-3 sm:grid-cols-2 ${columns === 4 ? 'lg:grid-cols-4' : ''}`}>
      {statuses.map((s) => {
        const { Icon } = STATUS_TONE[s.tone];
        return (
        <li key={s.key} className={`${sheet} border-t-[3px] p-4 shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent)] ${STATUS_TONE[s.tone].bar}`}>
          <p className="text-sm text-ink-2">{s.label}</p>
          <p className={`mt-1 flex items-start gap-2 font-serif text-lg font-bold leading-snug ${STATUS_TONE[s.tone].text}`}>
            <Icon aria-hidden="true" className="mt-1 size-[1.1rem] flex-none" strokeWidth={2.25} />
            {s.value}
          </p>
          {s.reasons.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-ink-2">
              {s.reasons.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
              {s.reasons.length > 4 && <li>and {s.reasons.length - 4} more</li>}
            </ul>
          )}
        </li>
        );
      })}
    </ul>
  );
}

export function StatusCardsSkeleton() {
  return (
    <Skeleton what="Loading statuses">
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <li key={i} className={`${sheet} space-y-3 border-t-[3px] border-t-rule-strong p-4`}>
            <Placeholder className="h-3 w-20" />
            <Placeholder className="h-5 w-32" />
            <Placeholder className="h-3 w-full" />
          </li>
        ))}
      </ul>
    </Skeleton>
  );
}

export function FindingsSkeleton() {
  return (
    <Skeleton what="Loading findings">
      <div className="space-y-4" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className={`${sheet} space-y-3 p-4`}>
            <div className="flex justify-between gap-4"><Placeholder className="h-4 w-2/3" /><Placeholder className="h-4 w-16" /></div>
            <Placeholder className="h-3 w-1/2" />
            <Placeholder className="h-3 w-full" />
            <div className="grid grid-cols-2 gap-3"><Placeholder className="h-12" /><Placeholder className="h-12" /></div>
          </div>
        ))}
      </div>
    </Skeleton>
  );
}

export function PriorityLedgerSkeleton() {
  return (
    <Skeleton what="Loading priority">
      <div className={`${sheet} space-y-3 p-4`} aria-hidden="true">
        <Placeholder className="h-6 w-24" />
        {[0, 1, 2].map((i) => <div key={i} className="flex justify-between gap-4"><Placeholder className="h-3 w-2/3" /><Placeholder className="h-3 w-8" /></div>)}
      </div>
    </Skeleton>
  );
}

/** The priority score worked out as a sum, so the reviewer sees how it was reached (build spec 7.4). */
export function PriorityLedger({ priority }: { priority: Priority }) {
  return (
    <div className={`${sheet} p-4`}>
      {priority.composition.length === 0 ? (
        <p className="text-sm text-ink-2">No unresolved findings, so nothing adds to the score.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">How the priority score is reached</caption>
          <tbody>
            {priority.composition.map((t) => (
              <tr key={t.key} className="border-b border-rule">
                <td className="py-1.5 pr-3">{t.label}</td>
                <td className="whitespace-nowrap py-1.5 pr-3 text-right tabular-nums text-ink-2">{t.count} × {t.weight}</td>
                <td className="w-12 py-1.5 text-right font-semibold tabular-nums">{t.contribution}</td>
              </tr>
            ))}
            {priority.capped && (
              <tr className="border-b border-rule">
                <td className="py-1.5 pr-3 text-ink-2" colSpan={2}>Capped at 100 (sum {priority.raw})</td>
                <td className="py-1.5 text-right tabular-nums text-ink-2">{100 - priority.raw}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
      <div className="ledger-rule" aria-hidden />
      <p className="mt-2 flex items-baseline justify-between gap-3">
        <span className="font-semibold">Priority {priority.band.toLowerCase()}</span>
        <span className="font-serif text-2xl font-bold tabular-nums">{priority.score}<span className="text-sm font-normal text-ink-2"> of 100</span></span>
      </p>
      <p className="mt-1 text-xs text-ink-2">Priority only orders the review queue. It never changes a status.</p>
    </div>
  );
}

export type Citation = { documentId: string; page: number | null; label: string };

/** The cited document, opened at the cited page. Links expire, so each citation asks for a fresh one. */
export function CitedPage({ citation }: { citation: Citation | null }) {
  const [view, setView] = useState<{ url: string; mime: string; key: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = citation ? `${citation.documentId}#${citation.page}` : '';

  useEffect(() => {
    if (!citation) return;
    let live = true;
    documentLink(citation.documentId).then(({ url, mime, error }) => {
      if (!live) return;
      if (url) { setView({ url, mime: mime ?? 'application/pdf', key }); setError(null); }
      else setError(error);
    });
    return () => { live = false; };
  }, [citation, key]);

  if (!citation) return <Empty>Choose a highlighted value to open the page it was read from.</Empty>;
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!view || view.key !== key) return <Loading what="Opening the document" />;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <p><span className="font-semibold">{citation.label}</span>{citation.page && <span className="text-ink-2">, page {citation.page}</span>}</p>
        <a href={view.url} target="_blank" rel="noreferrer" className={btnQuiet}>Open in a new tab</a>
      </div>
      <div className="overflow-hidden rounded-sheet border border-rule-strong bg-sheet">
        {view.mime === 'application/pdf' ? (
          <iframe key={key} src={`${view.url}#page=${citation.page ?? 1}`} title={`${citation.label}, page ${citation.page ?? 1}`} className="h-[34rem] w-full" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={view.url} alt={citation.label} className="max-h-[34rem] w-full object-contain" />
        )}
      </div>
    </div>
  );
}

function EvidenceCell({ ev, docLabel, onCite }: { ev: FindingEvidence; docLabel: (t: string) => string; onCite: (c: Citation) => void }) {
  const name = ev.document ? docLabel(ev.document.doc_type) : null;
  const cite = ev.document_id ? () => onCite({ documentId: ev.document_id!, page: ev.page_number, label: name ?? 'Document' }) : undefined;
  return (
    <div className="min-w-0">
      <p className="text-sm text-ink-2">{ev.label}</p>
      <p className="mt-0.5">
        {ev.shown_value
          ? <Mark onClick={cite} title={cite ? `Open ${name ?? 'the document'}${ev.page_number ? `, page ${ev.page_number}` : ''}` : undefined}>{ev.shown_value}</Mark>
          : <span className="text-ink-3">No value</span>}
      </p>
      {ev.document && (
        <p className="mt-1 text-xs text-ink-2">
          {name}{ev.page_number ? `, page ${ev.page_number}` : ''}{ev.document.status === 'superseded' ? ', replaced since' : ''}
        </p>
      )}
    </div>
  );
}

/** A photo cited as evidence, shown in place (links are short-lived, so each one is fetched fresh). */
function EvidencePhoto({ ev }: { ev: FindingEvidence }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    if (ev.document_id) documentLink(ev.document_id).then(({ url }) => live && setUrl(url));
    return () => { live = false; };
  }, [ev.document_id]);
  return (
    <figure className="min-w-0">
      <div className="flex aspect-[3/2] items-center justify-center overflow-hidden rounded-sheet border border-rule-strong bg-sheet">
        {url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={url} alt={ev.label ?? 'Photo cited as evidence'} className="h-full w-full object-cover" />
          : <span className="text-xs text-ink-2">Loading photo…</span>}
      </div>
      <figcaption className="mt-1 text-xs text-ink-2">{ev.label}</figcaption>
    </figure>
  );
}

const isImage = (e?: FindingEvidence) => !!e?.document?.mime?.startsWith('image/');

/** Two values that should agree are set side by side; a single piece of evidence stands alone. */
function Evidence({ evidence, docLabel, onCite, same = false }: {
  evidence: FindingEvidence[];
  docLabel: (t: string) => string;
  onCite: (c: Citation) => void;
  /** The finding is about two things that match (across institutions), not two that differ */
  same?: boolean;
}) {
  const a = evidence.find((e) => e.role === 'A');
  const b = evidence.find((e) => e.role === 'B');
  const singles = evidence.filter((e) => e.role !== 'A' && e.role !== 'B');
  return (
    <div className="space-y-3">
      {a && b && isImage(a) && isImage(b) && (
        <div className="grid gap-3 sm:grid-cols-2">
          <EvidencePhoto ev={a} />
          <EvidencePhoto ev={b} />
        </div>
      )}
      {a && b && (
        <div className="grid items-start gap-3 rounded-sheet border border-rule bg-paper p-3 sm:grid-cols-[1fr_auto_1fr]">
          <EvidenceCell ev={a} docLabel={docLabel} onCite={onCite} />
          <p className="self-center text-center text-sm font-semibold text-conflict">{same ? 'matches' : 'differs from'}</p>
          <EvidenceCell ev={b} docLabel={docLabel} onCite={onCite} />
        </div>
      )}
      {singles.length > 0 && (
        <div className="grid gap-3 rounded-sheet border border-rule bg-paper p-3 sm:grid-cols-2">
          {singles.map((e) => <EvidenceCell key={e.id} ev={e} docLabel={docLabel} onCite={onCite} />)}
        </div>
      )}
    </div>
  );
}

const ACTIONS: { kind: ReviewActionKind; button: string; submit: string; hint: string }[] = [
  { kind: 'resolve', button: 'Resolve', submit: 'Record as resolved', hint: 'Say what settles it, for example which document you checked.' },
  { kind: 'dismiss', button: 'Dismiss', submit: 'Record as dismissed', hint: 'Say why this finding does not need action.' },
  { kind: 'request_evidence', button: 'Ask for evidence', submit: 'Send the request', hint: 'The institution sees this message and the due date.' },
];

function ActionForm({ finding, onDone }: { finding: Finding; onDone: (f: Finding) => void }) {
  const [kind, setKind] = useState<ReviewActionKind | null>(null);
  const [reason, setReason] = useState('');
  const [due, setDue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chosen = ACTIONS.find((a) => a.kind === kind);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kind) return;
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<Finding>(`/findings/${finding.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: kind, reason: reason.trim(), ...(kind === 'request_evidence' && due ? { due_date: due } : {}) }),
    });
    setBusy(false);
    if (data) { setKind(null); setReason(''); setDue(''); onDone(data); }
    else setError(error);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Actions on this finding">
        {ACTIONS.map((a) => {
          const blocked = a.kind === 'request_evidence' && (finding.is_cross_institution || finding.status === 'evidence_requested');
          return (
            <button key={a.kind} type="button" disabled={blocked} aria-pressed={kind === a.kind}
              title={blocked ? (finding.is_cross_institution ? 'The institution is never told about another institution\'s records' : 'Evidence has already been requested') : undefined}
              onClick={() => { setKind(kind === a.kind ? null : a.kind); setError(null); }}
              className={`${btnSecondary} px-3 py-1.5 ${kind === a.kind ? 'border-officer bg-officer-wash text-officer' : ''}`}>
              {a.button}
            </button>
          );
        })}
      </div>
      {chosen && (
        <form onSubmit={submit} className="space-y-3 border-l-2 border-officer pl-4">
          <div>
            <label htmlFor={`reason-${finding.id}`} className={label}>Reason</label>
            <textarea id={`reason-${finding.id}`} required minLength={3} rows={3} value={reason}
              onChange={(e) => setReason(e.target.value)} className={input} aria-describedby={`hint-${finding.id}`} />
            <p id={`hint-${finding.id}`} className="mt-1 text-xs text-ink-2">{chosen.hint} A reason is required and goes into the audit trail.</p>
          </div>
          {kind === 'request_evidence' && (
            <div className="max-w-56">
              <label htmlFor={`due-${finding.id}`} className={label}>Due date (optional)</label>
              <input id={`due-${finding.id}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} />
              <p className="mt-1 text-xs text-ink-2">Left empty, it is 7 days from the as-of date.</p>
            </div>
          )}
          {error && <Notice kind="error">{error}</Notice>}
          <button type="submit" disabled={busy || reason.trim().length < 3}
            className="inline-flex items-center rounded-control bg-officer px-4 py-2 text-sm font-semibold text-sheet hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? 'Recording…' : chosen.submit}
          </button>
        </form>
      )}
    </div>
  );
}

/** Confirm a value as read, or correct it; the value as printed is always kept (build spec 11). */
export function FieldReview({ field, onDone }: { field: ExtractedField; onDone: (f: ExtractedField) => void }) {
  const [mode, setMode] = useState<'confirm' | 'correct' | null>(null);
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readAs = field.value_type === 'date' && field.field_value ? formatDateInWords(field.field_value) : field.field_value;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mode) return;
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<{ field: ExtractedField }>(`/fields/${field.id}/${mode}`, {
      method: 'POST', body: JSON.stringify(mode === 'confirm' ? { reason: reason.trim() } : { value: value.trim(), reason: reason.trim() }),
    });
    setBusy(false);
    if (data) { setMode(null); setReason(''); setValue(''); onDone(data.field); }
    else setError(error);
  };

  return (
    <div className="space-y-2 rounded-sheet border border-pending bg-pending-wash p-3 text-sm">
      <p>
        Printed as <Mark>{field.original_value ?? 'not found'}</Mark>
        {readAs && <>, read as <span className="font-semibold">{readAs}</span></>}.
        {field.review_reason && <span className="block text-ink-2">{field.review_reason}.</span>}
      </p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Check this value">
        {field.field_value && (
          <button type="button" aria-pressed={mode === 'confirm'} onClick={() => setMode(mode === 'confirm' ? null : 'confirm')}
            className={`${btnSecondary} px-3 py-1.5 ${mode === 'confirm' ? 'border-officer bg-officer-wash text-officer' : ''}`}>
            Confirm {readAs}
          </button>
        )}
        <button type="button" aria-pressed={mode === 'correct'} onClick={() => setMode(mode === 'correct' ? null : 'correct')}
          className={`${btnSecondary} px-3 py-1.5 ${mode === 'correct' ? 'border-officer bg-officer-wash text-officer' : ''}`}>
          Correct it
        </button>
      </div>
      {mode && (
        <form onSubmit={submit} className="space-y-3 border-l-2 border-officer pl-4">
          {mode === 'correct' && (
            <div className="max-w-64">
              <label htmlFor={`value-${field.id}`} className={label}>Correct value</label>
              <input id={`value-${field.id}`} required value={value} onChange={(e) => setValue(e.target.value)} className={input}
                placeholder={field.value_type === 'date' ? 'for example 8 March 2025' : undefined} />
            </div>
          )}
          <div>
            <label htmlFor={`freason-${field.id}`} className={label}>Reason</label>
            <textarea id={`freason-${field.id}`} required minLength={3} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
            <p className="mt-1 text-xs text-ink-2">Say how you checked it. The value as printed stays on record, and validation runs again.</p>
          </div>
          {error && <Notice kind="error">{error}</Notice>}
          <button type="submit" disabled={busy || reason.trim().length < 3 || (mode === 'correct' && !value.trim())}
            className="inline-flex items-center rounded-control bg-officer px-4 py-2 text-sm font-semibold text-sheet hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? 'Recording and validating…' : mode === 'confirm' ? 'Record as confirmed' : 'Record the correction'}
          </button>
        </form>
      )}
    </div>
  );
}

/** The value a "needs confirmation" finding is about, looked up from its document. */
function FindingField({ finding, onReviewed }: { finding: Finding; onReviewed: () => void }) {
  const [field, setField] = useState<ExtractedField | null>(null);
  const documentId = finding.evidence[0]?.document_id;
  const name = finding.finding_key.split('|')[2]?.split('.')[1];
  useEffect(() => {
    if (!documentId || !name) return;
    fetchApi<{ fields: ExtractedField[] }>(`/documents/${documentId}/fields`)
      .then(({ data }) => setField(data?.fields.find((f) => f.field_name === name) ?? null));
  }, [documentId, name]);
  if (!field || field.review_state !== 'needs_confirmation') return null;
  return <FieldReview field={field} onDone={onReviewed} />;
}

/** What reviewers did on a finding, in green ink. */
function ActionHistory({ finding }: { finding: Finding }) {
  if (finding.actions.length === 0 && finding.evidence_requests.length === 0) return null;
  return (
    <ol className="space-y-2 border-l-2 border-officer pl-4 text-sm">
      {finding.actions.map((a) => (
        <li key={a.id} className="text-officer">
          <span className="font-semibold">{a.action_label}</span>
          <span> by {a.actor_name ?? 'a reviewer'}, {formatDateTime(a.created_at)}</span>
          <p className="text-ink">{a.reason}</p>
        </li>
      ))}
      {finding.evidence_requests.map((r) => r.status === 'open' ? (
        <li key={r.id} className="text-pending">Waiting for the institution, due {formatDate(r.due_date)}</li>
      ) : r.status === 'fulfilled' ? (
        <li key={r.id} className="text-ink">
          The institution answered{r.fulfilled_by_document_id ? ' and sent a document' : ''}. Its note is in the audit trail.
        </li>
      ) : null)}
    </ol>
  );
}

/** The clauses the finding's rule rests on, and a draft explanation the reviewer asks for. Loaded on opening. */
function WhyThisRule({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const [found, setFound] = useState<FindingClauses | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);

  useEffect(() => {
    if (!open || found) return;
    fetchApi<FindingClauses>(`/findings/${finding.id}/clauses`).then(({ data, error }) => (data ? setFound(data) : setError(error)));
  }, [open, found, finding.id]);

  const draft = async () => {
    setDrafting(true);
    const { data, error } = await fetchApi<FindingClauses>(`/findings/${finding.id}/explanation`, { method: 'POST' });
    setDrafting(false);
    if (data) setFound(data); else setError(error ?? 'No draft');
  };

  const explanation = found?.explanation;
  return (
    <div>
      <button className={btnQuiet} aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? 'Hide the rule and its clauses' : 'Why this rule'}
      </button>
      {open && (
        <div className="mt-3 space-y-3 border-l-2 border-rule-strong pl-4">
          {error && <Notice kind="error">{error}</Notice>}
          {!found && !error && <Loading what="Finding the clauses" />}
          {found && (
            <>
              {found.rule && (
                <p className="text-sm">
                  <span className="font-semibold">{found.rule.title ?? found.rule.rule_code}</span>
                  {found.rule.description && <span className="text-ink-2">: {found.rule.description}</span>}
                </p>
              )}
              {found.clauses.length === 0 && <p className="text-sm text-ink-2">No clause in the library matches this rule yet.</p>}
              {found.clauses.map((c) => (
                <blockquote key={c.id} className="space-y-1 text-sm">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{c.clause_ref}, {c.heading}</span>
                    {c.is_illustrative && <Tag>Illustrative</Tag>}
                  </p>
                  <p>{c.body}</p>
                  <p className="text-xs text-ink-2">
                    {c.source}. {c.matched_by === 'rule' ? `Linked to rule ${finding.rule_code}.` : 'Found by keyword search; it may be related rather than the basis of the rule.'}
                  </p>
                </blockquote>
              ))}
              {found.clauses.some((c) => c.is_illustrative) && (
                <p className="text-xs text-ink-2">Illustrative clauses were written for this prototype. They are not official AICTE text.</p>
              )}
              {explanation ? (
                <div className="space-y-1 rounded-sheet border border-rule bg-sheet p-3">
                  <p className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                    <Tag tone="pending">Draft</Tag>
                    {explanation.by === 'llm' ? 'Suggested by AI' : 'Built from the record, without AI'}
                  </p>
                  <p className="text-sm">{explanation.text}</p>
                  <p className="text-xs text-ink-2">
                    {explanation.by === 'llm'
                      ? 'Written only from this finding, its evidence and the clauses above; every number in it was checked against them. '
                      : ''}
                    It explains the finding and is not a conclusion. It is not saved on the finding.
                  </p>
                </div>
              ) : (
                found.clauses.length > 0 && (
                  <button className={btnSecondary} disabled={drafting} onClick={draft}>
                    {drafting ? 'Drafting…' : 'Draft an explanation'}
                  </button>
                )
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const STATUS_TAG = {
  open: 'conflict', evidence_requested: 'pending', resolved: 'ok', dismissed: 'ok', auto_closed: 'neutral',
} as const;

export function FindingCard({ finding, docLabel, onCite, onChange, onReviewed, canAct }: {
  finding: Finding;
  docLabel: (t: string) => string;
  onCite: (c: Citation) => void;
  onChange: (f: Finding) => void;
  /** A value was confirmed or corrected, and validation ran again */
  onReviewed: () => void;
  canAct: boolean;
}) {
  const unresolved = finding.status === 'open' || finding.status === 'evidence_requested';
  return (
    <article className={`${sheet} space-y-4 p-4 shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent)] ${finding.status === 'open' ? 'margin-rule pl-9' : ''}`} aria-labelledby={`f-${finding.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 id={`f-${finding.id}`} className="font-serif text-base font-bold leading-snug">{finding.title}</h4>
        <Tag tone={STATUS_TAG[finding.status]}>{FINDING_STATUS_LABEL[finding.status]}</Tag>
      </div>
      <p className="-mt-2 text-xs text-ink-2">
        {humanize(finding.finding_type.toLowerCase())}, rule {finding.rule_code} version {finding.rule_version ?? '—'}
        {finding.severity && `, ${SEVERITY_LABEL[finding.severity].toLowerCase()} severity`}
      </p>
      <p className="text-sm">{finding.detail}</p>
      {finding.evidence.length > 0 && <Evidence evidence={finding.evidence} docLabel={docLabel} onCite={onCite} same={finding.is_cross_institution} />}
      {finding.related_application_id && (
        <Link href={`/review/${finding.related_application_id}`} className={btnQuiet}>Open the other application</Link>
      )}
      {canAct && unresolved && finding.finding_type === 'FIELD_NEEDS_CONFIRMATION' && <FindingField finding={finding} onReviewed={onReviewed} />}
      {finding.rule_code && <WhyThisRule finding={finding} />}
      <ActionHistory finding={finding} />
      {canAct && unresolved && <ActionForm finding={finding} onDone={onChange} />}
    </article>
  );
}

const EVENT_LABEL: Record<string, string> = {
  application_created: 'Application created',
  application_seeded: 'Application loaded with demo data',
  application_submitted: 'Application submitted',
  document_upload_started: 'Upload started',
  document_finalized: 'Document received',
  document_processed: 'Document read',
  document_processing_failed: 'Document could not be read',
  validation_run: 'Validation run',
  finding_resolve: 'Finding resolved',
  finding_dismiss: 'Finding dismissed',
  finding_request_evidence: 'Evidence requested',
  case_file_snapshot: 'Case File snapshot saved',
  rooms_saved: 'Room table saved',
  field_confirmed: 'Value confirmed',
  field_corrected: 'Value corrected',
  evidence_request_fulfilled: 'Institution answered a request',
  explanation_drafted: 'Explanation drafted',
};

function eventNote(e: AuditEvent): string {
  const d = e.detail ?? {};
  if (e.event_type === 'validation_run') {
    const by = d.trigger === 'document_replaced' ? 'After a replacement document was read. ' : d.trigger === 'value_confirmed' ? 'After a value was checked. ' : '';
    return `${by}${d.findings ?? 0} findings: ${d.created ?? 0} new, ${d.still_open ?? 0} still open, ${d.auto_closed ?? 0} closed. As of ${formatDate(String(d.as_of_date ?? ''))}.`;
  }
  if (e.event_type === 'evidence_request_fulfilled' && typeof d.note === 'string') return d.note;
  if (e.event_type === 'rooms_saved') return `${d.rooms ?? 0} rooms, ${d.total_sqm ?? 0} sq m`;
  if (e.event_type === 'field_corrected') return `${String(d.from ?? 'not read')} to ${String(d.to)}: ${String(d.reason ?? '')}`;
  if (e.event_type === 'explanation_drafted') return `${d.by === 'llm' ? 'Suggested by AI' : 'From the record, without AI'}; clauses ${(d.clause_refs as string[] | undefined)?.join(', ') || 'none'}`;
  if (typeof d.reason === 'string') return d.reason;
  if (typeof d.original_name === 'string') return d.original_name;
  return '';
}

/** The application's audit trail, newest first, with a check that no event was changed afterwards. */
export function AuditTrail({ applicationId, version }: { applicationId: string; version: number }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chain, setChain] = useState<{ ok: boolean; events_checked: number; broken_at_id: number | null } | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    fetchApi<AuditEvent[]>(`/audit?application_id=${applicationId}&limit=200`)
      .then(({ data, error }) => (data ? setEvents(data) : setError(error)));
  }, [applicationId, version]);

  const verify = async () => {
    setChecking(true);
    const { data, error } = await fetchApi<{ ok: boolean; events_checked: number; broken_at_id: number | null }>('/audit/verify');
    setChecking(false);
    if (data) setChain(data);
    else setError(error);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <button className={btnSecondary} onClick={verify} disabled={checking}>{checking ? 'Checking…' : 'Check the audit chain'}</button>
        {chain && (chain.ok
          ? <p className="text-sm" role="status">Chain intact: all {chain.events_checked} events still match their hashes.</p>
          : <p className="text-sm font-semibold text-conflict" role="alert">Chain broken at event {chain.broken_at_id}: it no longer matches its hash.</p>)}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!events ? <Loading what="Loading the audit trail" /> : events.length === 0 ? <Empty>No events yet.</Empty> : (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead className="sticky top-0 bg-paper">
              <tr><th className={th}>When</th><th className={th}>Event</th><th className={th}>By</th><th className={th}>Detail</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className={`${td} whitespace-nowrap`}>{formatDateTime(e.created_at)}</td>
                  <td className={td}>{EVENT_LABEL[e.event_type] ?? humanize(e.event_type)}</td>
                  <td className={td}>{e.actor_name ?? '—'}</td>
                  <td className={`${td} text-ink-2`}>{eventNote(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
