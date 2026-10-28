'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { UPLOAD_STEP_TEXT, uploadDocument, type UploadStep } from '@/lib/upload';
import { PHOTO_CATEGORY_LABEL, type ApplicationDetail, type DocumentRow, type Reference } from '@/lib/types';
import { Checklist, FileCover } from '@/components/FileCover';
import { EvidenceRequests } from '@/components/requests';
import { RoomTable } from '@/components/rooms';
import { FileCheckTag, ReadingTag, isBeingRead, openDocument } from '@/components/documents';
import { Empty, Loading, Notice, btnPrimary, btnQuiet, formatBytes, formatDateTime, input, label, td, th } from '@/components/ui';

function UploadForm({ applicationId, reference, onUploaded }: {
  applicationId: string;
  reference: Reference;
  onUploaded: () => void;
}) {
  const [docType, setDocType] = useState('application_form');
  const [category, setCategory] = useState('lab');
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<UploadStep | null>(null);
  const [result, setResult] = useState<{ kind: 'success' | 'error' | 'warning'; text: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);

  const type = reference.document_types.find((t) => t.code === docType);
  const busy = step !== null && step !== 'done';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setResult(null);
    const { document, error } = await uploadDocument(applicationId, file, docType, type?.is_photo ? category : null, setStep);
    setStep(null);
    if (error) setResult({ kind: document ? 'warning' : 'error', text: error });
    else if (document?.integrity_status === 'failed') setResult({ kind: 'error', text: `${file.name} failed the file check: ${document.integrity_note}` });
    else if (document?.processing_status === 'error') setResult({ kind: 'warning', text: `${file.name} passed the file check but could not be read: ${document.processing_note}` });
    else setResult({ kind: 'success', text: `${file.name} passed the file check and was read.` });
    setFile(null);
    setInputKey((k) => k + 1);
    onUploaded();
  };

  return (
    <form onSubmit={submit} className="rounded-sheet border border-rule bg-sheet p-5">
      <h2 className="font-serif text-xl font-bold">Upload a document</h2>
      <p className="mt-1 text-sm text-ink-2">PDF, JPEG or PNG. A new upload of the same type replaces the current one as its next version.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_1fr_1.4fr]">
        <div>
          <label htmlFor="doc_type" className={label}>Document</label>
          <select id="doc_type" className={input} value={docType} onChange={(e) => setDocType(e.target.value)} disabled={busy}>
            {reference.document_types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
          </select>
        </div>
        {type?.is_photo ? (
          <div>
            <label htmlFor="photo_category" className={label}>The photo shows</label>
            <select id="photo_category" className={input} value={category} onChange={(e) => setCategory(e.target.value)} disabled={busy}>
              {Object.entries(PHOTO_CATEGORY_LABEL).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
            </select>
          </div>
        ) : <div className="hidden sm:block" />}
        <div>
          <label htmlFor="file" className={label}>File</label>
          <input key={inputKey} id="file" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            className="block w-full text-sm file:mr-3 file:rounded-control file:border file:border-ink file:bg-sheet file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} disabled={busy} />
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="submit" className={btnPrimary} disabled={!file || busy}>{busy ? 'Uploading…' : 'Upload'}</button>
        {step && <p className="text-sm text-ink-2" role="status" aria-live="polite">{UPLOAD_STEP_TEXT[step]}</p>}
      </div>
      {result && <div className="mt-4"><Notice kind={result.kind}>{result.text}</Notice></div>}
    </form>
  );
}

