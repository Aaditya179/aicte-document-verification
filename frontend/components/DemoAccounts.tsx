'use client';

import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { ROLE_LABEL, type DemoAccount } from '@/lib/types';
import { Loading, Notice } from './ui';

/** The demo accounts, from the API, each with a one-click sign-in. */
export default function DemoAccounts({ onPick, busyEmail }: { onPick?: (a: DemoAccount) => void; busyEmail?: string | null }) {
  const [accounts, setAccounts] = useState<DemoAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/demo/accounts`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`The server answered ${r.status}`))))
      .then(setAccounts)
      .catch(() => setError('The demo accounts could not be loaded. The server may still be starting; refresh in a minute.'));
  }, []);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!accounts) return <Loading what="Loading demo accounts" />;

  return (
    <ul className="divide-y divide-rule border-y border-rule">
      {accounts.map((a) => (
        <li key={a.email} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-4">
          <div className="min-w-0 flex-1 basis-72">
            <p className="font-semibold">
              {a.institution ? ROLE_LABEL[a.role] : a.full_name}
              {a.institution && <span className="font-normal text-ink-2">, {a.institution}</span>}
            </p>
            <p className="mt-0.5 text-sm text-ink-2">{a.description}</p>
          </div>
          {onPick ? (
            <button type="button" onClick={() => onPick(a)} disabled={!!busyEmail}
              className="rounded-control border border-ink px-3 py-1.5 text-sm font-semibold hover:bg-ink hover:text-sheet disabled:opacity-50">
              {busyEmail === a.email ? 'Signing in…' : `Sign in as ${ROLE_LABEL[a.role].toLowerCase()}`}
            </button>
          ) : (
            <a href={`/login?demo=${encodeURIComponent(a.email)}`}
              className="rounded-control border border-ink px-3 py-1.5 text-sm font-semibold hover:bg-ink hover:text-sheet">
              Sign in as {ROLE_LABEL[a.role].toLowerCase()}
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}
