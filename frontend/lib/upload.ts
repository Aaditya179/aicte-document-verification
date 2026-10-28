import { fetchApi } from './api';
import { supabase } from './supabase';
import type { DocumentRow } from './types';

const BUCKET = 'proofpath-documents';
const POLL_MS = 1500;
const POLL_LIMIT = 80; // about two minutes

const BY_EXTENSION: Record<string, string> = { pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' };

/** The browser's type for the file, or the one its extension implies when the browser gives none. */
function mimeOf(file: File) {
  return file.type || BY_EXTENSION[file.name.split('.').pop()?.toLowerCase() ?? ''] || '';
}

export type UploadStep = 'preparing' | 'uploading' | 'checking' | 'reading' | 'done';

/**
 * Upload one document (build spec section 6): the API checks the metadata and returns a signed URL,
 * the file goes straight to private storage, the API checks the file, then reads it in the background.
 */
export async function uploadDocument(
  applicationId: string,
  file: File,
  docType: string,
  category: string | null,
  onStep: (step: UploadStep) => void,
): Promise<{ document: DocumentRow | null; error: string | null }> {
  onStep('preparing');
  const init = await fetchApi<{ document: DocumentRow; upload: { path: string; token: string } }>(
    `/applications/${applicationId}/documents/init`,
    { method: 'POST', body: JSON.stringify({ doc_type: docType, filename: file.name, mime: mimeOf(file), size: file.size, category }) },
  );
  if (!init.data) return { document: null, error: init.error };

  onStep('uploading');
  const { error: uploadError } = await supabase.storage
    .from(BUCKET)
    .uploadToSignedUrl(init.data.upload.path, init.data.upload.token, file, { contentType: mimeOf(file) });
  if (uploadError) return { document: null, error: `The upload did not finish: ${uploadError.message}` };

  onStep('checking');
  const finalized = await fetchApi<DocumentRow>(`/documents/${init.data.document.id}/finalize`, { method: 'POST' });
  if (!finalized.data) return { document: null, error: finalized.error };
  if (finalized.data.integrity_status === 'failed') return { document: finalized.data, error: null };

  onStep('reading');
  for (let i = 0; i < POLL_LIMIT; i++) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    const doc = await fetchApi<DocumentRow>(`/documents/${init.data.document.id}`);
    if (doc.data && (doc.data.processing_status === 'done' || doc.data.processing_status === 'error')) {
      onStep('done');
      return { document: doc.data, error: null };
    }
  }
  return { document: finalized.data, error: 'Reading is taking longer than usual. The list will update when it finishes.' };
}
