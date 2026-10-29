import type { Metadata } from "next";
import { Martel, Mukta } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import Navbar from "@/components/Navbar";
import { BrandMark } from "@/components/Brand";

// Both from Indian type foundries, and both carry Devanagari for a later Hindi interface
const martel = Martel({ variable: "--font-martel", subsets: ["latin"], weight: ["400", "700", "800"] });
const mukta = Mukta({ variable: "--font-mukta", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: "ProofPath AI | Evidence-first review of AICTE applications",
  description: "Every finding on an AICTE application points to the document and page it came from (SIH26261 prototype)",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${martel.variable} ${mukta.variable} h-full`}>
      <body className="flex min-h-full flex-col bg-paper text-ink">
        <Suspense fallback={<div className="h-14" />}>
          <Navbar />
        </Suspense>
        <main className="flex-1">{children}</main>
        {/* The spec's prototype notice (section 13), kept on every page in the footer rather than a strip on top */}
        <footer className="border-t border-rule bg-sheet">
          <div className="mx-auto flex max-w-7xl flex-wrap items-start justify-between gap-x-10 gap-y-3 px-4 py-5 text-xs text-ink-2 sm:px-6">
            <p className="flex items-center gap-2 font-semibold text-ink">
              <BrandMark className="size-4" />
              Decision support only. Final decision: Pending (authorised AICTE official).
            </p>
            <p className="max-w-[60ch]">Prototype demo. All institutions, people, documents and photos are fictional. Rules are illustrative, not official AICTE rules.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
