'use client';

import React, { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { API_BASE_URL, fetchApi } from '@/lib/api';
import Brand from '@/components/Brand';
import DemoAccounts from '@/components/DemoAccounts';
import ServerWakeNote from '@/components/ServerWakeNote';
import { HOME, Notice, btnPrimary, input, label, type Me } from '@/components/ui';
import type { DemoAccount } from '@/lib/types';

const DEMO_PASSWORD = 'password123';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyEmail, setBusyEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const signIn = async (targetEmail: string, targetPassword: string) => {
    setBusy(true);
    setError(null);
    try {
      // Sign in through the API so failed attempts are rate limited and lock the account
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: targetEmail, password: targetPassword }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The email or password is wrong');

      const { error } = await supabase.auth.setSession({ access_token: body.access_token, refresh_token: body.refresh_token });
      if (error) throw new Error(error.message);

      // The account may exist in the shared project without ProofPath access (for example a Nirikshan account)
      const me = await fetchApi<Me>('/me');
      if (!me.data) {
        await supabase.auth.signOut();
        throw new Error(me.error || 'This account has no ProofPath access');
      }
      const requested = new URLSearchParams(window.location.search).get('next') || '';
      const next = requested.startsWith('/') && !requested.startsWith('//') ? requested : HOME[me.data.role];
      window.location.assign(me.data.mfa_required ? `/mfa?next=${encodeURIComponent(next)}` : next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
      setBusy(false);
      setBusyEmail(null);
    }
  };

  const pick = (a: DemoAccount) => {
    setBusyEmail(a.email);
    signIn(a.email, DEMO_PASSWORD);
  };

  // /login?demo=<email> signs straight in, for the welcome page's links
  useEffect(() => {
    const demo = new URLSearchParams(window.location.search).get('demo');
    if (!demo || !demo.endsWith('@proofpath.demo')) return;
    const t = setTimeout(() => { setBusyEmail(demo); signIn(demo, DEMO_PASSWORD); }, 0);
    return () => clearTimeout(t);
  }, []);

  return (
    <div>
      <header className="ledger-rule">
        <div className="mx-auto flex max-w-6xl items-center px-4 py-3 sm:px-6"><Brand /></div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[22rem_1fr]">
        <section>
          <h1 className="font-serif text-3xl font-bold">Sign in</h1>
          <p className="mt-2 text-ink-2">With your ProofPath account, or pick a demo account.</p>
          <ServerWakeNote className="mt-4" />
          {error && <div className="mt-4"><Notice kind="error">{error}</Notice></div>}

          <form onSubmit={(e) => { e.preventDefault(); signIn(email, password); }} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className={label}>Email address</label>
              <input id="email" type="email" autoComplete="username" className={input} value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="name@proofpath.demo" required />
            </div>
            <div>
              <label htmlFor="password" className={label}>Password</label>
              <input id="password" type="password" autoComplete="current-password" className={input} value={password}
                onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className={`${btnPrimary} w-full`} disabled={busy}>
              {busy && !busyEmail ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </section>

        <section>
          <h2 className="font-serif text-2xl font-bold">Demo accounts</h2>
          <p className="mt-2 text-ink-2">All fictional. Each uses the password {DEMO_PASSWORD}.</p>
          <div className="mt-6"><DemoAccounts onPick={pick} busyEmail={busyEmail} /></div>
        </section>
      </div>
    </div>
  );
}
