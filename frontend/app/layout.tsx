import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import Navbar from "@/components/Navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ProofPath AI | Traceable case files for AICTE applications",
  description: "ProofPath AI turns the documents of an AICTE application into one traceable case file (SIH26261)",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      style={{ backgroundColor: '#FAF7F2', colorScheme: 'light' }}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased bg-[#FAF7F2]`}
    >
      <body
        style={{ backgroundColor: '#FAF7F2', colorScheme: 'light' }}
        className="min-h-full flex flex-col bg-[#FAF7F2] text-[#1C1917] selection:bg-[#FBF0E4] selection:text-[#C25E26] bg-grid-texture antialiased"
      >
        <Suspense fallback={<div className="h-16 bg-transparent" />}>
          <Navbar />
        </Suspense>
        <main className="flex-1 bg-[#FAF7F2] bg-grid-texture">{children}</main>
        <footer className="py-4 border-t border-[#E8E2D8] text-center text-xs text-stone-500 bg-[#FAF7F2]/90 backdrop-blur-xs">
          Advisory only: final decisions rest with the competent authority.
        </footer>
      </body>
    </html>
  );
}
