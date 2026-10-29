'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { humanize, type AdminSettings, type ExtractionTemplate, type RegistryMode, type RegistrySetting, type RegulationClause } from '@/lib/types';
import { Loading, Notice, PageShell, Tag, btnQuiet, btnSecondary, formatDate, input, label, td, th, useMe } from '@/components/ui';

const MODE_TEXT: Record<RegistryMode, { title: string; text: string }> = {
  unavailable: {
    title: 'Unavailable',
    text: 'The registry cannot be reached. Lookups record Pending (source unavailable), which is never a failed check. This is the default.',
  },
  match: { title: 'Answers with a matching record', text: 'The record repeats the values read from the document, so lookups read Source verified (MOCK).' },
  mismatch: {
    title: 'Answers with a differing record',
    text: 'The record differs from the document in one value, so lookups open a Differs from issuer registry finding (check C15).',
  },
};

type Ctx = {
  reason: string; canEdit: boolean; busy: boolean; setBusy: (b: boolean) => void;
  onSaved: (text: string) => void; onError: (text: string) => void; reload: () => void;
};

function Section({ id, title, text, children }: { id: string; title: React.ReactNode; text: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-4">
      <div>
        <h2 id={id} className="font-serif text-xl font-bold">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm text-ink-2">{text}</p>
      </div>
      {children}
    </section>
  );
}

async function save(ctx: Ctx, path: string, body: Record<string, unknown>, done: string, method = 'PUT') {
  ctx.setBusy(true);
  const { data, error } = await fetchApi(path, { method, body: JSON.stringify({ ...body, reason: ctx.reason.trim() }) });
  ctx.setBusy(false);
  if (data) { ctx.onSaved(done); ctx.reload(); return true; }
  ctx.onError(error ?? 'Not saved');
  return false;
}

const ready = (ctx: Ctx) => ctx.canEdit && !ctx.busy && ctx.reason.trim().length >= 3;

