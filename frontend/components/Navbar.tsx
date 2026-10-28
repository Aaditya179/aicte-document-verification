'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { fetchApi } from '@/lib/api';
import { HOME, type Me } from '@/components/ui';
import { ROLE_LABEL, type Role } from '@/lib/types';
import Brand from './Brand';
import Notifications from './Notifications';

type NavLink = { href: string; label: string };

// Each role sees only the pages it can use
const NAV_LINKS: Record<Role, NavLink[]> = {
  institution: [{ href: '/institution', label: 'Your applications' }],
  reviewer: [{ href: '/review', label: 'Review queue' }, { href: '/review/cross', label: 'Across institutions' }],
  rule_admin: [{ href: '/admin/rules', label: 'Rules' }],
};

const HIDDEN_ON = ['/login', '/welcome', '/mfa'];

export default function Navbar() {
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    // The role comes from ProofPath's own members table, through the API. The account's
    // app_metadata holds the Nirikshan role, since both apps share one Supabase project.
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) return setMe(null);
      fetchApi<Me>('/me').then(({ data }) => setMe(data));
    });
    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
    window.location.replace('/login');
  };

  if (HIDDEN_ON.includes(pathname)) return null;

  const links = me ? NAV_LINKS[me.role] : [];

  return (
    <header className="ledger-rule bg-paper print:hidden">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
        <Brand href={me ? HOME[me.role] : '/welcome'} />
        <nav aria-label="Main" className="flex flex-1 items-center gap-5">
          {links.map((l) => {
            // The longest matching link is the active one, so /review/cross does not also light up /review
            const matches = (h: string) => pathname === h || pathname.startsWith(`${h}/`);
            const active = matches(l.href) && !links.some((o) => o.href.length > l.href.length && matches(o.href));
            return (
              <Link key={l.href} href={l.href} aria-current={active ? 'page' : undefined}
                className={`text-sm font-semibold underline-offset-[6px] ${active ? 'text-ink underline decoration-2' : 'text-ink-2 hover:text-ink hover:underline'}`}>
                {l.label}
              </Link>
            );
          })}
        </nav>
        {me && (
          <div className="flex items-center gap-4 text-sm">
            <Notifications role={me.role} />
            <span className="text-ink-2">
              <span className="font-semibold text-ink">{me.full_name || me.email}</span>
              <span className="hidden sm:inline">, {ROLE_LABEL[me.role].toLowerCase()}</span>
            </span>
            <button onClick={signOut} className="font-semibold text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
