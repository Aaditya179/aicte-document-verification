import { humanize } from '@/lib/types';

/** A version's thresholds in words: "Min area sqm: 4500; Area tolerance pct: 1". */
export function paramsText(p: Record<string, unknown>) {
  const entries = Object.entries(p ?? {});
  if (entries.length === 0) return '—';
  return entries.map(([k, v]) => `${humanize(k)}: ${Array.isArray(v) ? v.join(', ') : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v)}`).join('; ');
}
