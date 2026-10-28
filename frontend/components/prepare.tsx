'use client';

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { UPLOAD_STEP_TEXT, uploadDocument, type UploadStep } from '@/lib/upload';
import { humanize, type DocumentRow, type ExtractedField, type FacultyRow } from '@/lib/types';
import { FileCheckTag, ReadingTag, isBeingRead, openDocument } from './documents';
import { Mark, Notice, Tag, btnQuiet, btnSecondary, formatBytes, formatDateTime } from './ui';

/** The values read from one of the institution's own documents, so it can see at once whether the file read well. */
function ValuesRead({ doc }: { doc: DocumentRow }) {
  const [values, setValues] = useState<{ fields: ExtractedField[]; faculty: FacultyRow[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<{ fields: ExtractedField[]; faculty: FacultyRow[] }>(`/documents/${doc.id}/fields`)
      .then(({ data, error }) => (data ? setValues(data) : setError(error)));
  }, [doc.id]);

  if (error) return <p className="text-xs text-conflict">{error}</p>;
  if (!values) return <p className="text-xs text-ink-2">Loading the values read…</p>;
  if (values.fields.length === 0 && values.faculty.length === 0) return <p className="text-xs text-ink-2">No values are read from this kind of document.</p>;
  const unclear = values.fields.filter((f) => f.review_state === 'needs_confirmation' || !f.original_value);
  return (
    <div className="space-y-2">
      <dl className="grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
        {values.fields.map((f) => (
          <div key={f.id} className="flex flex-wrap items-baseline gap-x-2">
            <dt className="text-ink-2">{humanize(f.field_name)}</dt>
            <dd>
              {f.original_value ? <Mark>{f.original_value}</Mark> : <span className="font-semibold text-conflict">not found</span>}
              {f.page_number && <span className="ml-1 text-xs text-ink-2">page {f.page_number}</span>}
              {f.review_state === 'needs_confirmation' && <span className="ml-1"><Tag tone="pending">Unclear</Tag></span>}
            </dd>
          </div>
        ))}
      </dl>
      {values.faculty.length > 0 && <p className="text-sm text-ink-2">{values.faculty.length} faculty members read from the list.</p>}
      {unclear.length > 0 && (
        <p className="text-xs text-pending">
          {unclear.length === 1 ? 'One value' : `${unclear.length} values`} could not be read clearly. A clearer copy helps; dates read best with the month in words.
          {unclear.find((f) => f.review_reason)?.review_reason && <span className="block">{unclear.find((f) => f.review_reason)!.review_reason}.</span>}
        </p>
      )}
    </div>
  );
}

/**
 * One document the application needs: what is uploaded now, its file check, the values read from it,
 * and a control to upload it or a new version.
 */
export function DocumentSlot({ applicationId, docType, label, category, required, documents, focused, onUploaded }: {
  applicationId: string;
  docType: string;
  label: string;
  category?: string;
  required: boolean;
  documents: DocumentRow[];
  focused: boolean;
  onUploaded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<UploadStep | null>(null);
  const [result, setResult] = useState<{ kind: 'success' | 'error' | 'warning'; text: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const id = `slot-${docType}${category ? `-${category}` : ''}`;

  const mine = documents.filter((d) => d.doc_type === docType && d.status === 'current' && (!category || d.photo_category === category));
  const latest = mine[0];                                         // newest first
  const inUse = mine.find((d) => d.integrity_status === 'passed');
  const busy = step !== null && step !== 'done';

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setResult(null);
    const { document, error } = await uploadDocument(applicationId, file, docType, category ?? null, setStep);
    setStep(null);
    if (error) setResult({ kind: document ? 'warning' : 'error', text: error });
    else if (document?.integrity_status === 'failed') setResult({ kind: 'error', text: `${file.name} failed the file check: ${document.integrity_note}` });
    else if (document?.processing_status === 'error') setResult({ kind: 'warning', text: `${file.name} passed the file check but could not be read: ${document.processing_note}` });
    else setResult({ kind: 'success', text: `${file.name} passed the file check and was read. Check the values below.` });
    setFile(null);
    setInputKey((k) => k + 1);
    onUploaded();
  };

  return (
    <li id={id} className={`scroll-mt-6 rounded-sheet border bg-sheet p-4 ${focused ? 'border-ink outline outline-2 outline-offset-2 outline-ink' : 'border-rule'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">
            {label} {required ? <Tag tone="active">Required</Tag> : <Tag>Optional</Tag>}
          </h3>
          {latest ? (
            <p className="mt-0.5 text-sm text-ink-2">
              {latest.original_name}, {formatBytes(latest.size_bytes)}, version {latest.version}, uploaded {formatDateTime(latest.uploaded_at)}
            </p>
          ) : (
            <p className="mt-0.5 text-sm text-ink-2">Not uploaded yet.</p>
          )}
        </div>
        {latest && (
          <div className="flex flex-wrap items-center gap-1.5">
            <FileCheckTag doc={latest} />
            <ReadingTag doc={latest} />
            {latest.integrity_status !== 'pending' && <button className={btnQuiet} onClick={() => openDocument(latest.id)}>Open</button>}
          </div>
        )}
      </div>

      {latest?.integrity_status === 'failed' && (
        <div className="mt-3">
          <Notice kind="error">
            {latest.integrity_note}. Upload the file again as a PDF, JPEG or PNG.
            {inUse && inUse.id !== latest.id && ` Version ${inUse.version} is still the one in use.`}
          </Notice>
        </div>
      )}
      {latest?.processing_status === 'error' && latest.integrity_status === 'passed' && (
        <div className="mt-3"><Notice kind="warning">{latest.processing_note}</Notice></div>
      )}
      {latest && isBeingRead(latest) && <p className="mt-3 text-sm text-pending" role="status">Reading the values in it…</p>}
      {latest?.processing_status === 'done' && latest.integrity_status === 'passed' && (
        <div className="mt-3 border-t border-rule pt-3"><ValuesRead key={latest.id} doc={latest} /></div>
      )}

      <form onSubmit={upload} className="mt-3 flex flex-wrap items-center gap-3">
        <label htmlFor={`${id}-file`} className="sr-only">{latest ? `New version of the ${label.toLowerCase()}` : `File for the ${label.toLowerCase()}`}</label>
        <input key={inputKey} id={`${id}-file`} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          className="block min-w-0 max-w-full text-sm file:mr-3 file:rounded-control file:border file:border-ink file:bg-sheet file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} disabled={busy} />
        <button type="submit" className={`${btnSecondary} px-3 py-1.5`} disabled={!file || busy}>
          {busy ? 'Uploading…' : latest ? 'Upload new version' : 'Upload'}
        </button>
        {step && <p className="text-sm text-ink-2" role="status" aria-live="polite">{UPLOAD_STEP_TEXT[step]}</p>}
      </form>
      {result && <div className="mt-3"><Notice kind={result.kind}>{result.text}</Notice></div>}
    </li>
  );
}
