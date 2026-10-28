'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { PageShell, Notice, Badge, card, formatDate, useMe } from '@/components/ui';
import { type CaseRow, STATUS_META, humanize } from '@/lib/types';

const CASE_STATUS: Record<CaseRow['status'], string> = { open: 'Open', in_review: 'In review', closed: 'Closed' };

export default function DashboardPage() {
  const { me, error: meError } = useMe();
  const [cases, setCases] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me || me.role === 'admin') return;
    fetchApi<CaseRow[]>('/cases').then(({ data, error }) => {
      setCases(data);
      setError(data ? null : error);
    });
  }, [me]);

  if (meError) {
    return <PageShell title="Case files"><Notice kind="error">{meError}. <Link href="/login" className="underline">Sign in</Link></Notice></PageShell>;
  }
  if (me?.role === 'admin') {
    return <PageShell title="Administration"><Notice>The administrator manages accounts and has no access to case files.</Notice></PageShell>;
  }

  return (
    <PageShell
      title="Case files"
      subtitle={me?.role === 'institution'
        ? 'Your applications, and what each one still needs.'
        : 'Every application, with how many fields are verified, in conflict or unverified. Conflicts first.'}
    >
      {error && <Notice kind="error">{error}</Notice>}
      {!cases && !error && <div className={`${card} h-32 animate-pulse`} aria-label="Loading case files" />}
      {cases?.length === 0 && <Notice>No case files yet.</Notice>}
      {cases && cases.length > 0 && (
        <ul className="divide-y divide-[#F0EBE3] rounded-2xl border border-[#E8E2D8] bg-white">
          {[...cases].sort((a, b) => b.checks.conflict - a.checks.conflict).map((c) => (
            <li key={c.id}>
              <Link href={`/cases/${c.id}`} className="group flex flex-wrap items-center gap-4 px-5 py-4 hover:bg-[#FAF7F2]">
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-sm font-bold text-[#C25E26]">{c.case_no}</p>
                  <p className="text-sm text-stone-900">{c.institutions?.name}</p>
                  <p className="text-xs text-stone-500">{humanize(c.application_type)} · {c.academic_year} · opened {formatDate(c.created_at)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {(['conflict', 'unverified', 'verified'] as const).map((s) => (
                    <Badge key={s} tone={c.checks[s] ? STATUS_META[s].tone : 'neutral'}>{c.checks[s]} {STATUS_META[s].label.toLowerCase()}</Badge>
                  ))}
                  <Badge>{CASE_STATUS[c.status]}</Badge>
                </div>
                <ChevronRight className="h-4 w-4 text-stone-400 group-hover:text-[#C25E26]" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}
