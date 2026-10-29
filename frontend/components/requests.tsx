'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import type { DocumentRow, EvidenceRequestRow } from '@/lib/types';
import { Empty, FileNumber, Loading, Notice, Tag, formatDate, input, label } from './ui';

function FulfilForm({ request, documents, docLabel, onDone }: {
  request: EvidenceRequestRow;
  documents: DocumentRow[];
  docLabel: (d: DocumentRow) => string;
  onDone: () => void;
}) {
  // The newest current document is usually the replacement just uploaded
  const choices = documents.filter((d) => d.status === 'current' && d.integrity_status === 'passed')
    .sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));
  // Until the institution picks one, follow the newest choice: a replacement uploaded after this form
  // appeared supersedes the document picked before, which the API would then refuse
  const [picked, setPicked] = useState<string | null>(null);
  const documentId = picked !== null && (picked === '' || choices.some((d) => d.id === picked)) ? picked : choices[0]?.id ?? '';
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await fetchApi(`/evidence-requests/${request.id}/fulfil`, {
      method: 'POST', body: JSON.stringify({ note: note.trim(), document_id: documentId || null }),
    });
    setBusy(false);
    if (error) setError(error);
    else onDone();
  };

  return (
    <form onSubmit={submit} className="mt-3 space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`doc-${request.id}`} className={label}>Document that answers it</label>
          <select id={`doc-${request.id}`} className={input} value={documentId} onChange={(e) => setPicked(e.target.value)}>
            <option value="">No document, a note only</option>
            {choices.map((d) => <option key={d.id} value={d.id}>{docLabel(d)}, version {d.version} ({d.original_name})</option>)}
          </select>
          <p className="mt-1 text-xs text-ink-2">Upload a replacement first with the form above; it becomes the next version.</p>
        </div>
        <div>
          <label htmlFor={`note-${request.id}`} className={label}>Your answer</label>
          <textarea id={`note-${request.id}`} required minLength={3} rows={3} className={input} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <button type="submit" disabled={busy || note.trim().length < 3}
        className="inline-flex items-center rounded-control bg-ink px-4 py-2 text-sm font-semibold text-sheet hover:bg-ink-2 disabled:cursor-not-allowed disabled:opacity-50">
        {busy ? 'Sending…' : 'Send to the reviewer'}
      </button>
    </form>
  );
}

/** What reviewers asked this institution for. With `documents`, open requests can be answered here. */
export function EvidenceRequests({ applicationId, documents, docLabel, onAnswered, showApplication = false }: {
  applicationId?: string;
  documents?: DocumentRow[];
  docLabel?: (d: DocumentRow) => string;
  onAnswered?: () => void;
  showApplication?: boolean;
}) {
  const [rows, setRows] = useState<EvidenceRequestRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    fetchApi<EvidenceRequestRow[]>(`/evidence-requests${applicationId ? `?application_id=${applicationId}` : ''}`)
      .then(({ data, error }) => (data ? setRows(data) : setError(error)));
  }, [applicationId, version]);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!rows) return <Loading what="Loading requests" />;
  if (rows.length === 0) return <Empty>No requests from reviewers.</Empty>;

  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.id} className={`rounded-sheet border bg-sheet p-4 ${r.status === 'open' ? 'border-pending' : 'border-rule'}`}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              {showApplication && (
                <Link href={`/institution/applications/${r.application.id}`} className="text-sm underline decoration-rule-strong underline-offset-4">
                  <FileNumber code={r.application.code} />
                </Link>
              )}
              <p className="font-semibold">{r.finding.title}</p>
            </div>
            {r.status === 'open'
              ? <Tag tone="pending">Due {formatDate(r.due_date)}</Tag>
              : <Tag tone="ok">{r.status === 'fulfilled' ? 'Answered' : 'Withdrawn'}</Tag>}
          </div>
          <p className="mt-2 text-sm"><span className="text-ink-2">The reviewer asks: </span>{r.message}</p>
          <p className="text-xs text-ink-2">Asked on {formatDate(r.created_at)}</p>
          {r.status === 'open' && documents && docLabel && (
            <FulfilForm request={r} documents={documents} docLabel={docLabel} onDone={() => { setVersion((v) => v + 1); onAnswered?.(); }} />
          )}
        </li>
      ))}
    </ul>
  );
}
