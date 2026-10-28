'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
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
      <p className={`flex items-center gap-1.5 text-xs text-emerald-700 ${className}`} role="status">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Server is awake, pages will load normally.
      </p>
    );
  }

  return (
    <div className={`rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 ${className}`} role="status" aria-live="polite">
      <p className="flex items-center gap-1.5 font-semibold">
        {state === 'down'
          ? <><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> The server is taking longer than usual. Please refresh in a minute.</>
          : <><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> {state === 'waking' ? 'Waking up the server, this can take up to a minute…' : 'Checking the server…'}</>}
      </p>
      <p className="mt-1 text-amber-800">
        The first load may be slow: this demo runs on a free hosting plan that puts the server to sleep after
        15 minutes without visitors, and the first request starts it again. After that, pages load normally.
      </p>
    </div>
  );
}
