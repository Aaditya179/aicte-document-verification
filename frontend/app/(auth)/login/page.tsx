'use client';

import React, { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { API_BASE_URL, fetchApi } from '@/lib/api';
import ServerWakeNote from '@/components/ServerWakeNote';
import Brand from '@/components/Brand';
import type { Me } from '@/components/ui';
import { Building2, FileCheck2, Network, Eye, Settings, ArrowRight, Loader2, Lock, Mail, AlertCircle, EyeOff } from 'lucide-react';

interface DemoRole {
  role: Me['role'];
  label: string;
  email: string;
  description: string;
  icon: React.ElementType;
}

const DEMO_PASSWORD = 'password123';

const DEMO_ROLES: DemoRole[] = [
  { role: 'verifier', label: 'Verifier', email: 'verifier@proofpath.demo', icon: FileCheck2,
    description: 'Opens a case file, sees what is verified, what conflicts and what is unverified, and confirms or overrules each finding.' },
  { role: 'analyst', label: 'Analyst', email: 'analyst@proofpath.demo', icon: Network,
    description: 'Reviews patterns across institutions: the same land parcel, faculty member or document turning up in more than one application.' },
  { role: 'institution', label: 'Institution', email: 'institution@proofpath.demo', icon: Building2,
    description: 'Sees its own case files and what still needs a document or a correction.' },
  { role: 'auditor', label: 'Auditor', email: 'auditor@proofpath.demo', icon: Eye,
    description: 'Read-only access to case files, patterns and the audit trail.' },
  { role: 'admin', label: 'Administrator', email: 'admin@proofpath.demo', icon: Settings,
    description: 'Manages accounts. No access to case files.' },
];

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [signingRole, setSigningRole] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSignIn = async (targetEmail = email, targetPassword = password, roleKey?: string) => {
    setLoading(true);
    setErrorMessage(null);
    if (roleKey) setSigningRole(roleKey);
    try {
      // Sign in through the API so failed attempts are rate limited and lock the account
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: targetEmail, password: targetPassword }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Invalid email or password');

      const { error } = await supabase.auth.setSession({ access_token: body.access_token, refresh_token: body.refresh_token });
      if (error) throw new Error(error.message);

      // The account may exist in the shared project without ProofPath access (for example a Nirikshan account)
      const me = await fetchApi<Me & { mfa_required: boolean }>('/me');
      if (!me.data) {
        await supabase.auth.signOut();
        throw new Error(me.error || 'This account has no ProofPath access');
      }
      const requested = new URLSearchParams(window.location.search).get('next') || '';
      const home = me.data.role === 'analyst' ? '/patterns' : '/dashboard';
      const next = requested.startsWith('/') && !requested.startsWith('//') ? requested : home;
      window.location.assign(me.data.mfa_required ? `/mfa?next=${encodeURIComponent(next)}` : next);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setLoading(false);
      setSigningRole(null);
    }
  };

  const signInAs = (role: DemoRole) => {
    setEmail(role.email);
    setPassword(DEMO_PASSWORD);
    handleSignIn(role.email, DEMO_PASSWORD, role.role);
  };

  // /login?demo=<role> signs straight in, for links from the welcome page
  useEffect(() => {
    const found = DEMO_ROLES.find((r) => r.role === new URLSearchParams(window.location.search).get('demo'));
    if (!found) return;
    const t = setTimeout(() => signInAs(found), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-[#FAF7F2] bg-grid-texture text-[#1C1917] flex flex-col justify-between p-4 sm:p-6 lg:p-8 font-sans">
      <header className="max-w-6xl mx-auto w-full pt-4 pb-6 flex items-center justify-between">
        <Brand />
        <div className="flex items-center gap-2 text-xs font-semibold px-4 py-1.5 rounded-full bg-white/95 border border-[#E8E2D8] text-[#C25E26] shadow-xs">
          <span className="w-2 h-2 rounded-full bg-[#C25E26] animate-pulse"></span>
          SIH26261 prototype
        </div>
      </header>

      <main className="max-w-6xl mx-auto w-full my-auto py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-5 bg-white rounded-2xl p-6 sm:p-8 shadow-xs border border-[#E8E2D8]">
            <h2 className="text-2xl font-bold font-serif text-[#1C1917]">Sign in</h2>
            <p className="text-sm text-stone-500 mt-1">Use your account, or pick a demo role.</p>
            <ServerWakeNote className="mt-3" />

            {errorMessage && (
              <div role="alert" className="mt-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-700 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={(e) => { e.preventDefault(); handleSignIn(); }} className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="block text-xs font-semibold text-stone-700 mb-1.5">Email address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-stone-400 absolute left-3.5 top-3.5" aria-hidden="true" />
                  <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@proofpath.demo" required
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#E8E2D8] bg-[#FAF7F2] text-sm focus:outline-none focus:ring-2 focus:ring-[#C25E26]" />
                </div>
              </div>
              <div>
                <label htmlFor="password" className="block text-xs font-semibold text-stone-700 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-stone-400 absolute left-3.5 top-3.5" aria-hidden="true" />
                  <input id="password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-[#E8E2D8] bg-[#FAF7F2] text-sm focus:outline-none focus:ring-2 focus:ring-[#C25E26]" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3.5 top-3.5 text-stone-400 hover:text-stone-600 cursor-pointer">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <button type="submit" disabled={loading}
                className="w-full mt-2 py-3 px-4 rounded-full bg-[#C25E26] hover:bg-[#A84A19] text-white font-bold text-sm transition shadow-md shadow-[#C25E26]/20 flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer">
                {loading && !signingRole ? <><Loader2 className="w-4 h-4 animate-spin" /> Signing in…</> : <>Sign in <ArrowRight className="w-4 h-4" /></>}
              </button>
            </form>
            <p className="mt-6 pt-5 border-t border-[#E8E2D8] text-center text-xs text-stone-500">
              Every demo account uses the password <code className="font-mono font-bold text-[#C25E26]">{DEMO_PASSWORD}</code>
            </p>
          </div>

          <div className="lg:col-span-7">
            <h3 className="text-lg font-bold font-serif text-[#1C1917]">Demo accounts</h3>
            <p className="text-xs text-stone-500 mb-4">Click a role to sign in as that person.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {DEMO_ROLES.map((r) => {
                const Icon = r.icon;
                return (
                  <button key={r.role} type="button" onClick={() => signInAs(r)} disabled={loading}
                    className="p-4 text-left rounded-2xl bg-white border border-[#E8E2D8] hover:border-[#C25E26] hover:shadow-xs transition group relative overflow-hidden cursor-pointer">
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 rounded-full bg-[#FAF7F2] border border-[#EAE4D9] text-[#C25E26] group-hover:bg-[#C25E26] group-hover:text-white transition-colors">
                        <Icon className="w-5 h-5" aria-hidden="true" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-bold text-[#1C1917] font-serif">{r.label}</h4>
                        <p className="text-xs text-stone-500 mt-1 leading-relaxed">{r.description}</p>
                        <p className="mt-2 text-[11px] font-mono text-stone-400 truncate">{r.email}</p>
                      </div>
                    </div>
                    {signingRole === r.role && (
                      <div className="absolute inset-0 bg-[#C25E26]/95 flex items-center justify-center text-white font-medium text-xs gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" /> Signing in as {r.label}…
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </main>

      <footer className="max-w-6xl mx-auto w-full pt-6 pb-2 border-t border-[#E8E2D8] text-center text-xs text-stone-500">
        Advisory only: final decisions rest with the competent authority.
      </footer>
    </div>
  );
}
