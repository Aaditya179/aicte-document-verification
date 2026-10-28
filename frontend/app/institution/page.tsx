'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { CATEGORY_LABEL, WORKFLOW_LABEL, type Application, type ApplicationRow } from '@/lib/types';
import { Empty, FileNumber, Loading, Notice, PageShell, Tag, btnPrimary, btnSecondary, formatDate, input, label, td, th } from '@/components/ui';

function NewApplication({ onCreated }: { onCreated: (a: Application) => void }) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<Application['category']>('extension_of_approval');
  const [year, setYear] = useState('2027-28');
  const [area, setArea] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return <button className={btnPrimary} onClick={() => setOpen(true)}>Start a new application</button>;

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = await fetchApi<Application>('/applications', {
      method: 'POST',
      body: JSON.stringify({ category, academic_year: year, declared_total_area_sqm: area ? Number(area) : null }),
    });
    setBusy(false);
    if (data) onCreated(data);
    else setError(error);
  };

  return (
    <form onSubmit={create} className="w-full rounded-sheet border border-rule bg-sheet p-5 sm:w-auto">
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="category" className={label}>Type</label>
          <select id="category" className={input} value={category} onChange={(e) => setCategory(e.target.value as Application['category'])}>
            {Object.entries(CATEGORY_LABEL).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="year" className={label}>Academic year</label>
          <input id="year" className={input} value={year} onChange={(e) => setYear(e.target.value)} pattern="20\d{2}-\d{2}" required />
        </div>
        <div>
          <label htmlFor="area" className={label}>Built-up area (sq m)</label>
          <input id="area" className={input} inputMode="decimal" value={area} onChange={(e) => setArea(e.target.value)} placeholder="Optional" />
        </div>
      </div>
      {error && <div className="mt-4"><Notice kind="error">{error}</Notice></div>}
      <div className="mt-4 flex gap-3">
        <button type="submit" className={btnPrimary} disabled={busy}>{busy ? 'Creating…' : 'Create application'}</button>
        <button type="button" className={btnSecondary} onClick={() => setOpen(false)} disabled={busy}>Cancel</button>
      </div>
    </form>
  );
}

export default function InstitutionHome() {
  const [rows, setRows] = useState<ApplicationRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();

  useEffect(() => {
    fetchApi<ApplicationRow[]>('/applications').then(({ data, error }) => (data ? setRows(data) : setError(error)));
  }, []);

  return (
    <PageShell
      title="Your applications"
      description="Prepare an application by uploading its documents. Each file is checked and read as soon as it arrives."
      actions={<NewApplication onCreated={(a) => router.push(`/institution/applications/${a.id}`)} />}
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
                  <td className={td}><Tag tone={a.workflow_status === 'draft' ? 'neutral' : 'active'}>{WORKFLOW_LABEL[a.workflow_status]}</Tag></td>
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
    </PageShell>
  );
}
