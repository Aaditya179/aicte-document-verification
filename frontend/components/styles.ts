/**
 * Shared class names. A plain module rather than part of ui.tsx, which is a client module: a server
 * component importing a string from a client module gets a reference, not the string.
 */
// Colours come only from the tokens in globals.css.
export const sheet = 'rounded-sheet border border-rule bg-sheet';
export const card = `${sheet} p-5`;
export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-control bg-ink px-4 py-2 text-sm font-semibold text-sheet shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_22%,transparent)] transition-colors duration-150 hover:bg-ink-2 disabled:cursor-not-allowed disabled:opacity-50';
export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-control border border-ink bg-sheet px-4 py-2 text-sm font-semibold text-ink transition-colors duration-150 hover:bg-ink-wash disabled:cursor-not-allowed disabled:opacity-50';
export const btnQuiet =
  'inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-sm font-medium text-ink underline decoration-rule-strong underline-offset-4 transition-[text-decoration-color] duration-150 hover:decoration-ink disabled:opacity-50';
export const input =
  'w-full rounded-control border border-rule-strong bg-sheet px-3 py-2 text-sm text-ink transition-[border-color,box-shadow] duration-150 placeholder:text-ink-3 hover:border-ink-3 focus:border-ink focus:shadow-[0_0_0_3px_var(--color-ink-wash)] focus:outline-none';
export const label = 'mb-1 block text-sm font-semibold text-ink';
export const th = 'border-b border-rule-strong px-3 py-2 text-left text-xs font-semibold text-ink-2';
export const td = 'border-b border-rule px-3 py-2.5 align-top text-sm';
