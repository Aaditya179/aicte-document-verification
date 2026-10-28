'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { fetchApi } from '@/lib/api';
import type { AppNotification, Role } from '@/lib/types';
import { formatDateTime } from './ui';

const POLL_MS = 60_000;   // notifications are polled, not pushed (ASSUMPTIONS.md D4)

function hrefFor(n: AppNotification, role: Role) {
  if (n.ref_type === 'rule' && n.ref_id) return `/admin/rules/${n.ref_id}`;
  if (n.ref_type !== 'application' || !n.ref_id) return null;
  return role === 'institution' ? `/institution/applications/${n.ref_id}` : `/review/${n.ref_id}`;
}

export default function Notifications({ role }: { role: Role }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    fetchApi<{ items: AppNotification[]; unread: number }>('/notifications').then(({ data }) => {
      if (data) { setItems(data.items); setUnread(data.unread); }
    });
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !panel.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);

  const readAll = async () => {
    await fetchApi('/notifications/read-all', { method: 'POST' });
    load();
  };

  return (
    <div className="relative" ref={panel}>
      <button onClick={() => { setOpen(!open); if (!open) load(); }} aria-expanded={open} aria-haspopup="true"
        className="inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-sm font-semibold text-ink hover:bg-ink-wash">
        <Bell aria-hidden size={16} />
        <span>Notifications</span>
        {unread > 0 && <span className="rounded-[2px] bg-conflict px-1.5 text-xs font-bold text-sheet">{unread}<span className="sr-only"> unread</span></span>}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-sheet border border-rule-strong bg-sheet shadow-[0_6px_18px_-8px_var(--color-ink)]">
          <div className="flex items-center justify-between border-b border-rule px-4 py-2">
            <p className="text-sm font-semibold">{unread > 0 ? `${unread} unread` : 'All read'}</p>
            {unread > 0 && <button onClick={readAll} className="text-sm underline decoration-rule-strong underline-offset-4 hover:decoration-ink">Mark all as read</button>}
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-ink-2">Nothing yet. Requests and answers about your applications appear here.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {items.map((n) => {
                const href = hrefFor(n, role);
                const body = (
                  <>
                    <span className={n.read_at ? 'text-ink-2' : 'font-semibold'}>{n.message}</span>
                    <span className="mt-0.5 block text-xs text-ink-2">{formatDateTime(n.created_at)}{!n.read_at && ', unread'}</span>
                  </>
                );
                return (
                  <li key={n.id} className="border-b border-rule last:border-b-0">
                    {href ? <Link href={href} onClick={() => setOpen(false)} className="block px-4 py-2.5 text-sm hover:bg-ink-wash">{body}</Link>
                      : <p className="px-4 py-2.5 text-sm">{body}</p>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
