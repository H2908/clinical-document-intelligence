"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getUser } from "@/lib/auth";

const features = [
  {
    title: "Documents in, structure out",
    body: "Upload scanned GP letters, cardiology notes, lab reports — we extract the diagnoses, medications, observations and dates so a clinician can review one structured record.",
  },
  {
    title: "Flagged for review",
    body: "Allergy conflicts, overdue referrals and drug-safety signals surface with provenance to the source document and quote, ready for the next appointment.",
  },
  {
    title: "Briefings in seconds",
    body: "A pre-appointment briefing assembles active conditions, current medications, recent results and open flags in a printable, prioritised view.",
  },
];

export default function LandingPage() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(getUser() !== null);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-nhs-pale">
      <header className="bg-nhs-blue text-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="border-2 border-white text-white text-xs font-bold px-1.5 py-0.5 leading-none tracking-widest">
              NHS
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                Clinical Document Intelligence
              </h1>
              <p className="text-xs text-white/70 mt-0.5">
                Administrative document structuring · For clinical review only
              </p>
            </div>
          </div>
          <nav className="flex items-center gap-3 text-sm">
            {signedIn ? (
              <Link
                href="/dashboard"
                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
              >
                Open dashboard →
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-2 rounded-lg bg-white text-nhs-blue font-medium hover:bg-nhs-blue-light transition-colors"
                >
                  Get an account
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 py-16 space-y-16">
          {/* Hero */}
          <section className="text-center space-y-5">
            <h2 className="text-4xl md:text-5xl font-semibold text-slate-900 tracking-tight">
              Turn scattered clinical documents<br />into a structured record.
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Built for NHS trusts who need to triage pre-appointment paperwork in
              minutes, not hours. Upload, flag, brief — then review.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <Link
                href={signedIn ? "/dashboard" : "/login"}
                className="px-6 py-3 rounded-lg bg-nhs-blue text-white font-medium hover:bg-nhs-blue-dark transition-colors"
              >
                {signedIn ? "Open dashboard" : "Sign in"}
              </Link>
              <Link
                href="/register"
                className="px-6 py-3 rounded-lg bg-white border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
              >
                Register with invite
              </Link>
            </div>
          </section>

          {/* Features */}
          <section className="grid md:grid-cols-3 gap-5">
            {features.map((f, i) => (
              <div
                key={f.title}
                className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-3"
              >
                <div className="w-8 h-8 rounded-lg bg-nhs-blue-light text-nhs-blue font-semibold flex items-center justify-center text-sm">
                  {i + 1}
                </div>
                <h3 className="font-semibold text-slate-900">{f.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{f.body}</p>
              </div>
            ))}
          </section>

          {/* Trust statement */}
          <section className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-3">
            <h3 className="font-semibold text-slate-900">How we handle your data</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Document text and structured outputs stay within your trust. Outputs
              surface information for a clinician to review — they are not
              treatment recommendations or clinical advice. Each trust runs an
              isolated tenant boundary; documents never cross trusts.
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-slate-200 bg-white/60">
        <div className="max-w-5xl mx-auto px-6 py-6 text-center text-xs text-slate-500">
          For administrative use only · outputs do not constitute clinical advice
        </div>
      </footer>
    </div>
  );
}
