'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import {
  VERIFY_STATUS_LABEL, humanize,
  type DocumentRow, type DocumentVerification, type VerificationCheck,
} from '@/lib/types';
import { Loading, Mark, Notice, Tag, btnQuiet, btnSecondary, formatDate, formatDateTime, input, label, td, th, type Tone } from './ui';

const TONE: Record<string, Tone> = {
  passed: 'ok', match: 'ok', manual_confirmed: 'ok', valid: 'ok',
  failed: 'conflict', mismatch: 'conflict', manual_not_confirmed: 'conflict', invalid: 'conflict', untrusted_chain: 'conflict',
  unavailable: 'pending', manual_pending: 'pending', unsigned: 'pending', indicators: 'pending', clear: 'ok',
};

const METHOD_NAME: Record<string, string> = {
  HASH: 'File check', SIGNATURE: 'Signature', METADATA: 'File metadata', REGISTRY: 'Issuer registry (MOCK)', MANUAL: 'Manual check',
};

const OUTCOMES = [
  { value: 'pending', text: 'Asked, waiting for an answer' },
  { value: 'confirmed', text: 'The issuer confirmed it' },
  { value: 'not_confirmed', text: 'The issuer did not confirm it' },
] as const;

function StateTag({ check }: { check?: VerificationCheck }) {
  if (!check) return <Tag>Not checked yet</Tag>;
  return <Tag tone={TONE[check.status] ?? 'neutral'}>{VERIFY_STATUS_LABEL[check.status] ?? humanize(check.status)}</Tag>;
}

function By({ check }: { check: VerificationCheck }) {
  return (
    <p className="text-xs text-ink-2">
      {formatDateTime(check.checked_at)}{check.checked_by_name ? `, ${check.checked_by_name}` : check.checked_by ? '' : ', by the system'}
    </p>
  );
}

const shown = (type: string, v: string | null | undefined) => (v == null ? '—' : type === 'date' ? formatDate(v) : v);

/** The registry's record beside the values read from the document. */
function Comparison({ check }: { check: VerificationCheck }) {
  const rows = check.response.compared ?? [];
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] border-collapse">
        <thead>
          <tr>
            <th className={th}>Value</th>
            <th className={th}>In the document</th>
            <th className={th}>In the registry record (MOCK)</th>
            <th className={th}>Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.field}>
              <td className={`${td} font-semibold`}>{humanize(c.field)}</td>
              <td className={td}>{c.document_shown ? <Mark>{c.document_shown}</Mark> : <span className="text-ink-3">Not read</span>}</td>
              <td className={td}>{shown(c.value_type, c.registry_value)}</td>
              <td className={td}>
                {c.same === true ? <Tag tone="ok">Same</Tag> : c.same === false ? <Tag tone="conflict">Differs</Tag> : <Tag>Not compared</Tag>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Attachment({ check }: { check: VerificationCheck }) {
  const a = check.response.attachment;
  if (!a) return null;
  const open = async () => {
    const tab = window.open('', '_blank');
    const { data, error } = await fetchApi<{ url: string }>(`/verification-checks/${check.id}/attachment`);
    if (data && tab) tab.location.href = data.url;
    else { tab?.close(); window.alert(error || 'Could not open the attachment'); }
  };
  return <button className={`${btnQuiet} -ml-2`} onClick={open}>Open the issuer&apos;s reply ({a.name})</button>;
}

function ManualForm({ documentId, issuer, onDone }: { documentId: string; issuer: string; onDone: () => void }) {
  const [outcome, setOutcome] = useState<(typeof OUTCOMES)[number]['value']>('pending');
  const [who, setWho] = useState(issuer);
  const [contact, setContact] = useState('');
  const [note, setNote] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.set('outcome', outcome);
    body.set('issuer', who.trim());
    body.set('contact', contact.trim());
    body.set('note', note.trim());
    if (file) body.set('attachment', file);
    const { data, error } = await fetchApi(`/documents/${documentId}/verify/manual`, { method: 'POST', body });
    setBusy(false);
    if (data) onDone();
    else setError(error);
  };

  return (
    <form onSubmit={submit} className="space-y-3 border-l-2 border-officer pl-4">
      <fieldset>
        <legend className={label}>What happened</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {OUTCOMES.map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-sm">
              <input type="radio" name={`outcome-${documentId}`} value={o.value} checked={outcome === o.value} onChange={() => setOutcome(o.value)} />
              {o.text}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`issuer-${documentId}`} className={label}>Issuer asked</label>
          <input id={`issuer-${documentId}`} required minLength={2} value={who} onChange={(e) => setWho(e.target.value)} className={input} />
        </div>
        <div>
          <label htmlFor={`contact-${documentId}`} className={label}>How you asked</label>
          <input id={`contact-${documentId}`} required minLength={2} value={contact} onChange={(e) => setContact(e.target.value)} className={input}
            placeholder="for example phone call to the approvals desk" />
        </div>
      </div>
      <div>
        <label htmlFor={`note-${documentId}`} className={label}>What they said</label>
        <textarea id={`note-${documentId}`} required minLength={3} rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={input} />
      </div>
      <div>
        <label htmlFor={`file-${documentId}`} className={label}>Copy of their reply (optional)</label>
        <input id={`file-${documentId}`} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm file:mr-3 file:rounded-control file:border file:border-ink file:bg-sheet file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink" />
        <p className="mt-1 text-xs text-ink-2">PDF, JPEG or PNG up to 5 MB, kept in private storage.</p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <button type="submit" disabled={busy || !who.trim() || !contact.trim() || note.trim().length < 3}
        className="inline-flex items-center rounded-control bg-officer px-4 py-2 text-sm font-semibold text-sheet hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
        {busy ? 'Recording…' : 'Record the manual check'}
      </button>
    </form>
  );
}

