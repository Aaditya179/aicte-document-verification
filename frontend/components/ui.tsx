'use client';

import React, { useEffect, useState } from 'react';
import { CircleAlert, CircleCheck, Clock, Info } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import type { Role } from '@/lib/types';

import { sheet, card, btnPrimary, btnSecondary, btnQuiet, input, label, th, td } from './styles';

export { sheet, card, btnPrimary, btnSecondary, btnQuiet, input, label, th, td };

export function PageShell({ title, description, actions, children, wide = false }: {
  title: React.ReactNode;
  /** One line saying what this screen is for (build spec section 13) */
  description: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`mx-auto w-full ${wide ? 'max-w-7xl' : 'max-w-5xl'} px-4 py-8 sm:px-6`}>
      <div className="ledger-rule mb-8 flex flex-wrap items-end justify-between gap-4 pb-6">
        <div className="max-w-2xl">
          <h1 className="font-serif text-3xl font-extrabold leading-[1.15] tracking-[-0.01em] sm:text-4xl">{title}</h1>
          <p className="mt-3 max-w-[65ch] text-ink-2">{description}</p>
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'error' | 'success' | 'warning'; children: React.ReactNode }) {
  const { styles, Icon } = {
    info: { styles: 'border-rule-strong bg-sheet text-ink', Icon: Info },
    error: { styles: 'border-conflict/50 bg-conflict-wash text-conflict', Icon: CircleAlert },
    success: { styles: 'border-officer/50 bg-officer-wash text-officer', Icon: CircleCheck },
    warning: { styles: 'border-pending/50 bg-pending-wash text-pending', Icon: Clock },
  }[kind];
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`flex gap-2.5 rounded-sheet border px-4 py-3 text-sm ${styles}`}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 flex-none" strokeWidth={2} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export type Tone = 'neutral' | 'ok' | 'conflict' | 'pending' | 'active';

/** A status in words; colour only reinforces the text, never replaces it. */
export function Tag({ tone = 'neutral', children }: { tone?: Tone; children: React.ReactNode }) {
  const styles = {
    neutral: 'border-rule-strong text-ink-2',
    ok: 'border-officer text-officer',
    conflict: 'border-conflict text-conflict',
    pending: 'border-pending text-pending bg-pending-wash',
    active: 'border-ink text-ink bg-ink-wash',
  }[tone];
  return <span className={`inline-flex items-center whitespace-nowrap rounded-[2px] border px-1.5 py-px text-xs font-semibold ${styles}`}>{children}</span>;
}

/** A value read from a document, highlighted as cited evidence. */
export function Mark({ children, onClick, title }: { children: React.ReactNode; onClick?: () => void; title?: string }) {
  if (onClick) {
    return (
      <button type="button" onClick={onClick} title={title} className="mark mark-link text-left font-semibold">
        {children}
      </button>
    );
  }
  return <span className="mark font-semibold" title={title}>{children}</span>;
}

/** Shown after this long, so a slow first load says why */
const SLOW_MS = 3000;

function useSlow(): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_MS);
    return () => clearTimeout(t);
  }, []);
  return slow;
}

function SlowNote() {
  return (
    <p className="mt-2 text-xs text-ink-2">
      Still working. If nobody has used the site for a while, the server takes up to a minute to wake up.
    </p>
  );
}

/** Waiting for data: a highlighter sweeping along a ruled line, as if a value were being read. The words
 *  carry the meaning; with reduced motion asked for, the mark stands still. */
export function Loading({ what = 'Loading' }: { what?: string }) {
  const slow = useSlow();
  return (
    <div className="py-6" role="status" aria-live="polite">
      <p className="flex items-center gap-3 text-sm text-ink-2">
        <span className="reading-line" aria-hidden="true" />
        <span>{what}…</span>
      </p>
      {slow && <SlowNote />}
    </div>
  );
}

/** A ruled placeholder in the shape of what is coming, so the page does not jump when it arrives. */
export function Placeholder({ className = '' }: { className?: string }) {
  return <span aria-hidden="true" className={`placeholder block rounded-[2px] ${className}`} />;
}

/** Placeholders laid out like a page section, with the words for screen readers. */
export function Skeleton({ what, children }: { what: string; children: React.ReactNode }) {
  const slow = useSlow();
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{what}…</span>
      {children}
      {slow && <SlowNote />}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-sheet border border-dashed border-rule-strong px-5 py-8 text-center text-sm text-ink-2">{children}</div>;
}

/** The file number, set the way it appears on a file cover. */
export function FileNumber({ code }: { code: string }) {
  return <span className="font-serif font-bold tabular-nums tracking-wide">{code}</span>;
}

export interface Me {
  user_id: string;
  email: string;
  role: Role;
  institution_id: string | null;
  full_name: string | null;
  mfa_required: boolean;
}

export const HOME: Record<Role, string> = {
  institution: '/institution',
  reviewer: '/review',
  rule_admin: '/admin/rules',
};

export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetchApi<Me>('/me').then(({ data, error }) => {
      if (data) setMe(data);
      else setError(error || 'Not signed in');
    });
  }, []);
  return { me, error };
}

// Dates are shown as dd/mm/yyyy everywhere; a date-only value ("2026-11-03") is read as a local day
function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  return new Date(value.length === 10 ? `${value}T00:00:00` : value);
}

function ddmmyyyy(d: Date) {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export function formatTime(value?: string | Date | null) {
  if (!value) return '—';
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

export function formatDate(value?: string | Date | null) {
  if (!value) return '—';
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? String(value) : ddmmyyyy(d);
}

export function formatDateTime(value?: string | Date | null) {
  if (!value) return '—';
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? String(value) : `${ddmmyyyy(d)}, ${formatTime(d)}`;
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** A date with the month in words ("3 August 2025"), for when dd/mm/yyyy is itself the ambiguity. */
export function formatDateInWords(iso?: string | null) {
  const m = iso?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : (iso ?? '—');
}

export function formatBytes(n?: number | null) {
  if (!n) return '—';
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}
