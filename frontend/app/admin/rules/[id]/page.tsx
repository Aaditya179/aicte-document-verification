'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { FINDING_TYPE_LABEL, humanize, ruleStage, type ParamSpec, type Rule, type RuleDetail, type RuleImpact } from '@/lib/types';
import { paramsText } from '@/components/rules';
import {
  Empty, Loading, Notice, PageShell, Tag, btnPrimary, btnQuiet, btnSecondary, formatDate, formatDateTime, input, label, td, th, useMe,
} from '@/components/ui';

const EVENT_TEXT: Record<string, string> = {
  rule_drafted: 'Drafted', rule_drafted_from_text: 'Drafted from regulation text', rule_edited: 'Edited', rule_submitted: 'Submitted for approval',
  rule_approved: 'Approved', rule_returned: 'Returned to the author', rule_activated: 'Activated', rule_retired: 'Retired',
};

type Draft = { title: string; description: string; severity: string; effective_from: string; source_reference: string; clause: string; params: Record<string, unknown> };

function toDraft(r: Rule): Draft {
  return {
    title: r.title ?? '', description: r.description ?? '', severity: r.severity ?? 'medium', effective_from: r.effective_from ?? '',
    source_reference: r.source_reference ?? '', clause: r.clause ?? '', params: { ...(r.params ?? {}) },
  };
}

function ParamField({ name, spec, value, onChange }: { name: string; spec: ParamSpec; value: unknown; onChange: (v: unknown) => void }) {
  const id = `param-${name}`;
  if (spec.kind === 'bool') {
    return (
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
        {spec.label}
      </label>
    );
  }
  if (spec.kind === 'choices') {
    const chosen = Array.isArray(value) ? (value as string[]) : [];
    return (
      <fieldset>
        <legend className={label}>{spec.label}</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {spec.choices.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={chosen.includes(c)}
                onChange={(e) => onChange(e.target.checked ? [...chosen, c] : chosen.filter((x) => x !== c))} />
              {humanize(c)}
            </label>
          ))}
        </div>
      </fieldset>
    );
  }
  return (
    <div className="max-w-xs">
      <label htmlFor={id} className={label}>{spec.label}</label>
      <input id={id} type="number" min={spec.min} max={spec.max} step={spec.kind === 'int' ? 1 : 'any'} required
        value={value == null ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} className={input} />
    </div>
  );
}