/**
 * Authenticity of one document, one row per method (build spec 10). Each method shows its own latest
 * state; a registry that cannot be reached reads as pending, never as a failure.
 */
export function VerificationPanel({ doc, canAct, onChanged }: { doc: DocumentRow; canAct: boolean; onChanged: () => void }) {
  const [view, setView] = useState<DocumentVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signing, setSigning] = useState(false);
  const [note, setNote] = useState<{ kind: 'success' | 'error' | 'warning'; text: string } | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    fetchApi<DocumentVerification>(`/documents/${doc.id}/verification`).then(({ data, error }) => (data ? setView(data) : setError(error)));
  }, [doc.id, version]);

  const reload = useCallback(() => { setVersion((v) => v + 1); onChanged(); }, [onChanged]);

  const lookUp = async () => {
    setBusy(true);
    setNote(null);
    const { data, error } = await fetchApi<{ check: VerificationCheck; validation: { created: number; auto_closed: number } | null }>(
      `/documents/${doc.id}/verify/registry`, { method: 'POST' });
    setBusy(false);
    if (!data) return setNote({ kind: 'error', text: error ?? 'The lookup did not run' });
    const s = data.check.status;
    const ran = data.validation ? ' Validation ran again.' : '';
    setNote(s === 'unavailable'
      ? { kind: 'warning', text: `The registry (MOCK) could not be reached. Authenticity stays pending; this is not a failed check.${ran}` }
      : s === 'mismatch'
        ? { kind: 'error', text: `The registry record (MOCK) differs from the document. It is listed as a finding.${ran}` }
        : { kind: 'success', text: `The registry record (MOCK) matches the values read from the document.${ran}` });
    reload();
  };

  const recheck = async () => {
    setSigning(true);
    setNote(null);
    const { data, error } = await fetchApi<{ signature: string; metadata: string; validation: unknown }>(
      `/documents/${doc.id}/verify/signature`, { method: 'POST' });
    setSigning(false);
    if (!data) return setNote({ kind: 'error', text: error ?? 'The signature check did not run' });
    setNote({ kind: data.signature === 'valid' ? 'success' : 'warning',
      text: `Signature: ${(VERIFY_STATUS_LABEL[data.signature] ?? data.signature).toLowerCase()}. File metadata: ${(VERIFY_STATUS_LABEL[data.metadata] ?? data.metadata).toLowerCase()}.${data.validation ? ' Validation ran again.' : ''}` });
    reload();
  };

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!view) return <Loading what="Loading verification" />;

  const latest = (method: string) => view.checks.find((c) => c.method === method);
  const hash = latest('HASH');
  const registry = latest('REGISTRY');
  const manual = latest('MANUAL');
  const signature = latest('SIGNATURE');
  const metadata = latest('METADATA');
  const current = doc.status === 'current' && doc.integrity_status === 'passed';
  const latestOnes = [hash, registry, manual, signature, metadata];
  const earlier = view.checks.filter((c) => !latestOnes.includes(c));
  const signer = signature?.response.signatures?.find((x) => x.signer);

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-2">Each method keeps its own result, and none overrides another.</p>
      <ul className="divide-y divide-rule rounded-sheet border border-rule bg-paper">
        <li className="grid gap-2 px-4 py-3 sm:grid-cols-[13rem_1fr]">
          <p className="font-semibold">File check</p>
          <div className="space-y-1">
            <StateTag check={hash} />
            {hash && <By check={hash} />}
          </div>
        </li>

        <li className="grid gap-2 px-4 py-3 sm:grid-cols-[13rem_1fr]">
          <div>
            <p className="font-semibold">Signature</p>
            <p className="text-xs text-ink-2">Embedded PDF signature, against the trust store</p>
          </div>
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StateTag check={signature} />
              {canAct && current && doc.mime === 'application/pdf' && (
                <button className={`${btnSecondary} px-3 py-1.5`} onClick={recheck} disabled={signing}>
                  {signing ? 'Checking…' : 'Check signature again'}
                </button>
              )}
            </div>
            {signature && <By check={signature} />}
            {signature?.response.note && <p className="text-sm">{signature.response.note}.</p>}
            {signer && (
              <p className="text-sm">
                <span className="text-ink-2">Signer named in the file</span> <Mark>{signer.signer}</Mark>
                {signer.signer_issuer && <span className="text-ink-2">, issued by {signer.signer_issuer}</span>}
                {signer.signed_at && <span className="text-ink-2">, signed {formatDateTime(signer.signed_at)}</span>}
              </p>
            )}
            {!signature && doc.mime !== 'application/pdf' && <p className="text-sm text-ink-2">Only a PDF carries an embedded signature.</p>}
          </div>
        </li>

        <li className="grid gap-2 px-4 py-3 sm:grid-cols-[13rem_1fr]">
          <div>
            <p className="font-semibold">File metadata</p>
            <p className="text-xs text-ink-2">Indicators only, not a verdict</p>
          </div>
          <div className="min-w-0 space-y-2">
            <StateTag check={metadata} />
            {metadata && <By check={metadata} />}
            {(metadata?.response.indicators ?? []).length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {metadata!.response.indicators!.map((i) => <li key={i.code}><Mark>{i.text}</Mark></li>)}
              </ul>
            )}
            {metadata && (
              <p className="text-xs text-ink-2">
                Created {formatDateTime(metadata.response.creation_date)}, last modified {formatDateTime(metadata.response.modification_date)}
                {metadata.response.revisions ? `, ${metadata.response.revisions} revision${metadata.response.revisions > 1 ? 's' : ''}` : ''}
                {metadata.response.producer ? `, made with ${metadata.response.producer}` : ''}.
              </p>
            )}
          </div>
        </li>

        <li className="grid gap-2 px-4 py-3 sm:grid-cols-[13rem_1fr]">
          <div>
            <p className="font-semibold">Issuer registry <Tag tone="pending">MOCK</Tag></p>
            {view.registry.issuer && <p className="text-xs text-ink-2">{view.registry.issuer}</p>}
          </div>
          <div className="min-w-0 space-y-2">
            {!view.registry.supported ? (
              <p className="text-sm text-ink-2">No issuer registry holds this kind of document. Record a manual check instead.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <StateTag check={registry} />
                  {canAct && current && (
                    <button className={`${btnSecondary} px-3 py-1.5`} onClick={lookUp} disabled={busy}>
                      {busy ? 'Looking up…' : registry ? 'Look up again (MOCK)' : 'Check issuer registry (MOCK)'}
                    </button>
                  )}
                </div>
                {registry && <By check={registry} />}
                {registry?.response.key && (
                  <p className="text-sm">Looked up by {humanize(registry.response.key.field).toLowerCase()} <Mark>{registry.response.key.value}</Mark></p>
                )}
                {registry && <Comparison check={registry} />}
                {registry?.response.note && <p className="text-xs text-ink-2">{registry.response.note}</p>}
                <p className="text-xs text-ink-2">
                  The MOCK registry is set to answer {view.registry.mode === 'unavailable' ? 'as unavailable' : `with a ${view.registry.mode === 'match' ? 'matching' : 'differing'} record`}.
                  A rule administrator can change this in Settings. A real registry needs authorisation and is not connected.
                </p>
              </>
            )}
          </div>
        </li>

        <li className="grid gap-2 px-4 py-3 sm:grid-cols-[13rem_1fr]">
          <p className="font-semibold">Manual check with the issuer</p>
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StateTag check={manual} />
              {canAct && (
                <button className={`${btnSecondary} px-3 py-1.5`} aria-expanded={manualOpen} onClick={() => setManualOpen((v) => !v)}>
                  {manualOpen ? 'Close' : manual ? 'Record an update' : 'Record a manual check'}
                </button>
              )}
            </div>
            {manual && (
              <>
                <By check={manual} />
                <p className="text-sm"><span className="text-ink-2">Asked</span> {manual.source}, {manual.response.contact}</p>
                <p className="text-sm"><span className="text-ink-2">Answer</span> {manual.response.note}</p>
                <Attachment check={manual} />
              </>
            )}
            {manualOpen && (
              <ManualForm documentId={doc.id} issuer={manual?.source ?? view.registry.issuer ?? ''}
                onDone={() => { setManualOpen(false); setNote({ kind: 'success', text: 'Manual check recorded.' }); reload(); }} />
            )}
          </div>
        </li>
      </ul>

      {note && <Notice kind={note.kind}>{note.text}</Notice>}

      {earlier.length > 0 && (
        <div>
          <button className={btnQuiet} aria-expanded={historyOpen} onClick={() => setHistoryOpen((v) => !v)}>
            {historyOpen ? 'Hide' : 'Show'} {earlier.length} earlier check{earlier.length > 1 ? 's' : ''}
          </button>
          {historyOpen && (
            <ul className="mt-2 space-y-2 border-l-2 border-rule pl-4 text-sm">
              {earlier.map((c) => (
                <li key={c.id}>
                  <span className="font-semibold">{METHOD_NAME[c.method] ?? humanize(c.method)}</span>{' '}
                  <StateTag check={c} />
                  {c.method === 'MANUAL' && c.response.note && <span className="block text-ink-2">{c.response.note}</span>}
                  <By check={c} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