function AsOf({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const [mode, setMode] = useState(s.as_of.mode);
  const [date, setDate] = useState(s.as_of.date ?? '');
  const changed = mode !== s.as_of.mode || (mode === 'fixed' && date !== (s.as_of.date ?? ''));
  return (
    <Section id="as-of" title="As-of date" text="The date every date check compares against (expiry, photo age, rule versions in force). A fixed date keeps demonstrations and the evaluation repeatable.">
      <p className="text-sm">In use now: <strong>{formatDate(s.as_of.effective)}</strong>{s.as_of.mode === 'today' ? ' (today)' : ' (fixed)'}</p>
      <fieldset className="flex flex-wrap items-end gap-5" disabled={!ctx.canEdit}>
        <legend className="sr-only">As-of date</legend>
        <label className="flex items-center gap-2 text-sm"><input type="radio" checked={mode === 'today'} onChange={() => setMode('today')} />Today</label>
        <label className="flex items-center gap-2 text-sm"><input type="radio" checked={mode === 'fixed'} onChange={() => setMode('fixed')} />A fixed date</label>
        {mode === 'fixed' && (
          <div>
            <label htmlFor="as-of-date" className={label}>Date</label>
            <input id="as-of-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className={input} />
          </div>
        )}
        <button className={btnSecondary} disabled={!ready(ctx) || !changed || (mode === 'fixed' && !date)}
          onClick={() => save(ctx, '/admin/settings/as-of', { mode, date: mode === 'fixed' ? date : null }, 'As-of date saved. It applies to the next validation run.')}>
          Save as-of date
        </button>
      </fieldset>
    </Section>
  );
}

function Weights({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const [w, setW] = useState<Record<string, number>>(() => Object.fromEntries(s.priority_weights.map((x) => [x.key, x.weight])));
  const changed = s.priority_weights.some((x) => w[x.key] !== x.weight);
  const valid = Object.values(w).every((v) => Number.isInteger(v) && v >= 0 && v <= 100);
  return (
    <Section id="weights" title="Priority weights" text="How much each signal adds to an application's place in the review queue. Weights only order the queue; they never change a status or a finding.">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {s.priority_weights.map((x) => (
          <div key={x.key}>
            <label htmlFor={`w-${x.key}`} className={label}>{x.label}</label>
            <input id={`w-${x.key}`} type="number" min={0} max={100} step={1} value={Number.isNaN(w[x.key]) ? '' : w[x.key]} disabled={!ctx.canEdit}
              onChange={(e) => setW((v) => ({ ...v, [x.key]: e.target.valueAsNumber }))} className={input} />
          </div>
        ))}
      </div>
      <button className={btnSecondary} disabled={!ready(ctx) || !changed || !valid}
        onClick={() => save(ctx, '/admin/settings/priority-weights', { weights: w }, 'Weights saved. The queue uses them from its next load.')}>
        Save weights
      </button>
    </Section>
  );
}

function Checklists({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const required = new Set(s.required_documents.map((r) => `${r.category}|${r.doc_type}`));
  const [busy, setBusy] = useState<string | null>(null);
  const toggle = async (category: string, doc_type: string, on: boolean) => {
    setBusy(`${category}|${doc_type}`);
    await save(ctx, '/admin/settings/checklist', { category, doc_type, required: on },
      `${humanize(doc_type)} is ${on ? 'now required' : 'no longer required'} for ${s.categories.find((c) => c.code === category)?.label ?? category}. Check C1 uses it from the next run.`);
    setBusy(null);
  };
  return (
    <Section id="checklists" title="Checklists" text="Which documents each application category must include (check C1). A tick means required.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] border-collapse">
          <thead>
            <tr>
              <th className={th}>Document</th>
              {s.categories.map((c) => <th key={c.code} className={`${th} text-center`}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {s.document_types.map((d) => (
              <tr key={d.code}>
                <td className={`${td} font-semibold`}>{d.label}</td>
                {s.categories.map((c) => {
                  const k = `${c.code}|${d.code}`;
                  return (
                    <td key={c.code} className={`${td} text-center`}>
                      <input type="checkbox" aria-label={`${d.label} required for ${c.label}`} checked={required.has(k)}
                        disabled={!ready(ctx) || busy !== null} onChange={(e) => toggle(c.code, d.code, e.target.checked)} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function DocumentTypes({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const [busy, setBusy] = useState(false);
  const flip = async (code: string, flag: 'has_expiry' | 'signature_required', on: boolean) => {
    setBusy(true);
    await save(ctx, `/admin/settings/document-types/${code}`, { [flag]: on },
      `${humanize(code)}: ${flag === 'has_expiry' ? (on ? 'expiry is checked (C2)' : 'expiry is not checked') : (on ? 'a digital signature is required (C13)' : 'a signature is not required')}.`);
    setBusy(false);
  };
  return (
    <Section id="doc-types" title="Document types" text="Whether a type carries an expiry date that check C2 compares with the as-of date, and whether an unsigned copy is a finding (check C13).">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse">
          <thead><tr><th className={th}>Document</th><th className={`${th} text-center`}>Has an expiry date</th><th className={`${th} text-center`}>Signature required</th></tr></thead>
          <tbody>
            {s.document_types.map((d) => (
              <tr key={d.code}>
                <td className={`${td} font-semibold`}>{d.label}</td>
                <td className={`${td} text-center`}>
                  <input type="checkbox" aria-label={`${d.label} has an expiry date`} checked={d.has_expiry} disabled={!ready(ctx) || busy}
                    onChange={(e) => flip(d.code, 'has_expiry', e.target.checked)} />
                </td>
                <td className={`${td} text-center`}>
                  <input type="checkbox" aria-label={`${d.label} requires a signature`} checked={d.signature_required} disabled={!ready(ctx) || busy || d.is_photo}
                    onChange={(e) => flip(d.code, 'signature_required', e.target.checked)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function TemplateRow({ t, typeLabel, ctx }: { t: ExtractionTemplate; typeLabel: string; ctx: Ctx }) {
  const [editing, setEditing] = useState(false);
  const [regex, setRegex] = useState(t.regex);
  return (
    <tr>
      <td className={td}><p className="font-semibold">{humanize(t.field_name)}</p><p className="text-xs text-ink-2">{typeLabel}</p></td>
      <td className={`${td} w-full`}>
        {editing ? (
          <div className="space-y-2">
            <input aria-label={`Pattern for ${t.field_name}`} value={regex} onChange={(e) => setRegex(e.target.value)} className={`${input} font-mono text-xs`} />
            <div className="flex gap-2">
              <button className={btnSecondary} disabled={!ready(ctx) || regex === t.regex || regex.trim().length < 3}
                onClick={async () => { if (await save(ctx, `/admin/settings/templates/${t.id}`, { regex }, `Pattern for ${humanize(t.field_name).toLowerCase()} saved. It applies to documents read from now on.`)) setEditing(false); }}>
                Save pattern
              </button>
              <button className={btnQuiet} onClick={() => { setRegex(t.regex); setEditing(false); }}>Cancel</button>
            </div>
          </div>
        ) : (
          <code className="break-all text-xs">{t.regex}</code>
        )}
      </td>
      <td className={td}>{t.required ? 'Required' : 'Optional'}</td>
      <td className={td}>{ctx.canEdit && !editing && <button className={btnQuiet} onClick={() => setEditing(true)}>Change</button>}</td>
    </tr>
  );
}

function Templates({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const [open, setOpen] = useState(false);
  const labels = Object.fromEntries(s.document_types.map((d) => [d.code, d.label]));
  return (
    <Section id="templates" title="Reading templates" text="The pattern each value is read from a document with. A changed pattern is checked before it is saved and applies to documents read from then on; values already read keep their reading.">
      <button className={btnQuiet} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide' : 'Show'} {s.extraction_templates.length} patterns
      </button>
      {open && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[48rem] border-collapse">
            <thead><tr><th className={th}>Value</th><th className={th}>Pattern</th><th className={th}>Needed</th><th className={th}><span className="sr-only">Change</span></th></tr></thead>
            <tbody>{s.extraction_templates.map((t) => <TemplateRow key={t.id} t={t} typeLabel={labels[t.doc_type] ?? t.doc_type} ctx={ctx} />)}</tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function TrustStore({ s, ctx }: { s: AdminSettings; ctx: Ctx }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    const body = new FormData();
    body.set('certificate', file);
    body.set('name', name.trim());
    body.set('reason', ctx.reason.trim());
    const { data, error } = await fetchApi('/admin/settings/trust-store', { method: 'POST', body });
    setBusy(false);
    if (data) { ctx.onSaved(`${name.trim()} is trusted. Signatures checked from now on use it; a reviewer can check earlier ones again.`); setFile(null); setName(''); setFormKey((k) => k + 1); ctx.reload(); }
    else ctx.onError(error ?? 'Not added');
  };

  return (
    <Section id="trust" title="Signature trust store" text="Certificates a digital signature must chain to for check C13 to read it as valid. The seeded issuers are fictional; their root is added by the seed.">
      {s.trust_store.length === 0 ? (
        <Notice kind="warning">No certificate is trusted, so every signature reads as an untrusted certificate chain.</Notice>
      ) : (
        <ul className="divide-y divide-rule rounded-sheet border border-rule bg-paper">
          {s.trust_store.map((c) => (
            <li key={c.fingerprint} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
              <div className="min-w-0 text-sm">
                <p className="font-semibold">{c.name} {c.is_ca && <Tag>Root or issuing authority</Tag>} {c.source === 'seed' && <Tag>Fictional, from the seed</Tag>}</p>
                <p className="text-ink-2">{c.subject}</p>
                <p className="text-xs text-ink-2">Valid {formatDate(c.not_before)} to {formatDate(c.not_after)}. Fingerprint (SHA-256) <code className="break-all">{c.fingerprint}</code></p>
              </div>
              {ctx.canEdit && (
                <button className={btnQuiet} disabled={!ready(ctx)}
                  onClick={() => save(ctx, `/admin/settings/trust-store/${c.fingerprint}/remove`, {}, `${c.name} removed from the trust store.`, 'POST')}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {ctx.canEdit && (
        <form key={formKey} onSubmit={add} className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="cert-file" className={label}>Certificate (PEM or DER)</label>
            <input id="cert-file" type="file" accept=".pem,.crt,.cer,.der" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block text-sm file:mr-3 file:rounded-control file:border file:border-ink file:bg-sheet file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink" />
          </div>
          <div className="min-w-[16rem] flex-1">
            <label htmlFor="cert-name" className={label}>Name</label>
            <input id="cert-name" value={name} onChange={(e) => setName(e.target.value)} className={input} placeholder="for example State fire services root" />
          </div>
          <button type="submit" className={btnSecondary} disabled={!ready(ctx) || !file || name.trim().length < 2 || busy}>{busy ? 'Adding…' : 'Trust this certificate'}</button>
        </form>
      )}
    </Section>
  );
}

function Registry({ ctx }: { ctx: Ctx }) {
  const [setting, setSetting] = useState<RegistrySetting | null>(null);
  const [mode, setMode] = useState<RegistryMode>('unavailable');
  useEffect(() => {
    fetchApi<RegistrySetting>('/admin/settings/registry').then(({ data }) => { if (data) { setSetting(data); setMode(data.mode); } });
  }, []);
  if (!setting) return null;
  return (
    <Section id="registry" title={<>Issuer registry <Tag tone="pending">MOCK</Tag></>}
      text="A reviewer can look a certificate, NOC or land record up in its issuer's registry. A real registry, such as DigiLocker or API Setu, needs authorisation, so a MOCK answers instead.">
      <fieldset className="space-y-3" disabled={!ctx.canEdit}>
        <legend className={label}>The MOCK registry answers</legend>
        {setting.modes.map((m) => (
          <label key={m} className="flex items-start gap-3 text-sm">
            <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} className="mt-1" />
            <span>
              <span className="font-semibold">{MODE_TEXT[m].title}</span>
              {setting.mode === m && <span className="ml-2"><Tag tone="active">Current</Tag></span>}
              <span className="block text-ink-2">{MODE_TEXT[m].text}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <button className={btnSecondary} disabled={!ready(ctx) || mode === setting.mode}
        onClick={async () => { if (await save(ctx, '/admin/settings/registry', { mode }, `Saved. Lookups from now on ${mode === 'unavailable' ? 'read as unavailable' : `get a ${mode === 'match' ? 'matching' : 'differing'} record`}. Earlier lookups keep their answers.`)) setSetting({ ...setting, mode }); }}>
        Save registry setting
      </button>
      <div>
        <h3 className="mb-2 font-semibold">Documents a registry holds</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse">
            <thead><tr><th className={th}>Document</th><th className={th}>Issuer</th><th className={th}>Looked up by</th><th className={th}>Values compared</th></tr></thead>
            <tbody>
              {setting.documents.map((d) => (
                <tr key={d.doc_type}>
                  <td className={`${td} font-semibold`}>{d.label}</td>
                  <td className={td}>{d.issuer}</td>
                  <td className={td}>{humanize(d.key).toLowerCase()}</td>
                  <td className={td}>{d.fields.map((f) => humanize(f).toLowerCase()).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Section>
  );
}

const NEW_CLAUSE = { clause_ref: '', heading: '', body: '', source: '', rule_codes: '', is_illustrative: true };

function Clauses({ ctx }: { ctx: Ctx }) {
  const [clauses, setClauses] = useState<RegulationClause[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [form, setForm] = useState(NEW_CLAUSE);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    fetchApi<RegulationClause[]>('/admin/clauses').then(({ data, error }) => (data ? setClauses(data) : setProblem(error)));
  }, [version]);
  const set = (k: keyof typeof NEW_CLAUSE) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });
  const complete = form.clause_ref.trim().length >= 2 && form.heading.trim().length >= 3 && form.source.trim().length >= 3 && form.body.trim().length >= 20;
  const add = async () => {
    const rule_codes = form.rule_codes.split(',').map((c) => c.trim()).filter(Boolean);
    if (await save(ctx, '/admin/clauses', { ...form, rule_codes }, `Clause ${form.clause_ref.trim()} added. Findings under its rules show it from now on.`, 'POST')) {
      setForm(NEW_CLAUSE);
      setVersion((v) => v + 1);
    }
  };
  return (
    <Section id="clauses" title="Regulation clauses"
      text="The clauses a reviewer sees under Why this rule on each finding. Those linked to a rule come first, then the closest by keyword search. Clauses are added, not edited.">
      {problem && <Notice kind="error">{problem}</Notice>}
      {!clauses && !problem && <Loading what="Loading clauses" />}
      {clauses && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead><tr><th className={th}>Clause</th><th className={th}>Text</th><th className={th}>Linked rules</th></tr></thead>
            <tbody>
              {clauses.map((c) => (
                <tr key={c.id}>
                  <td className={`${td} align-top`}>
                    <span className="font-semibold">{c.clause_ref}</span>
                    {c.is_illustrative && <span className="ml-2"><Tag>Illustrative</Tag></span>}
                    <span className="block text-xs text-ink-2">{c.source}</span>
                  </td>
                  <td className={`${td} align-top`}><span className="font-semibold">{c.heading}.</span> {c.body}</td>
                  <td className={`${td} align-top`}>{c.rule_codes.join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {ctx.canEdit && (
        <fieldset className="grid gap-3 sm:grid-cols-2">
          <legend className="mb-2 font-semibold">Add a clause</legend>
          <div><label htmlFor="cl-ref" className={label}>Reference</label><input id="cl-ref" className={input} value={form.clause_ref} onChange={set('clause_ref')} placeholder="for example ILL-6.1" /></div>
          <div><label htmlFor="cl-heading" className={label}>Heading</label><input id="cl-heading" className={input} value={form.heading} onChange={set('heading')} /></div>
          <div className="sm:col-span-2"><label htmlFor="cl-body" className={label}>Text</label><textarea id="cl-body" rows={3} className={input} value={form.body} onChange={set('body')} /></div>
          <div><label htmlFor="cl-source" className={label}>Source</label><input id="cl-source" className={input} value={form.source} onChange={set('source')} placeholder="where the text comes from" /></div>
          <div><label htmlFor="cl-rules" className={label}>Linked rules, separated by commas</label><input id="cl-rules" className={input} value={form.rule_codes} onChange={set('rule_codes')} placeholder="for example R-EXP-01" /></div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" checked={form.is_illustrative} onChange={(e) => setForm({ ...form, is_illustrative: e.target.checked })} />
            Illustrative text, not quoted from an official regulation
          </label>
          <div className="sm:col-span-2"><button className={btnSecondary} disabled={!ready(ctx) || !complete} onClick={add}>Add clause</button></div>
        </fieldset>
      )}
    </Section>
  );
}

export default function SettingsPage() {
  const { me } = useMe();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchApi<AdminSettings>('/admin/settings').then(({ data, error }) => (data ? setSettings(data) : setError(error)));
  }, [version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const canEdit = me?.role === 'rule_admin';
  const ctx: Ctx = {
    reason, canEdit, reload, busy, setBusy,
    onSaved: (text) => setNote({ kind: 'success', text }),
    onError: (text) => setNote({ kind: 'error', text }),
  };

  return (
    <PageShell
      wide
      title="Settings"
      description="The as-of date, queue weights, checklists, document types, reading patterns, the signature trust store, the MOCK issuer registry and the regulation clauses. Every change is kept in the audit trail."
    >
      {error && <div className="mb-4"><Notice kind="error">{error}</Notice></div>}
      {!settings && !error && <Loading what="Loading settings" />}
      {settings && (
        <div className="grid gap-10 lg:grid-cols-[1fr_18rem]">
          <div className="order-2 space-y-12 lg:order-1">
            <AsOf key={`as-of-${version}`} s={settings} ctx={ctx} />
            <Weights key={`w-${version}`} s={settings} ctx={ctx} />
            <Checklists s={settings} ctx={ctx} />
            <DocumentTypes s={settings} ctx={ctx} />
            <TrustStore s={settings} ctx={ctx} />
            <Templates s={settings} ctx={ctx} />
            <Registry ctx={ctx} />
            <Clauses ctx={ctx} />
          </div>
          <aside className="order-1 lg:order-2">
            <div className="space-y-3 rounded-sheet border border-rule bg-sheet p-5 lg:sticky lg:top-6">
              {canEdit ? (
                <>
                  <label htmlFor="reason" className={label}>Reason for your changes</label>
                  <textarea id="reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} className={input}
                    placeholder="for example fixed date for the demonstration" />
                  <p className="text-xs text-ink-2">Every change is saved with this reason and with the value before and after. Changes are not versioned like rules.</p>
                  {reason.trim().length < 3 && <p className="text-xs text-ink-2">Write a reason first; the controls are off until then.</p>}
                </>
              ) : (
                <p className="text-sm text-ink-2">Only a rule administrator can change settings.</p>
              )}
              {busy && <p className="text-sm text-ink-2" role="status">Saving…</p>}
              {!busy && note && <Notice kind={note.kind}>{note.text}</Notice>}
            </div>
          </aside>
        </div>
      )}
    </PageShell>
  );
}