function Editor({ rule, schema, onSaved }: { rule: Rule; schema: Record<string, ParamSpec>; onSaved: () => void }) {
  const [d, setD] = useState<Draft>(() => toDraft(rule));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const set = (k: keyof Draft, v: unknown) => { setSaved(false); setD((x) => ({ ...x, [k]: v })); };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<Rule>(`/rules/${rule.id}`, {
      method: 'PUT',
      body: JSON.stringify({ ...d, effective_from: d.effective_from || null, source_reference: d.source_reference || null, clause: d.clause || null }),
    });
    setBusy(false);
    if (data) { setSaved(true); onSaved(); } else setError(error);
  };

  return (
    <form onSubmit={save} className="space-y-4 rounded-sheet border border-rule bg-sheet p-5">
      <h2 className="font-serif text-xl font-bold">Change this draft</h2>
      {Object.keys(schema).length > 0 ? (
        <div className="space-y-3">
          {Object.entries(schema).map(([name, spec]) => (
            <ParamField key={name} name={name} spec={spec} value={d.params[name]} onChange={(v) => set('params', { ...d.params, [name]: v })} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-ink-2">This check has no thresholds to set; only its wording, severity and dates change.</p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="title" className={label}>Title</label>
          <input id="title" maxLength={200} value={d.title} onChange={(e) => set('title', e.target.value)} className={input} />
        </div>
        <div>
          <label htmlFor="severity" className={label}>Severity of its findings</label>
          <select id="severity" value={d.severity} onChange={(e) => set('severity', e.target.value)} className={input}>
            {['low', 'medium', 'high'].map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label htmlFor="description" className={label}>What it checks</label>
        <textarea id="description" rows={2} maxLength={2000} value={d.description} onChange={(e) => set('description', e.target.value)} className={input} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="source_reference" className={label}>Source</label>
          <input id="source_reference" maxLength={300} value={d.source_reference} onChange={(e) => set('source_reference', e.target.value)} className={input} />
        </div>
        <div>
          <label htmlFor="effective_from" className={label}>In force from (optional)</label>
          <input id="effective_from" type="date" value={d.effective_from} onChange={(e) => set('effective_from', e.target.value)} className={input} />
          <p className="mt-1 text-xs text-ink-2">Left empty, it starts on the day it is activated.</p>
        </div>
      </div>
      <div>
        <label htmlFor="clause" className={label}>Clause it applies</label>
        <textarea id="clause" rows={3} maxLength={4000} value={d.clause} onChange={(e) => set('clause', e.target.value)} className={input} />
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {saved && <Notice kind="success">Draft saved.</Notice>}
      <button type="submit" className={btnPrimary} disabled={busy}>{busy ? 'Saving…' : 'Save draft'}</button>
    </form>
  );
}

function Impact({ rule }: { rule: Rule }) {
  const [impact, setImpact] = useState<RuleImpact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<RuleImpact>(`/rules/${rule.id}/impact`);
    setBusy(false);
    if (data) setImpact(data); else setError(error);
  };

  return (
    <section aria-labelledby="impact" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="impact" className="font-serif text-xl font-bold">Impact preview</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-2">
            Runs this version&apos;s check over every submitted application and compares it with the version in force. Nothing is saved.
          </p>
        </div>
        <button className={btnSecondary} onClick={run} disabled={busy}>{busy ? 'Checking every application…' : impact ? 'Preview again' : 'Preview impact'}</button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {impact && !impact.available && <Notice>{impact.note}</Notice>}
      {impact && impact.available && (
        <>
          <p className="text-sm">
            Compared with {impact.compared_with ? `version ${impact.compared_with}` : 'no version in force'} on {formatDate(impact.as_of_date)}:{' '}
            {impact.totals.applications_checked} applications checked, <strong>{impact.totals.created}</strong> finding{impact.totals.created === 1 ? '' : 's'} would
            open and <strong>{impact.totals.closed}</strong> would close, in {impact.totals.affected} application{impact.totals.affected === 1 ? '' : 's'}.
          </p>
          {impact.applications.length === 0 ? (
            <Empty>No application&apos;s findings would change.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[48rem] border-collapse">
                <thead><tr><th className={th}>Application</th><th className={th}>Would open</th><th className={th}>Would close</th><th className={th}>Unchanged</th></tr></thead>
                <tbody>
                  {impact.applications.map((a) => (
                    <tr key={a.id}>
                      <td className={td}>
                        <Link href={`/review/${a.id}`} className="font-semibold tabular-nums underline decoration-rule-strong underline-offset-4">{a.code}</Link>
                        {a.institution && <p className="text-xs text-ink-2">{a.institution}</p>}
                      </td>
                      <td className={td}>{a.created.length ? <ul className="space-y-1">{a.created.map((f) => <li key={f.key}>{f.title} <Tag>{humanize(f.severity)}</Tag></li>)}</ul> : '—'}</td>
                      <td className={td}>{a.closed.length ? <ul className="space-y-1">{a.closed.map((f) => <li key={f.key}>{f.title}</li>)}</ul> : '—'}</td>
                      <td className={`${td} tabular-nums`}>{a.unchanged}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-ink-2">{impact.note}</p>
        </>
      )}
    </section>
  );
}

function Actions({ rule, meId, onDone }: { rule: Rule; meId: string; onDone: (r?: Rule) => void }) {
  const router = useRouter();
  const [reason, setReason] = useState('');
  const [from, setFrom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const author = rule.created_by === meId;
  const approved = Boolean(rule.approved_by);

  const act = async (path: string, extra: Record<string, unknown> = {}) => {
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<Rule>(path, { method: 'POST', body: JSON.stringify({ reason: reason.trim(), ...extra }) });
    setBusy(false);
    if (!data) return setError(error);
    setReason('');
    if (data.id !== rule.id) router.push(`/admin/rules/${data.id}`);
    else onDone(data);
  };

  const ready = reason.trim().length >= 3 && !busy;
  const buttons: React.ReactNode[] = [];
  let explain: string | null = null;
  if (rule.status === 'draft') {
    if (author) buttons.push(<button key="s" className={btnPrimary} disabled={!ready} onClick={() => act(`/rules/${rule.id}/submit`)}>Submit for approval</button>);
    else explain = `Only the author${rule.created_by_name ? `, ${rule.created_by_name},` : ''} can change or submit this draft.`;
  } else if (rule.status === 'pending_approval' && !approved) {
    buttons.push(
      <button key="a" className={btnPrimary} disabled={!ready || author} onClick={() => act(`/rules/${rule.id}/approve`)}>Approve this version</button>,
      <button key="r" className={btnSecondary} disabled={!ready || author} onClick={() => act(`/rules/${rule.id}/return`)}>Return to the author</button>,
    );
    if (author) explain = 'You wrote this version, so another rule administrator approves or returns it (four eyes).';
  } else if (rule.status === 'pending_approval' && approved) {
    buttons.push(<button key="act" className={btnPrimary} disabled={!ready} onClick={() => act(`/rules/${rule.id}/activate`, { effective_from: from || null })}>Activate</button>);
  } else {
    buttons.push(<button key="n" className={btnPrimary} disabled={!ready} onClick={() => act('/rules', { from_rule_id: rule.id })}>Start a new version</button>);
    if (rule.status === 'active') buttons.push(<button key="ret" className={btnSecondary} disabled={!ready} onClick={() => act(`/rules/${rule.id}/retire`)}>Retire</button>);
  }

  return (
    <section aria-labelledby="actions" className="space-y-3 rounded-sheet border border-rule bg-sheet p-5">
      <h2 id="actions" className="font-serif text-xl font-bold">Next step</h2>
      {rule.status === 'pending_approval' && approved && (
        <div className="max-w-xs">
          <label htmlFor="from" className={label}>In force from</label>
          <input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={input} />
          <p className="mt-1 text-xs text-ink-2">Empty means {rule.effective_from ? formatDate(rule.effective_from) : 'the as-of date'}. A date before the as-of date is moved to it. The version in force ends the day before.</p>
        </div>
      )}
      {buttons.length > 0 && (
        <div className="max-w-xl">
          <label htmlFor="reason" className={label}>Reason</label>
          <input id="reason" minLength={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} className={input}
            placeholder="Kept in the rule's history" />
        </div>
      )}
      {explain && <p className="text-sm text-ink-2">{explain}</p>}
      {error && <Notice kind="error">{error}</Notice>}
      {buttons.length > 0 && <div className="flex flex-wrap gap-3">{buttons}</div>}
    </section>
  );
}

function RuleView() {
  const { id } = useParams<{ id: string }>();
  const drafted = useSearchParams().get('drafted');
  const { me } = useMe();
  const [detail, setDetail] = useState<RuleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    fetchApi<RuleDetail>(`/rules/${id}`).then(({ data, error }) => (data ? setDetail(data) : setError(error)));
  }, [id, version]);

  if (error) return <PageShell title="Rule" description="A rule, its versions and its history."><Notice kind="error">{error}</Notice></PageShell>;
  if (!detail || !me) return <PageShell title="Rule" description="A rule, its versions and its history."><Loading what="Loading the rule" /></PageShell>;

  const r = detail.rule;
  const stage = ruleStage(r);
  const editable = r.status === 'draft' && r.created_by === me.user_id;

  return (
    <PageShell
      wide
      title={<>{r.rule_code} <span className="text-ink-2">version {r.version}</span></>}
      description={`${r.title ?? 'Rule'}. Illustrative, not an official AICTE rule.`}
      actions={<Link href="/admin/rules" className={btnQuiet}>All rules</Link>}
    >
      {drafted && r.status === 'draft' && (
        <div className="mb-6">
          <Notice kind="warning">
            Drafted from the pasted text {drafted === 'llm' ? 'with the language model; its clause and numbers were checked against the text' : 'by the rule-based reader'}.
            Check every value against the clause before you submit it.
          </Notice>
        </div>
      )}
      <div className="grid gap-8 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-8">
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <Tag tone={stage.tone}>{stage.label}</Tag>
              {r.check && <span className="text-sm text-ink-2">Check {r.check}</span>}
              {r.finding_types.length > 0 && <span className="text-sm text-ink-2">Findings: {r.finding_types.map((t) => FINDING_TYPE_LABEL[t] ?? humanize(t)).join(', ')}</span>}
            </div>
            {r.description && <p>{r.description}</p>}
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[12rem_1fr]">
              <dt className="text-ink-2">Thresholds</dt><dd>{paramsText(r.params)}</dd>
              <dt className="text-ink-2">Severity</dt><dd>{r.severity ? humanize(r.severity) : '—'}</dd>
              <dt className="text-ink-2">In force</dt>
              <dd>{r.effective_from ? `from ${formatDate(r.effective_from)}` : 'set when activated'}{r.effective_to ? ` to ${formatDate(r.effective_to)}` : ''}</dd>
              <dt className="text-ink-2">Source</dt><dd>{r.source_reference ?? '—'}</dd>
              <dt className="text-ink-2">Written by</dt><dd>{r.created_by_name ?? 'Reference data'}</dd>
              <dt className="text-ink-2">Approved by</dt><dd>{r.approved_by_name ? `${r.approved_by_name}, ${formatDateTime(r.approved_at)}` : '—'}</dd>
            </dl>
            {r.clause && (
              <blockquote className="border-l-2 border-rule-strong pl-4 text-sm">
                <p className="text-xs text-ink-2">Clause it applies</p>
                <p className="mt-1">{r.clause}</p>
              </blockquote>
            )}
          </section>

          {editable && <Editor key={`${r.id}-${version}`} rule={r} schema={detail.params_schema} onSaved={reload} />}
          {(r.status === 'draft' || r.status === 'pending_approval') && <Impact rule={r} />}

          <section aria-labelledby="versions" className="space-y-3">
            <h2 id="versions" className="font-serif text-xl font-bold">Versions</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] border-collapse">
                <thead><tr><th className={th}>Version</th><th className={th}>Thresholds</th><th className={th}>In force</th><th className={th}>Status</th></tr></thead>
                <tbody>
                  {detail.versions.map((v) => (
                    <tr key={v.id} aria-current={v.id === r.id ? 'true' : undefined} className={v.id === r.id ? 'bg-ink-wash' : undefined}>
                      <td className={td}>
                        {v.id === r.id ? <span className="font-semibold">Version {v.version}</span>
                          : <Link href={`/admin/rules/${v.id}`} className="underline decoration-rule-strong underline-offset-4">Version {v.version}</Link>}
                      </td>
                      <td className={td}>{paramsText(v.params)}</td>
                      <td className={td}>{v.effective_from ? formatDate(v.effective_from) : '—'}{v.effective_to ? ` to ${formatDate(v.effective_to)}` : ''}</td>
                      <td className={td}><Tag tone={ruleStage(v).tone}>{ruleStage(v).label}</Tag></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-ink-2">A validation run records the version of each rule it used, so earlier findings keep meaning what they meant.</p>
          </section>
        </div>

        <aside className="space-y-8">
          <Actions rule={r} meId={me.user_id} onDone={reload} />
          <section aria-labelledby="history" className="space-y-3">
            <h2 id="history" className="font-serif text-xl font-bold">History of this version</h2>
            {detail.history.length === 0 ? (
              <p className="text-sm text-ink-2">Nothing recorded yet. Reference versions were loaded with the illustrative rule set.</p>
            ) : (
              <ol className="space-y-3 border-l-2 border-officer pl-4 text-sm">
                {detail.history.map((e) => (
                  <li key={e.id}>
                    <p className="font-semibold text-officer">{EVENT_TEXT[e.event_type] ?? humanize(e.event_type)}</p>
                    <p className="text-xs text-ink-2">{formatDateTime(e.created_at)}{e.actor_name ? `, ${e.actor_name}` : ''}</p>
                    {typeof e.detail?.reason === 'string' && <p className="mt-0.5">{e.detail.reason}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </PageShell>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><Loading what="Loading the rule" /></div>}>
      <RuleView />
    </Suspense>
  );
}
