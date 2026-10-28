'use client';

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { humanize, type RegistryMode, type RegistrySetting } from '@/lib/types';
import { Loading, Notice, PageShell, Tag, btnPrimary, input, label, td, th, useMe } from '@/components/ui';

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

export default function SettingsPage() {
  const { me } = useMe();
  const [setting, setSetting] = useState<RegistrySetting | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<RegistryMode>('unavailable');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<RegistrySetting>('/admin/settings/registry').then(({ data, error }) => {
      if (data) { setSetting(data); setMode(data.mode); } else setError(error);
    });
  }, []);

  const canEdit = me?.role === 'rule_admin';

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    setError(null);
    const { data, error } = await fetchApi<RegistrySetting>('/admin/settings/registry', {
      method: 'PUT', body: JSON.stringify({ mode, reason: reason.trim() }),
    });
    setBusy(false);
    if (data) { setSetting(data); setReason(''); setNote(`Saved. Lookups from now on ${mode === 'unavailable' ? 'read as unavailable' : `get a ${mode === 'match' ? 'matching' : 'differing'} record`}. Earlier lookups keep their answers.`); }
    else setError(error);
  };

  return (
    <PageShell
      title="Settings"
      description="How the issuer registry check behaves. The registry is a MOCK: no real registry is connected."
    >
      {error && <div className="mb-4"><Notice kind="error">{error}</Notice></div>}
      {!setting && !error && <Loading what="Loading settings" />}
      {setting && (
        <div className="space-y-10">
          <section aria-labelledby="registry" className="space-y-4">
            <div>
              <h2 id="registry" className="font-serif text-xl font-bold">Issuer registry <Tag tone="pending">MOCK</Tag></h2>
              <p className="mt-1 max-w-2xl text-sm text-ink-2">
                A reviewer can look a certificate, NOC or land record up in its issuer&apos;s registry. A real registry, such as
                DigiLocker or API Setu, needs authorisation, so a MOCK answers instead. Choose how it answers for demonstrations.
              </p>
            </div>
            <form onSubmit={save} className="space-y-4 rounded-sheet border border-rule bg-sheet p-5">
              <fieldset className="space-y-3" disabled={!canEdit || busy}>
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
              {canEdit ? (
                <>
                  <div className="max-w-xl">
                    <label htmlFor="reason" className={label}>Reason for the change</label>
                    <input id="reason" required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} className={input}
                      placeholder="for example demo of a differing record" />
                    <p className="mt-1 text-xs text-ink-2">Kept in the audit trail with the old and new setting.</p>
                  </div>
                  {note && <Notice kind="success">{note}</Notice>}
                  <button type="submit" className={btnPrimary} disabled={busy || mode === setting.mode || reason.trim().length < 3}>
                    {busy ? 'Saving…' : 'Save setting'}
                  </button>
                </>
              ) : (
                <p className="text-sm text-ink-2">Only a rule administrator can change this.</p>
              )}
            </form>

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
          </section>
        </div>
      )}
    </PageShell>
  );
}
