'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import { FINDING_STATUS_LABEL, FINDING_TYPE_LABEL, type CrossApplication, type CrossFlag } from '@/lib/types';
import { Empty, FileNumber, Loading, Notice, PageShell, Tag, btnQuiet, formatDate, td, th } from '@/components/ui';

const ORDER: CrossFlag['finding_type'][] = ['GHOST_FACULTY', 'PHOTO_REUSE', 'REUSED_IDENTIFIER'];

function AppCell({ app }: { app: CrossApplication | null }) {
  if (!app) return <span className="text-ink-3">—</span>;
  return (
    <>
      <Link href={`/review/${app.id}`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
        <FileNumber code={app.code} />
      </Link>
      <p className="text-sm text-ink-2">{app.institution.name}</p>
    </>
  );
}

/** Each pair is flagged from both sides; the list shows it once, with the side flagged first on the left. */
function pairs(flags: CrossFlag[]) {
  const seen = new Map<string, CrossFlag & { both: boolean }>();
  for (const f of flags) {
    const ends = [f.application?.code ?? '', f.related_application?.code ?? ''].sort().join('~');
    const key = `${f.finding_type}|${ends}|${f.finding_type === 'GHOST_FACULTY' ? f.finding_key.split('|')[3] ?? '' : ''}`;
    const prior = seen.get(key);
    if (prior) prior.both = true;
    else seen.set(key, { ...f, both: false });
  }
  return [...seen.values()];
}

export default function CrossFlags() {
  const [flags, setFlags] = useState<CrossFlag[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<CrossFlag[]>('/cross').then(({ data, error }) => (data ? setFlags(data) : setError(error)));
  }, []);

  const groups = ORDER.map((t) => ({ type: t, rows: pairs((flags ?? []).filter((f) => f.finding_type === t)) }));

  return (
    <PageShell
      wide
      title="Flags across institutions"
      description="The same faculty member, photo or identifier in applications from different institutions. Candidates for review, shown to reviewers only."
      actions={<Link href="/review" className={btnQuiet}>Review queue</Link>}
    >
      <p className="mb-6 max-w-2xl text-sm text-ink-2">
        This list shows masked IDs only. Names are on each case page. Institutions never see these flags, and evidence cannot be requested on them.
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      {!flags && !error && <Loading what="Loading flags" />}
      {flags && flags.length === 0 && <Empty>No unresolved flags across institutions. They appear here when validation finds one.</Empty>}
      {flags && flags.length > 0 && (
        <div className="space-y-10">
          {groups.filter((g) => g.rows.length > 0).map((g) => (
            <section key={g.type} aria-labelledby={`g-${g.type}`}>
              <h2 id={`g-${g.type}`} className="mb-3 font-serif text-xl font-bold">
                {FINDING_TYPE_LABEL[g.type]} <span className="font-sans text-base font-normal text-ink-2">({g.rows.length})</span>
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[50rem] border-collapse">
                  <thead>
                    <tr>
                      <th className={th}>Application</th>
                      <th className={th}>Matches</th>
                      <th className={th}>What matches</th>
                      <th className={th}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.rows.map((f) => (
                      <tr key={f.id}>
                        <td className={td}><AppCell app={f.application} /></td>
                        <td className={td}><AppCell app={f.related_application} /></td>
                        <td className={td}>
                          {f.title}
                          <p className="text-xs text-ink-2">Found {formatDate(f.created_at)}{f.both && ', flagged on both applications'}</p>
                        </td>
                        <td className={td}><Tag tone={f.status === 'open' ? 'conflict' : 'pending'}>{FINDING_STATUS_LABEL[f.status]}</Tag></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}
    </PageShell>
  );
}
