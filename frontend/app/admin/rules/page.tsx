'use client';

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { humanize, type Rule } from '@/lib/types';
import { Empty, Loading, Notice, PageShell, Tag, formatDate, td, th } from '@/components/ui';

function params(p: Record<string, unknown>) {
  const entries = Object.entries(p);
  if (entries.length === 0) return '—';
  return entries.map(([k, v]) => `${humanize(k)}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join('; ');
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<Rule[]>('/rules').then(({ data, error }) => (data ? setRules(data) : setError(error)));
  }, []);

  return (
    <PageShell
      wide
      title="Rules"
      description="The rules each application is checked against, with their versions and thresholds. All are illustrative, not official AICTE rules."
    >
      {error && <Notice kind="error">{error}</Notice>}
      {!rules && !error && <Loading what="Loading rules" />}
      {rules && rules.length === 0 && <Empty>No rules yet. Run the reference data migration (0003) to add the illustrative set.</Empty>}
      {rules && rules.length > 0 && (
        <>
          <p className="mb-4 text-sm text-ink-2">Writing, approving and retiring rules arrives with rule governance. For now the list is read-only.</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[60rem] border-collapse">
              <thead>
                <tr>
                  <th className={th}>Rule</th>
                  <th className={th}>What it checks</th>
                  <th className={th}>Thresholds</th>
                  <th className={th}>Severity</th>
                  <th className={th}>Status</th>
                  <th className={th}>In force from</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td className={td}>
                      <p className="font-semibold tabular-nums">{r.rule_code}</p>
                      <p className="text-xs text-ink-2">Version {r.version}</p>
                    </td>
                    <td className={td}>
                      <p className="font-semibold">{r.title}</p>
                      <p className="text-ink-2">{r.description}</p>
                    </td>
                    <td className={td}>{params(r.params)}</td>
                    <td className={td}>{r.severity ? humanize(r.severity) : '—'}</td>
                    <td className={td}><Tag tone={r.status === 'active' ? 'active' : 'neutral'}>{humanize(r.status)}</Tag></td>
                    <td className={td}>{formatDate(r.effective_from)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </PageShell>
  );
}
