'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { humanize, ruleStage, type Rule } from '@/lib/types';
import { paramsText } from '@/components/rules';
import { Empty, Loading, Notice, PageShell, Tag, btnPrimary, btnSecondary, formatDate, input, label, td, th } from '@/components/ui';

type Group = { code: string; inForce: Rule | undefined; working: Rule | undefined; latest: Rule; count: number };

function DraftFromText({ onCancel }: { onCancel: () => void }) {
  const router = useRouter();
  const [text, setText] = useState('');
  const [source, setSource] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<{ rule: Rule; drafted_by: string }>('/rules/draft-from-text', {
      method: 'POST', body: JSON.stringify({ text: text.trim(), source_reference: source.trim() }),
    });
    setBusy(false);
    if (data) router.push(`/admin/rules/${data.rule.id}?drafted=${data.drafted_by}`);
    else setError(error);
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-sheet border border-rule bg-sheet p-5">
      <div>
        <h2 className="font-serif text-xl font-bold">Draft a version from regulation text</h2>
        <p className="mt-1 max-w-2xl text-sm text-ink-2">
          Paste the clause. ProofPath finds a threshold one of its checks applies (a minimum area, an area tolerance, a photo age)
          and saves it as a draft version of that rule, quoting the clause. Check every value before you submit it; a second rule
          administrator approves it before it is used.
        </p>
      </div>
      <div>
        <label htmlFor="clause" className={label}>Regulation text</label>
        <textarea id="clause" required minLength={20} maxLength={6000} rows={5} value={text} onChange={(e) => setText(e.target.value)}
          className={input} placeholder="for example: The total built-up area shall be not less than 4,500 sq m." />
      </div>
      <div className="max-w-xl">
        <label htmlFor="source" className={label}>Where it comes from</label>
        <input id="source" required minLength={3} maxLength={300} value={source} onChange={(e) => setSource(e.target.value)} className={input}
          placeholder="for example illustrative handbook, section 3.2" />
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <div className="flex flex-wrap gap-3">
        <button type="submit" className={btnPrimary} disabled={busy || text.trim().length < 20 || source.trim().length < 3}>
          {busy ? 'Reading the text…' : 'Draft a version'}
        </button>
        <button type="button" className={btnSecondary} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);

  useEffect(() => {
    fetchApi<Rule[]>('/rules').then(({ data, error }) => (data ? setRules(data) : setError(error)));
  }, []);

  const groups = useMemo<Group[]>(() => {
    const by = new Map<string, Rule[]>();
    for (const r of rules ?? []) by.set(r.rule_code, [...(by.get(r.rule_code) ?? []), r]);
    return [...by.entries()].map(([code, versions]) => {
      const sorted = [...versions].sort((a, b) => b.version - a.version);
      return {
        code, latest: sorted[0], count: sorted.length,
        inForce: sorted.find((r) => r.status === 'active'),
        working: sorted.find((r) => r.status === 'draft' || r.status === 'pending_approval'),
      };
    }).sort((a, b) => (a.latest.check ?? 'Z').localeCompare(b.latest.check ?? 'Z', undefined, { numeric: true }) || a.code.localeCompare(b.code));
  }, [rules]);

  const waiting = groups.filter((g) => g.working?.status === 'pending_approval' && !g.working.approved_by);

  return (
    <PageShell
      wide
      title="Rules"
      description="The rules each application is checked against. A change is a new version, approved by a second rule administrator. All rules are illustrative, not official AICTE rules."
      actions={!drafting && rules ? <button className={btnSecondary} onClick={() => setDrafting(true)}>Draft from regulation text</button> : undefined}
    >
      {error && <Notice kind="error">{error}</Notice>}
      {!rules && !error && <Loading what="Loading rules" />}
      {drafting && <div className="mb-8"><DraftFromText onCancel={() => setDrafting(false)} /></div>}
      {rules && rules.length === 0 && <Empty>No rules yet. Run the reference data migration (0003) to add the illustrative set.</Empty>}
      {waiting.length > 0 && (
        <div className="mb-6">
          <Notice kind="warning">
            {waiting.length === 1 ? 'One version is' : `${waiting.length} versions are`} waiting for a second rule administrator:{' '}
            {waiting.map((g, i) => (
              <React.Fragment key={g.code}>
                {i > 0 && ', '}
                <Link className="font-semibold underline underline-offset-4" href={`/admin/rules/${g.working!.id}`}>{g.code} version {g.working!.version}</Link>
              </React.Fragment>
            ))}
          </Notice>
        </div>
      )}
      {groups.length > 0 && (
        <div className="overflow-x-auto rounded-sheet border border-rule bg-sheet shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent)]">
          <table className="w-full min-w-[64rem] border-collapse">
            <thead>
              <tr>
                <th className={th}>Rule</th>
                <th className={th}>What it checks</th>
                <th className={th}>Thresholds in force</th>
                <th className={th}>In force</th>
                <th className={th}>Being changed</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => {
                const shown = g.inForce ?? g.latest;
                return (
                  <tr key={g.code}>
                    <td className={td}>
                      <Link href={`/admin/rules/${shown.id}`} className="font-semibold tabular-nums underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                        {g.code}
                      </Link>
                      <p className="text-xs text-ink-2">{shown.check ? `Check ${shown.check}` : humanize(shown.check_type)}, {g.count} version{g.count > 1 ? 's' : ''}</p>
                    </td>
                    <td className={td}>
                      <p className="font-semibold">{shown.title}</p>
                      <p className="text-ink-2">{shown.description}</p>
                    </td>
                    <td className={td}>{g.inForce ? paramsText(g.inForce.params) : '—'}</td>
                    <td className={td}>
                      {g.inForce ? (
                        <>
                          <p>Version {g.inForce.version}</p>
                          <p className="text-xs text-ink-2">from {formatDate(g.inForce.effective_from)}{g.inForce.effective_to ? ` to ${formatDate(g.inForce.effective_to)}` : ''}</p>
                        </>
                      ) : <Tag>None in force</Tag>}
                    </td>
                    <td className={td}>
                      {g.working ? (
                        <Link href={`/admin/rules/${g.working.id}`} className="inline-flex flex-col gap-1">
                          <span className="underline decoration-rule-strong underline-offset-4">Version {g.working.version}</span>
                          <Tag tone={ruleStage(g.working).tone}>{ruleStage(g.working).label}</Tag>
                        </Link>
                      ) : <span className="text-ink-3">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
