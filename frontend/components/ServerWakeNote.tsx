'use client';

import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/lib/api';

type State = 'checking' | 'waking' | 'ready' | 'down';

const SLOW_MS = 2500; // longer than this, the server is starting up
const GIVE_UP_MS = 120_000;
const RETRY_MS = 5000;

/**
 * The API runs on a free plan that sleeps when nobody uses it. This pings it as soon as the page
 * opens, so it is starting while the visitor reads, and says why the first load may be slow.
 */
export default function ServerWakeNote({ className = '' }: { className?: string }) {
  const [state, setState] = useState<State>('checking');

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    const slow = setTimeout(() => { if (!cancelled) setState((s) => (s === 'checking' ? 'waking' : s)); }, SLOW_MS);

    async function ping() {
      try {
        const res = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store' });
        if (res.ok) {
          if (!cancelled) setState('ready');
          return;
        }
      } catch {
        // still starting: the platform drops or rejects requests until the server is up
      }
      if (cancelled) return;
      if (Date.now() - started > GIVE_UP_MS) setState('down');
      else setTimeout(ping, RETRY_MS);
    }
    ping();
    return () => { cancelled = true; clearTimeout(slow); };
  }, []);

  if (state === 'ready') {
    return (
      <p className={`flex items-center gap-2 text-sm text-officer ${className}`} role="status">
        <svg
          className="h-4 w-4 shrink-0 text-officer"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span>The server is awake, so pages will load normally.</span>
      </p>
    );
  }

  return (
    <div
      className={`rounded-sheet border-l-4 border border-pending bg-pending-wash px-4 py-3 text-sm text-pending ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2 font-semibold">
        {(state === 'checking' || state === 'waking') && (
          <svg
            className="h-4 w-4 shrink-0 animate-spin text-pending"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="3"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        <p>
          {state === 'down'
            ? 'The server is taking longer than usual. Refresh in a minute.'
            : state === 'waking'
            ? 'Waking up the server. This can take up to a minute…'
            : 'Checking the server…'}
        </p>
      </div>
      <p className="mt-1">
        The first load may be slow: this demo runs on a free hosting plan that puts the server to sleep after
        15 minutes without visitors, and the first request starts it again. After that, pages load normally.
      </p>
      {(state === 'checking' || state === 'waking') && (
        <div className="mt-2.5 h-1 w-full overflow-hidden rounded-full bg-sheet">
          <div className="h-full w-2/5 animate-pulse rounded-full bg-pending" />
        </div>
      )}
    </div>
  );
}
