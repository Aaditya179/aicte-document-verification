'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { card, btnPrimary, btnSecondary, input, label, Notice } from '@/components/ui';

type Step = 'loading' | 'enroll' | 'verify' | 'done';

/**
 * Second sign-in step for verifiers and analysts: enrol an authenticator app once, then enter its
 * six-digit code each time. A verified code raises the session to aal2, which their routes require.
 */
function MfaContent() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/dashboard';
  const [step, setStep] = useState<Step>('loading');
  const [factorId, setFactorId] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const { data: session } = await supabase.auth.getSession();
      if (!session.session) return router.replace('/login');
      const { data: aal } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
      if (aal?.currentLevel === 'aal2') return router.replace(next);
      const { data, error } = await supabase.auth.mfa.listFactors();
      if (error) return setError(error.message);
      const verified = data.totp.find((f) => f.status === 'verified');
      if (verified) {
        setFactorId(verified.id);
        return setStep('verify');
      }
      // Clear any half-finished enrolment before starting a new one
      for (const f of data.all.filter((f) => f.status === 'unverified')) {
        await supabase.auth.mfa.unenroll({ factorId: f.id });
      }
      const enrolled = await supabase.auth.mfa.enroll({ factorType: 'totp', friendlyName: `ProofPath ${Date.now()}` });
      if (enrolled.error) return setError(enrolled.error.message);
      setFactorId(enrolled.data.id);
      setQr(enrolled.data.totp.qr_code);
      setSecret(enrolled.data.totp.secret);
      setStep('enroll');
    })();
  }, [router, next]);

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (!factorId) return;
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId, code: code.trim() });
    setBusy(false);
    if (error) return setError('That code did not work. Check the time on your phone and try the newest code.');
    setStep('done');
    router.replace(next);
  }

  async function signOut() {
    await supabase.auth.signOut();
    window.location.replace('/login');
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <div className={card}>
        <h1 className="text-xl font-bold text-stone-900">Verify it’s you</h1>
        <p className="mt-1 text-sm text-stone-600">Verifier and analyst accounts use a second step: a six-digit code from an authenticator app.</p>

        {step === 'loading' && !error && <p className="mt-6 text-sm text-stone-500">Checking your account…</p>}

        {step === 'enroll' && (
          <div className="mt-6 space-y-4">
            <p className="text-sm text-stone-800">1. Scan this code with Google Authenticator, Microsoft Authenticator or a similar app.</p>
            {qr && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={qr} alt="QR code to add ProofPath to your authenticator app" className="mx-auto h-48 w-48 rounded-lg border border-[#E8E2D8] bg-white p-2" />
            )}
            {secret && (
              <p className="text-xs text-stone-600">Can’t scan? Enter this key: <code className="break-all font-mono text-stone-900">{secret}</code></p>
            )}
            <p className="text-sm text-stone-800">2. Enter the six-digit code the app shows.</p>
          </div>
        )}

        {(step === 'enroll' || step === 'verify') && (
          <form onSubmit={verify} className="mt-4 space-y-4">
            <div>
              <label htmlFor="totp" className={label}>Six-digit code</label>
              <input id="totp" className={`${input} text-center font-mono text-lg tracking-[0.4em]`} inputMode="numeric" autoComplete="one-time-code"
                pattern="\d{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} autoFocus required />
            </div>
            <button type="submit" className={`${btnPrimary} w-full`} disabled={busy || code.length !== 6}>{busy ? 'Checking…' : 'Verify and continue'}</button>
          </form>
        )}

        {step === 'done' && <div className="mt-6"><Notice kind="success">Verified. Taking you back…</Notice></div>}
        {error && <div className="mt-4"><Notice kind="error">{error}</Notice></div>}
        <button className={`${btnSecondary} mt-6 w-full`} onClick={signOut}>Sign in as someone else</button>
      </div>
    </div>
  );
}

export default function MfaPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-stone-500">Loading…</div>}>
      <MfaContent />
    </Suspense>
  );
}