function DocumentsTable({ documents, types }: { documents: DocumentRow[]; types: Record<string, string> }) {
  if (documents.length === 0) return <Empty>No documents yet. Upload the first one above.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse">
        <thead>
          <tr>
            <th className={th}>Document</th>
            <th className={th}>File</th>
            <th className={th}>File check</th>
            <th className={th}>Values</th>
            <th className={th}>Uploaded</th>
            <th className={th}><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {documents.map((d) => (
            <tr key={d.id} className={d.status === 'superseded' ? 'text-ink-3' : ''}>
              <td className={td}>
                <p className="font-semibold">{types[d.doc_type] ?? d.doc_type}{d.photo_category && `, ${PHOTO_CATEGORY_LABEL[d.photo_category] ?? d.photo_category}`}</p>
                <p className="text-xs text-ink-2">Version {d.version}{d.status === 'superseded' && ', replaced by a newer version'}</p>
              </td>
              <td className={`${td} max-w-56 break-words`}>
                {d.original_name}
                <p className="text-xs text-ink-2">{formatBytes(d.size_bytes)}{d.page_count ? `, ${d.page_count} page${d.page_count > 1 ? 's' : ''}` : ''}</p>
              </td>
              <td className={td}>
                <FileCheckTag doc={d} />
                {d.integrity_note && <p className="mt-1 max-w-56 text-xs text-conflict">{d.integrity_note}</p>}
              </td>
              <td className={td}>
                <ReadingTag doc={d} />
                {d.processing_note && d.integrity_status !== 'failed' && <p className="mt-1 max-w-56 text-xs text-ink-2">{d.processing_note}</p>}
              </td>
              <td className={td}>{formatDateTime(d.uploaded_at)}</td>
              <td className={td}>
                {d.integrity_status !== 'pending' && <button className={btnQuiet} onClick={() => openDocument(d.id)}>Open</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [reference, setReference] = useState<Reference | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    fetchApi<ApplicationDetail>(`/applications/${id}`).then(({ data, error }) => (data ? setDetail(data) : setError(error)));
  }, [id, version]);

  useEffect(() => {
    fetchApi<Reference>('/reference').then(({ data, error }) => (data ? setReference(data) : setError(error)));
  }, []);

  // Keep the list current while any document is still being read
  const reading = detail?.documents.some(isBeingRead) ?? false;
  useEffect(() => {
    if (!reading) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [reading, load]);

  if (error) return <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6"><Notice kind="error">{error}</Notice></div>;
  if (!detail || !reference) return <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6"><Loading what="Opening the application" /></div>;

  const types = Object.fromEntries(reference.document_types.map((t) => [t.code, t.label]));
  const editable = detail.application.workflow_status === 'draft' || detail.application.workflow_status === 'awaiting_institution';

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    const { error } = await fetchApi(`/applications/${id}/submit`, { method: 'POST' });
    setSubmitting(false);
    if (error) setSubmitError(error);
    else load();
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-10 px-4 py-8 sm:px-6">
      <div>
        <Link href="/institution" className={btnQuiet}>Your applications</Link>
        <div className="mt-4">
          <FileCover detail={detail}>
            {editable && (
              <p className="mt-4 text-sm">
                <Link href={`/institution/applications/new?application=${id}&step=${detail.application.workflow_status === 'draft' ? 'documents' : 'preflight'}`} className={btnPrimary}>
                  {detail.application.workflow_status === 'draft' ? 'Continue in guided steps' : 'Run the pre-flight check'}
                </Link>
                <span className="ml-3 text-ink-2">Upload by document, see what was read, and check what to fix before submitting.</span>
              </p>
            )}
          </FileCover>
        </div>
      </div>

      <Checklist detail={detail} />

      {detail.application.workflow_status !== 'draft' && (
        <section aria-labelledby="requests" className="space-y-3">
          <h2 id="requests" className="font-serif text-xl font-bold">Requests from reviewers</h2>
          {detail.application.workflow_status === 'awaiting_institution' && (
            <p className="text-sm text-ink-2">A reviewer needs more from you. Upload a replacement below if one is asked for, then answer each request.</p>
          )}
          <EvidenceRequests applicationId={id} documents={detail.documents} onAnswered={load}
            docLabel={(d) => `${types[d.doc_type] ?? d.doc_type}${d.photo_category ? `, ${PHOTO_CATEGORY_LABEL[d.photo_category] ?? d.photo_category}` : ''}`} />
        </section>
      )}

      {editable ? (
        <UploadForm applicationId={id} reference={reference} onUploaded={load} />
      ) : (
        <Notice kind="info">This application is with the reviewers, so its documents can no longer be changed unless a reviewer asks for more.</Notice>
      )}

      <section aria-labelledby="rooms" className="space-y-3">
        <h2 id="rooms" className="font-serif text-xl font-bold">Room table</h2>
        <p className="text-sm text-ink-2">Each room on the floor plan with its length and width. Their areas should add up to the declared built-up area.</p>
        <RoomTable applicationId={id} canEdit={editable} />
      </section>

      <section aria-labelledby="documents">
        <h2 id="documents" className="mb-3 font-serif text-xl font-bold">Documents</h2>
        <DocumentsTable documents={detail.documents} types={types} />
      </section>

      {detail.application.workflow_status === 'draft' && (
        <section className="border-t border-rule pt-6">
          <h2 className="font-serif text-xl font-bold">Submit for review</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-2">
            Submitting sends the application to the scrutiny reviewers. You can no longer change its documents
            unless a reviewer asks you for more.
          </p>
          {submitError && <div className="mt-3"><Notice kind="error">{submitError}</Notice></div>}
          <button className={`${btnPrimary} mt-4`} onClick={submit} disabled={submitting || reading || detail.documents.length === 0}>
            {submitting ? 'Submitting…' : reading ? 'Wait until every document is read' : 'Submit for review'}
          </button>
        </section>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-5xl px-4 py-8 sm:px-6"><Loading what="Opening the application" /></div>}>
      <ApplicationPage />
    </Suspense>
  );
}
