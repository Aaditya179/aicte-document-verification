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
      <p className={`text-sm text-officer ${className}`} role="status">
        The server is awake, so pages will load normally.
      </p>
    );
  }

  return (
    <div className={`rounded-sheet border-l-4 border border-pending bg-pending-wash px-4 py-3 text-sm text-pending ${className}`} role="status" aria-live="polite">
      <p className="font-semibold">
        {state === 'down'
          ? 'The server is taking longer than usual. Refresh in a minute.'
          : state === 'waking' ? 'Waking up the server. This can take up to a minute…' : 'Checking the server…'}
      </p>
      <p className="mt-1">
        The first load may be slow: this demo runs on a free hosting plan that puts the server to sleep after
        15 minutes without visitors, and the first request starts it again. After that, pages load normally.
      </p>
    </div>
  );
}
