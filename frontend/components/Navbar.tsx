'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LogOut, Menu, X } from 'lucide-react';
import { supabase } from '@/lib/supabase';
import { fetchApi } from '@/lib/api';
import type { Me } from '@/components/ui';
import Brand from './Brand';

type NavLink = { href: string; label: string };

const L = {
  cases: { href: '/dashboard', label: 'Case files' },
  patterns: { href: '/patterns', label: 'Patterns' },
} satisfies Record<string, NavLink>;

// Each role sees only the pages it can use. The administrator has no case pages.
const NAV_LINKS: Record<Me['role'], NavLink[]> = {
  institution: [L.cases],
  verifier: [L.cases, L.patterns],
  analyst: [L.patterns, L.cases],
  auditor: [L.cases, L.patterns],
  admin: [],
};

const HIDDEN_ON = ['/login', '/welcome', '/mfa'];

export default function Navbar() {
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    // The role comes from ProofPath's own members table, through the API. The account's
    // app_metadata holds the Nirikshan role, since both apps share one Supabase project.
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) return setMe(null);
      fetchApi<Me>('/me').then(({ data }) => setMe(data));
    });
    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    window.location.replace('/login');
  };

  if (HIDDEN_ON.includes(pathname)) return null;

  const links = me ? NAV_LINKS[me.role] : [];
  const active = links
    .filter((l) => pathname === l.href || pathname?.startsWith(`${l.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <header className="sticky top-0 z-40 w-full bg-transparent border-none pt-3 sm:pt-4 pb-2 px-4 sm:px-6 lg:px-8 pointer-events-none">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        <div className="pointer-events-auto flex items-center">
          <Brand href={links[0]?.href || '/dashboard'} />
        </div>

        {links.length > 0 && (
          <nav aria-label="Main" className="pointer-events-auto hidden lg:flex items-center gap-1 bg-white/95 backdrop-blur-md border border-[#E8E2D8] px-2.5 py-1.5 rounded-full shadow-xs">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active === l.href ? 'page' : undefined}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
                  active === l.href
                    ? 'bg-[#FBF0E4] text-[#C25E26] border border-[#F0D5BE] shadow-2xs'
                    : 'text-stone-600 hover:text-[#1C1917] hover:bg-stone-100/70'
                }`}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="pointer-events-auto flex items-center gap-2">
          {me && (
            <div className="hidden sm:flex items-center gap-2 bg-white/95 backdrop-blur-md border border-[#E8E2D8] px-3.5 py-1.5 rounded-full shadow-xs">
              <div className="w-6 h-6 rounded-full bg-[#FBF0E4] text-[#C25E26] flex items-center justify-center font-bold text-xs uppercase">
                {(me.full_name || me.email)[0]}
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-stone-800 leading-none">{me.full_name || me.email}</p>
                <span className="text-[10px] text-stone-500 capitalize">{me.role}</span>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="p-2 rounded-full bg-white/95 backdrop-blur-md border border-[#E8E2D8] shadow-xs text-stone-500 hover:text-[#C25E26] hover:bg-[#FBF0E4] transition cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
          {links.length > 0 && (
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-full bg-white/95 backdrop-blur-md border border-[#E8E2D8] shadow-xs text-stone-700 hover:text-[#C25E26] transition cursor-pointer"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="pointer-events-auto lg:hidden mt-2 max-w-7xl mx-auto p-4 rounded-3xl bg-white/95 backdrop-blur-md border border-[#E8E2D8] shadow-xl flex flex-col gap-1.5">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setMobileMenuOpen(false)}
              aria-current={active === l.href ? 'page' : undefined}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-stone-700 hover:bg-[#FBF0E4] hover:text-[#C25E26] transition"
            >
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
