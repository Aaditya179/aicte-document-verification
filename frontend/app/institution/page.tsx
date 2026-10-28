'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import { CATEGORY_LABEL, WORKFLOW_LABEL, type ApplicationRow } from '@/lib/types';
import { EvidenceRequests } from '@/components/requests';
import { Empty, FileNumber, Loading, Notice, PageShell, Tag, btnPrimary, btnQuiet, formatDate, td, th } from '@/components/ui';

export default function InstitutionHome() {
  const [rows, setRows] = useState<ApplicationRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<ApplicationRow[]>('/applications').then(({ data, error }) => (data ? setRows(data) : setError(error)));
  }, []);

  return (
    <PageShell
      title="Your applications"
      description="Prepare an application by uploading its documents. Each file is checked and read as soon as it arrives."
      actions={<Link href="/institution/applications/new" className={btnPrimary}>Start a new application</Link>}
    >
      {error && <Notice kind="error">{error}</Notice>}
      {!rows && !error && <Loading what="Loading your applications" />}
      {rows && rows.length === 0 && <Empty>No applications yet. Start one to upload its documents.</Empty>}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead>
              <tr>
                <th className={th}>File number</th>
                <th className={th}>Type</th>
                <th className={th}>Status</th>
                <th className={th}>Documents</th>
                <th className={th}>Started</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} className="hover:bg-sheet">
                  <td className={td}>
                    <Link href={`/institution/applications/${a.id}`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                      <FileNumber code={a.code} />
                    </Link>
                  </td>
                  <td className={td}>{CATEGORY_LABEL[a.category]}, {a.academic_year}</td>
                  <td className={td}>
                    <Tag tone={a.workflow_status === 'draft' ? 'neutral' : 'active'}>{WORKFLOW_LABEL[a.workflow_status]}</Tag>
                    {a.workflow_status === 'draft' && (
                      <Link href={`/institution/applications/new?application=${a.id}&step=documents`} className={`${btnQuiet} mt-1 block`}>Continue preparing</Link>
                    )}
                  </td>
                  <td className={td}>
                    {a.documents.current}
                    {a.documents.failed_check > 0 && <span className="ml-2 text-conflict">{a.documents.failed_check} failed the file check</span>}
                  </td>
                  <td className={td}>{formatDate(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows && rows.some((a) => a.workflow_status !== 'draft') && (
        <section aria-labelledby="requests" className="mt-10 space-y-3">
          <h2 id="requests" className="font-serif text-xl font-bold">Requests from reviewers</h2>
          <p className="text-sm text-ink-2">Open requests first, with their due dates. Answer each one from its application.</p>
          <EvidenceRequests showApplication />
        </section>
      )}
    </PageShell>
  );
}
