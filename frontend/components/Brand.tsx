import React from 'react';
import Link from 'next/link';

/** A sheet with a folded corner and one highlighter stroke across it: a value cited from a page. */
export function BrandMark({ className = 'size-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="none">
      <path d="M5 2.75h9.5L19.25 7.5V21.25H5z" fill="var(--color-sheet)" stroke="var(--color-ink)" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M14.5 2.75V7.5h4.75" stroke="var(--color-ink)" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M7.5 11.25h9" stroke="var(--color-rule-strong)" strokeWidth="1.25" strokeLinecap="round" />
      <path d="M7 14.6c3-.5 6.2-.55 10.2-.2" stroke="var(--color-mark)" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M7.5 14.5h7" stroke="var(--color-ink)" strokeWidth="1.25" strokeLinecap="round" />
      <path d="M7.5 17.75h5.5" stroke="var(--color-rule-strong)" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

/** The ProofPath wordmark: the mark, then the name set in the heading face. */
export default function Brand({ href = '/welcome' }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 font-serif text-xl font-extrabold leading-none text-ink" title="ProofPath AI">
      <BrandMark />
      <span className="translate-y-px">ProofPath AI</span>
    </Link>
  );
}
