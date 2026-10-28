'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Network } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { PageShell, Notice, Badge, card, formatDate } from '@/components/ui';
import { type Pattern, humanize } from '@/lib/types';

const SEVERITY: Record<Pattern['severity'], 'red' | 'amber' | 'neutral'> = { high: 'red', medium: 'amber', low: 'neutral' };
const FILTERS = [['open', 'Open'], ['confirmed', 'Confirmed'], ['dismissed', 'Dismissed'], ['all', 'All']] as const;

export default function PatternsPage() {
  const [status, setStatus] = useState<(typeof FILTERS)[number][0]>('open');
  const [patterns, setPatterns] = useState<Pattern[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<Pattern[]>(`/patterns?status=${status}`).then(({ data, error }) => {
      setPatterns(data);
      setError(data ? null : error);
    });
  }, [status]);

  return (
    <PageShell
      title="Patterns across institutions"
      subtitle="The same land parcel, faculty member or document turning up in more than one application. Each one only shows when applications are compared, never in a single review."
    >
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {FILTERS.map(([value, text]) => (
          <button key={value} type="button" onClick={() => setStatus(value)} aria-pressed={status === value}
            className={`rounded-full border px-3 py-1 text-xs font-semibold cursor-pointer ${status === value
              ? 'border-[#F0D5BE] bg-[#FBF0E4] text-[#C25E26]' : 'border-[#E8E2D8] bg-white text-stone-600 hover:text-stone-900'}`}>
            {text}
          </button>
        ))}
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {!patterns && !error && <div className={`${card} h-32 animate-pulse`} aria-label="Loading patterns" />}
      {patterns?.length === 0 && <Notice>No {status === 'all' ? '' : `${status} `}patterns.</Notice>}
      <ul className="space-y-3">
        {patterns?.map((p) => (
          <li key={p.id} className={card}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold text-stone-900">
                <Network className="h-4 w-4 text-[#C25E26]" aria-hidden="true" /> {humanize(p.kind)}
              </h2>
              <div className="flex gap-1.5">
                <Badge tone={SEVERITY[p.severity]}>{humanize(p.severity)}</Badge>
                <Badge>{humanize(p.status)}</Badge>
              </div>
            </div>
            <p className="mt-1.5 text-sm text-stone-700">{p.summary}</p>
            <p className="mt-2 text-xs text-stone-500">
              {p.institution_ids.length} institutions · {p.case_ids.length} case files · found {formatDate(p.detected_at)}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {p.case_ids.map((id, i) => (
                <Link key={id} href={`/cases/${id}`} className="text-xs font-medium text-[#C25E26] hover:underline">Case file {i + 1}</Link>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
