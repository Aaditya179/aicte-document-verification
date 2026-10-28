'use client';

import React from 'react';
import { fetchApi } from '@/lib/api';
import type { DocumentRow } from '@/lib/types';
import { Tag } from './ui';

/** The file check: is this really a PDF, JPEG or PNG of acceptable size and length. */
export function FileCheckTag({ doc }: { doc: DocumentRow }) {
  if (doc.integrity_status === 'passed') return <Tag tone="ok">File check passed</Tag>;
  if (doc.integrity_status === 'failed') return <Tag tone="conflict">File check failed</Tag>;
  return <Tag tone="neutral">Not checked yet</Tag>;
}

/** Whether the values in the document have been read. */
export function ReadingTag({ doc }: { doc: DocumentRow }) {
  if (doc.integrity_status === 'failed') return <Tag tone="neutral">Not read</Tag>;
  if (doc.processing_status === 'done') return <Tag tone="ok">Read</Tag>;
  if (doc.processing_status === 'error') return <Tag tone="conflict">Could not be read</Tag>;
  return <Tag tone="pending">Being read</Tag>;
}

export function isBeingRead(doc: DocumentRow) {
  return doc.integrity_status !== 'failed' && (doc.processing_status === 'pending' || doc.processing_status === 'processing');
}

/** A short-lived link to the file (the bucket is private). */
export async function documentLink(id: string): Promise<{ url: string | null; mime?: string; error: string | null }> {
  const { data, error } = await fetchApi<{ url: string; mime: string }>(`/documents/${id}/signed-url`);
  return { url: data?.url ?? null, mime: data?.mime, error };
}

export async function openDocument(id: string) {
  // Open the tab first, so the browser treats it as a response to the click
  const tab = window.open('', '_blank');
  const { url, error } = await documentLink(id);
  if (url && tab) tab.location.href = url;
  else {
    tab?.close();
    window.alert(error || 'Could not open the document');
  }
}
