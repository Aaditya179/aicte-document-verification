import React from 'react';
import Link from 'next/link';
import { ArrowRight, CheckCircle2, AlertTriangle, HelpCircle, Network, FileText, Quote, Sparkles } from 'lucide-react';
import Brand from '@/components/Brand';
import ServerWakeNote from '@/components/ServerWakeNote';

const focusRing = 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#C25E26]';

const STEPS = [
  { icon: FileText, title: 'Read every document', text: 'Each upload is read page by page. Every value, from land area to fire NOC expiry, is kept with the page and the line it came from.' },
  { icon: CheckCircle2, title: 'Check each field', text: 'Values are compared across documents and against the record, across units and spellings, and each field gets a verdict with its reason.' },
  { icon: Network, title: 'Look across institutions', text: 'The same land parcel, faculty member or document turning up in more than one application is flagged, which no single review can see.' },
];

const VERDICTS = [
  { icon: CheckCircle2, label: 'Verified', tone: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    field: 'Institution name', why: 'The lease and the building plan name the same institution once abbreviations are expanded.' },
  { icon: AlertTriangle, label: 'Conflict', tone: 'bg-red-50 border-red-200 text-red-800',
    field: 'Land area', why: 'The lease says 10 acres and the building plan 3.2 hectares, 21% apart; the limit is 2%.' },
  { icon: HelpCircle, label: 'Unverified', tone: 'bg-amber-50 border-amber-200 text-amber-900',
    field: 'Fire NOC validity', why: 'The expiry date was read with 62% confidence and no officer has confirmed it yet.' },
];

export default function WelcomePage() {
  return (
    <div className="min-h-screen bg-[#FAF7F2] bg-grid-texture text-[#1C1917] font-sans">
      <header className="w-full pt-4 pb-2 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          <Brand />
          <Link href="/login" className={`px-5 py-2.5 rounded-full bg-[#C25E26] hover:bg-[#A84A19] text-white text-xs font-bold transition shadow-sm flex items-center gap-1.5 ${focusRing}`}>
            Sign in <ArrowRight className="w-3.5 h-3.5" aria-hidden />
          </Link>
        </div>
      </header>

      <main>
        <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-12 pb-16">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#FBF0E4] border border-[#F0D5BE] text-[#C25E26] text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" aria-hidden /> SIH26261 prototype
              </div>
              <h1 className="text-3xl sm:text-5xl font-serif font-bold tracking-tight leading-[1.12]">
                One traceable case file for every AICTE application.
              </h1>
              <p className="text-base text-stone-600 leading-relaxed max-w-xl">
                ProofPath AI turns the documents of an application into a single case file that shows what is
                verified, what conflicts and what is unverified, and why. It also catches patterns across
                institutions that checking one application at a time cannot see.
              </p>
              <div className="flex flex-wrap items-center gap-3.5">
                <Link href="/login?demo=verifier" className={`px-6 py-3 rounded-full bg-[#C25E26] hover:bg-[#A84A19] text-white font-medium text-sm transition shadow-sm flex items-center gap-2 ${focusRing}`}>
                  Enter as verifier <ArrowRight className="w-4 h-4" aria-hidden />
                </Link>
                <Link href="/login?demo=analyst" className={`px-6 py-3 rounded-full bg-[#FBF0E4] border-2 border-[#C25E26] text-[#C25E26] font-bold text-sm transition flex items-center gap-2 ${focusRing}`}>
                  <Network className="w-4 h-4" aria-hidden /> See cross-institution patterns
                </Link>
              </div>
              <p className="text-xs text-stone-600 bg-white/80 border border-[#E8E2D8] p-2.5 rounded-xl max-w-lg">
                All data is dummy. Every finding is advisory: officers confirm or overrule it, and the decision stays with them.
              </p>
              <ServerWakeNote className="max-w-lg" />
            </div>

            <div className="lg:col-span-5 bg-white rounded-2xl border border-[#E8E2D8] p-6 shadow-2xs">
              <span className="text-[11px] font-semibold text-stone-500">Demo case file</span>
              <h2 className="font-serif font-bold text-base mt-0.5">PP-2027-0001 · Demo Institute of Technology</h2>
              <ul className="mt-4 space-y-3">
                {VERDICTS.map((v) => {
                  const Icon = v.icon;
                  return (
                    <li key={v.field} className={`rounded-xl border p-3 ${v.tone}`}>
                      <p className="flex items-center gap-1.5 text-xs font-bold"><Icon className="w-4 h-4" aria-hidden /> {v.label} · {v.field}</p>
                      <p className="mt-1 flex gap-1.5 text-xs leading-relaxed"><Quote className="w-3 h-3 mt-0.5 shrink-0 opacity-60" aria-hidden /> {v.why}</p>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-20">
          <h2 className="text-2xl font-serif font-bold">How it works</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              return (
                <div key={s.title} className="bg-white rounded-2xl border border-[#E8E2D8] p-5">
                  <div className="flex items-center gap-2">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#FBF0E4] text-[#C25E26]"><Icon className="w-4 h-4" aria-hidden /></span>
                    <span className="text-xs font-semibold text-stone-500">Step {i + 1}</span>
                  </div>
                  <h3 className="mt-3 font-serif font-bold">{s.title}</h3>
                  <p className="mt-1 text-sm text-stone-600 leading-relaxed">{s.text}</p>
                </div>
              );
            })}
          </div>
        </section>
      </main>

      <footer className="py-4 border-t border-[#E8E2D8] text-center text-xs text-stone-500">
        Advisory only: final decisions rest with the competent authority.
      </footer>
    </div>
  );
}
