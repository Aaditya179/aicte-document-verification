import React from 'react';
import Link from 'next/link';

/** The ProofPath wordmark: set in the heading face, nothing more. */
export default function Brand({ href = '/welcome' }: { href?: string }) {
  return (
    <Link href={href} className="font-serif text-xl font-extrabold leading-none text-ink" title="ProofPath AI">
      ProofPath AI
    </Link>
  );
}
