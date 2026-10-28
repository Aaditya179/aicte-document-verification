'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';
import type { AuditEvent } from '@/lib/types';
import {
  Empty,
  Loading,
  Notice,
  PageShell,
  Tag,
  btnPrimary,
  btnSecondary,
  formatDate,
  formatDateTime,
  input,
  label,
  td,
  th,
} from '@/components/ui';

const EVENT_LABELS: Record<string, string> = {
  application_seeded: 'Application seeded',
  application_submitted: 'Application submitted',
  document_uploaded: 'Document uploaded',
  document_processed: 'Document processed',
  document_processing_failed: 'Document reading failed',
  validation_run: 'Validation run',
  finding_resolved: 'Finding resolved',
  finding_dismissed: 'Finding dismissed',
  evidence_requested: 'Evidence requested',
  evidence_request_fulfilled: 'Request answered',
  case_file_snapshot: 'Case File snapshot saved',
  rooms_saved: 'Room table saved',
  field_confirmed: 'Value confirmed',
  field_corrected: 'Value corrected',
  rule_created: 'Rule draft created',
  rule_submitted: 'Rule submitted for approval',
  rule_approved: 'Rule approved',
  rule_activated: 'Rule activated',
  rule_retired: 'Rule retired',
  rule_drafted_from_text: 'Rule drafted from text',
  settings_updated: 'Settings updated',
  verification_recorded: 'Verification check recorded',
};

