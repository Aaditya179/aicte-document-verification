'use client';

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import type { Room, RoomView } from '@/lib/types';
import { Empty, Loading, Notice, btnPrimary, btnQuiet, btnSecondary, input, td, th } from './ui';

const sqm = (n: number) => `${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })} sq m`;

/** The room table read off the floor plan. Its total is set against the declared built-up area (check C11). */
export function RoomTable({ applicationId, canEdit, onSaved }: { applicationId: string; canEdit: boolean; onSaved?: () => void }) {
  const [view, setView] = useState<RoomView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Room[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    fetchApi<RoomView>(`/applications/${applicationId}/rooms`).then(({ data, error }) => (data ? setView(data) : setError(error)));
  }, [applicationId, version]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    const rooms = draft.filter((r) => r.room_label.trim()).map((r) => ({ room_label: r.room_label.trim(), length_m: Number(r.length_m), width_m: Number(r.width_m) }));
    const { data, error } = await fetchApi<RoomView>(`/applications/${applicationId}/rooms`, { method: 'POST', body: JSON.stringify({ rooms }) });
    setSaving(false);
    if (data) { setView(data); setDraft(null); setVersion((v) => v + 1); onSaved?.(); }
    else setError(error);
  };

  if (!view) return error ? <Notice kind="error">{error}</Notice> : <Loading what="Loading the room table" />;
  const declared = view.declared_total_area_sqm;
  const editing = draft !== null;
  const rows = draft ?? view.rooms;
  const total = editing ? rows.reduce((s, r) => s + (Number(r.length_m) || 0) * (Number(r.width_m) || 0), 0) : view.total_sqm;
  const gap = declared ? ((total - declared) / declared) * 100 : null;

  const update = (i: number, patch: Partial<Room>) => setDraft((d) => d!.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-3">
      {rows.length === 0 && !editing ? (
        <Empty>No room table yet. {canEdit ? 'Enter each room from the floor plan so its areas can be added up.' : 'The areas cannot be added up until it is entered.'}</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] border-collapse">
            <thead>
              <tr>
                <th className={th}>Room</th>
                <th className={`${th} text-right`}>Length (m)</th>
                <th className={`${th} text-right`}>Width (m)</th>
                <th className={`${th} text-right`}>Area</th>
                {editing && <th className={th}><span className="sr-only">Remove</span></th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id ?? `new-${i}`}>
                  {editing ? (
                    <>
                      <td className={td}><input aria-label={`Room ${i + 1} name`} className={input} value={r.room_label} onChange={(e) => update(i, { room_label: e.target.value })} /></td>
                      <td className={td}><input aria-label={`Room ${i + 1} length in metres`} className={`${input} text-right`} inputMode="decimal" value={r.length_m || ''} onChange={(e) => update(i, { length_m: e.target.value as unknown as number })} /></td>
                      <td className={td}><input aria-label={`Room ${i + 1} width in metres`} className={`${input} text-right`} inputMode="decimal" value={r.width_m || ''} onChange={(e) => update(i, { width_m: e.target.value as unknown as number })} /></td>
                      <td className={`${td} text-right tabular-nums`}>{sqm((Number(r.length_m) || 0) * (Number(r.width_m) || 0))}</td>
                      <td className={td}><button className={btnQuiet} onClick={() => setDraft((d) => d!.filter((_, j) => j !== i))}>Remove</button></td>
                    </>
                  ) : (
                    <>
                      <td className={td}>{r.room_label}</td>
                      <td className={`${td} text-right tabular-nums`}>{r.length_m}</td>
                      <td className={`${td} text-right tabular-nums`}>{r.width_m}</td>
                      <td className={`${td} text-right tabular-nums`}>{sqm(Number(r.area_sqm ?? r.length_m * r.width_m))}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="ledger-rule">
                <td className="px-3 py-2 font-semibold" colSpan={3}>Rooms add up to</td>
                <td className="px-3 py-2 text-right font-semibold tabular-nums">{sqm(total)}</td>
                {editing && <td />}
              </tr>
              {declared != null && (
                <tr>
                  <td className="px-3 py-1 text-sm text-ink-2" colSpan={3}>Declared built-up area</td>
                  <td className="px-3 py-1 text-right text-sm tabular-nums text-ink-2">{sqm(Number(declared))}</td>
                  {editing && <td />}
                </tr>
              )}
            </tfoot>
          </table>
        </div>
      )}
      {gap != null && rows.length > 0 && Math.abs(gap) > 1 && (
        <p className="text-sm font-semibold text-conflict">The rooms differ from the declared area by {Math.abs(gap).toFixed(1)}%. The illustrative rule allows 1%.</p>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          {editing ? (
            <>
              <button className={btnSecondary} onClick={() => setDraft((d) => [...d!, { room_label: '', length_m: 0, width_m: 0 }])}>Add a room</button>
              <button className={btnPrimary} onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save room table'}</button>
              <button className={btnQuiet} onClick={() => { setDraft(null); setError(null); }} disabled={saving}>Cancel</button>
            </>
          ) : (
            <button className={btnSecondary} onClick={() => setDraft(view.rooms.length ? view.rooms.map((r) => ({ ...r })) : [{ room_label: '', length_m: 0, width_m: 0 }])}>
              {view.rooms.length ? 'Edit room table' : 'Enter room table'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
