import React from 'react';
import Link from 'next/link';
import { FileSearch } from 'lucide-react';

/** The ProofPath wordmark, in the shared terracotta palette. */
export default function Brand({ href = '/welcome' }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 transition hover:opacity-85" title="ProofPath AI">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#C25E26] text-white shadow-2xs">
        <FileSearch className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="font-serif text-lg font-bold tracking-tight text-[#1C1917]">
        ProofPath <span className="text-[#C25E26]">AI</span>
      </span>
    </Link>
  );
}
