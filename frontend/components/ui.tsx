'use client';

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';

// Shared look, following the palette in globals.css (the same as Nirikshan)
export const card = 'bg-white border border-[#E8E2D8] rounded-xl p-5';
export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-[#C25E26] px-4 py-2 text-sm font-semibold text-white hover:bg-[#A84A19] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C25E26]';
export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-[#E8E2D8] bg-white px-4 py-2 text-sm font-medium text-stone-800 hover:bg-[#FBF0E4] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C25E26]';
export const btnDanger =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600';
export const input =
  'w-full rounded-lg border border-[#E8E2D8] bg-white px-3 py-2 text-sm text-stone-900 focus:border-[#C25E26] focus:outline-none focus:ring-2 focus:ring-[#FBF0E4]';
export const label = 'block text-xs font-semibold text-stone-600 mb-1';

export function PageShell({ title, subtitle, actions, children }: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-stone-900">{title}</h1>
          {subtitle && <p className="mt-1 max-w-3xl text-sm text-stone-600">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'error' | 'success' | 'warning'; children: React.ReactNode }) {
  const styles = {
    info: 'border-[#E8E2D8] bg-[#FBF0E4] text-stone-800',
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
  }[kind];
  return <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>{children}</div>;
}

export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'red' | 'amber' | 'green' | 'blue'; children: React.ReactNode }) {
  const styles = {
    neutral: 'bg-stone-100 text-stone-700',
    red: 'bg-red-100 text-red-800',
    amber: 'bg-amber-100 text-amber-900',
    green: 'bg-emerald-100 text-emerald-800',
    blue: 'bg-sky-100 text-sky-800',
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${styles}`}>{children}</span>;
}

export interface Me {
  user_id: string;
  email: string;
  role: 'institution' | 'verifier' | 'analyst' | 'auditor' | 'admin';
  institution_id: string | null;
  full_name: string | null;
  mfa_required: boolean;
}

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

export function formatDate(value?: string | Date | null, opts: { weekday?: boolean } = {}) {
  if (!value) return '—';
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return opts.weekday ? `${d.toLocaleDateString('en-IN', { weekday: 'short' })}, ${ddmmyyyy(d)}` : ddmmyyyy(d);
}

export function formatDateTime(value?: string | Date | null) {
  if (!value) return '—';
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? String(value) : `${ddmmyyyy(d)}, ${formatTime(d)}`;
}