function eventNote(e: AuditEvent): string {
  const d = e.detail ?? {};
  if (e.event_type === 'validation_run') {
    const by =
      d.trigger === 'document_replaced'
        ? 'After replacement document was read. '
        : d.trigger === 'value_confirmed'
          ? 'After value confirmation. '
          : '';
    return `${by}${d.findings ?? 0} findings (${d.created ?? 0} new, ${d.still_open ?? 0} open, ${d.auto_closed ?? 0} closed). Rule run as of ${formatDate(String(d.as_of_date ?? ''))}.`;
  }
  if (e.event_type === 'evidence_request_fulfilled' && typeof d.note === 'string') return d.note;
  if (e.event_type === 'rooms_saved') return `${d.rooms ?? 0} rooms, ${d.total_sqm ?? 0} sq m`;
  if (e.event_type === 'field_corrected')
    return `${String(d.from ?? 'not read')} → ${String(d.to)}: ${String(d.reason ?? '')}`;
  if (e.event_type === 'settings_updated')
    return `${String(d.key ?? '')}: ${String(d.reason ?? 'Configuration updated')}`;
  if (typeof d.reason === 'string') return d.reason;
  if (typeof d.message === 'string') return d.message;
  if (typeof d.original_name === 'string') return d.original_name;
  if (typeof d.code === 'string') return `Code ${d.code}`;
  return '';
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chain, setChain] = useState<{ ok: boolean; events_checked: number; broken_at_id: number | null } | null>(
    null
  );
  const [checking, setChecking] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const load = () => {
    fetchApi<AuditEvent[]>('/audit?limit=300').then(({ data, error }) => {
      setEvents(data);
      setError(error);
    });
  };

  useEffect(() => {
    load();
  }, []);

  const verifyChain = async () => {
    setChecking(true);
    const { data, error } = await fetchApi<{ ok: boolean; events_checked: number; broken_at_id: number | null }>(
      '/audit/verify'
    );
    setChecking(false);
    if (error) setError(error);
    else setChain(data);
  };

  const eventTypes = useMemo(() => {
    if (!events) return [];
    const set = new Set<string>();
    events.forEach((e) => set.add(e.event_type));
    return Array.from(set).sort();
  }, [events]);

  const filtered = useMemo(() => {
    if (!events) return [];
    return events.filter((e) => {
      if (typeFilter && e.event_type !== typeFilter) return false;
      if (!search.trim()) return true;
      const term = search.toLowerCase();
      const note = eventNote(e).toLowerCase();
      const actor = (e.actor_name || e.actor_role || '').toLowerCase();
      const entity = (e.entity_type || '').toLowerCase();
      const type = (EVENT_LABELS[e.event_type] || e.event_type).toLowerCase();
      return note.includes(term) || actor.includes(term) || entity.includes(term) || type.includes(term);
    });
  }, [events, search, typeFilter]);

  return (
    <PageShell
      title="Audit log"
      description="An append-only log of every run, action, rule change and setting, hash-chained from genesis so tampering is detected."
    >
      <div className="space-y-6">
        {/* Verification banner card */}
        <section
          aria-labelledby="chain-heading"
          className="rounded-sm border border-rule bg-sheet p-4 flex flex-wrap items-center justify-between gap-4"
        >
          <div>
            <h2 id="chain-heading" className="font-serif text-base font-bold text-ink">
              Cryptographic hash chain
            </h2>
            <p className="text-sm text-ink-2">
              Each event signs the previous event hash with SHA-256. Database triggers block update and delete.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {chain && (
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-sm text-xs font-semibold ${
                  chain.ok ? 'bg-officer/10 text-officer border border-officer/30' : 'bg-conflict/10 text-conflict border border-conflict/30'
                }`}
              >
                {chain.ok
                  ? `✓ Intact (${chain.events_checked} events verified)`
                  : `✗ Tampering detected at event #${chain.broken_at_id}`}
              </span>
            )}
            <button
              type="button"
              className={btnSecondary}
              onClick={verifyChain}
              disabled={checking}
            >
              {checking ? 'Verifying chain…' : 'Check audit chain'}
            </button>
          </div>
        </section>

        {error && <Notice kind="error">{error}</Notice>}

        {/* Filters */}
        <div className="flex flex-wrap items-end gap-4 rounded-sm border border-rule bg-sheet p-4">
          <div className="w-64">
            <label htmlFor="audit-search" className={label}>
              Search log
            </label>
            <input
              id="audit-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search actors, notes, entities…"
              className={input}
            />
          </div>

          <div className="w-56">
            <label htmlFor="type-filter" className={label}>
              Filter by event type
            </label>
            <select
              id="type-filter"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className={input}
            >
              <option value="">All event types ({events?.length ?? 0})</option>
              {eventTypes.map((t) => (
                <option key={t} value={t}>
                  {EVENT_LABELS[t] || t}
                </option>
              ))}
            </select>
          </div>

          {(search || typeFilter) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setTypeFilter('');
              }}
              className="text-xs text-ink-2 hover:text-ink underline self-center mb-1"
            >
              Reset filters
            </button>
          )}

          <div className="ml-auto text-xs text-ink-2 self-center">
            Showing {filtered.length} of {events?.length ?? 0} events
          </div>
        </div>

        {/* Events Table */}
        {!events ? (
          <Loading what="Loading audit events" />
        ) : filtered.length === 0 ? (
          <Empty>No audit events match your search.</Empty>
        ) : (
          <div className="overflow-x-auto rounded-sm border border-rule bg-paper">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-rule bg-sheet font-serif text-xs text-ink-2">
                <tr>
                  <th className={th}>Time</th>
                  <th className={th}>Event</th>
                  <th className={th}>Actor</th>
                  <th className={th}>Entity</th>
                  <th className={th}>Details</th>
                  <th className={`${th} text-right font-mono`}>Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule font-sans">
                {filtered.map((e) => {
                  const labelText = EVENT_LABELS[e.event_type] || e.event_type;
                  const isOfficer = e.actor_role === 'reviewer' || e.actor_role === 'rule_admin';
                  return (
                    <tr key={e.id} className="hover:bg-sheet/50 transition-colors">
                      <td className={`${td} whitespace-nowrap text-xs text-ink-2`}>
                        {formatDateTime(e.created_at)}
                      </td>
                      <td className={td}>
                        <Tag tone={isOfficer ? 'ok' : 'neutral'}>{labelText}</Tag>
                      </td>
                      <td className={td}>
                        <div className="text-xs">
                          <span className="font-semibold text-ink">{e.actor_name || 'System'}</span>
                          {e.actor_role && (
                            <span className="ml-1 text-ink-2">({e.actor_role})</span>
                          )}
                        </div>
                      </td>
                      <td className={`${td} text-xs text-ink-2 whitespace-nowrap`}>
                        {e.entity_type ? (
                          <span>
                            {e.entity_type}
                            {e.application_id && (
                              <Link
                                href={`/review/${e.application_id}`}
                                className="ml-1.5 text-ink underline hover:text-officer"
                              >
                                view case
                              </Link>
                            )}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className={`${td} text-xs text-ink max-w-md`}>
                        {eventNote(e) || '—'}
                      </td>
                      <td className={`${td} text-xs text-right font-mono text-ink-2 whitespace-nowrap`}>
                        <span title={e.event_hash}>{e.event_hash ? e.event_hash.slice(0, 8) + '…' : '—'}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}
