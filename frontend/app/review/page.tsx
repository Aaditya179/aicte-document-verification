'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import { CATEGORY_LABEL, WORKFLOW_LABEL, type ApplicationRow } from '@/lib/types';
import { Empty, FileNumber, Loading, Notice, PageShell, Tag, formatDate, td, th } from '@/components/ui';

export default function ReviewList() {
  const [rows, setRows] = useState<ApplicationRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<ApplicationRow[]>('/applications').then(({ data, error }) => (data ? setRows(data) : setError(error)));
  }, []);

  return (
    <PageShell
      wide
      title="Applications"
      description="Every institution's applications. Open one to see its documents and the values read from each page."
    >
      {error && <Notice kind="error">{error}</Notice>}
      {!rows && !error && <Loading what="Loading applications" />}
      {rows && rows.length === 0 && <Empty>No applications yet. They appear here as institutions start them.</Empty>}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] border-collapse">
            <thead>
              <tr>
                <th className={th}>File number</th>
                <th className={th}>Institution</th>
                <th className={th}>Type</th>
                <th className={th}>Status</th>
                <th className={th}>Documents</th>
                <th className={th}>Submitted</th>
                <th className={th}>Review due</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} className="hover:bg-sheet">
                  <td className={td}>
                    <Link href={`/review/${a.id}`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                      <FileNumber code={a.code} />
                    </Link>
                  </td>
                  <td className={td}>{a.institution.name}<p className="text-xs text-ink-2">{a.institution.city}</p></td>
                  <td className={td}>{CATEGORY_LABEL[a.category]}, {a.academic_year}</td>
                  <td className={td}><Tag tone={a.workflow_status === 'draft' ? 'neutral' : 'active'}>{WORKFLOW_LABEL[a.workflow_status]}</Tag></td>
                  <td className={td}>
                    {a.documents.current}
                    {a.documents.failed_check > 0 && <p className="text-xs text-conflict">{a.documents.failed_check} failed the file check</p>}
                    {a.documents.being_read > 0 && <p className="text-xs text-pending">{a.documents.being_read} being read</p>}
                  </td>
                  <td className={td}>{formatDate(a.submitted_at)}</td>
                  <td className={td}>{formatDate(a.review_deadline)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
