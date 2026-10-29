import type { Metadata } from "next";
import { Martel, Mukta } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import Navbar from "@/components/Navbar";

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
        <footer className="space-y-1 border-t border-rule px-4 py-4 text-center text-xs text-ink-2">
          <p>Decision support only. Final decision: Pending (authorised AICTE official).</p>
          <p>Prototype demo. All institutions, people, documents and photos are fictional. Rules are illustrative, not official AICTE rules.</p>
        </footer>
      </body>
    </html>
  );
}
