from pathlib import Path

content = r'''"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, BriefingResponse } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

export default function BriefingPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [briefing, setBriefing] = useState<BriefingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getBriefing(patientId)
      .then((b) => {
        if (!cancelled) {
          setBriefing(b);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  if (loading) {
    return <main className="p-8 text-slate-500">Loading briefing...</main>;
  }

  if (error) {
    return (
      <main className="p-8">
        <div className="max-w-3xl bg-white rounded-xl border border-red-200 p-6">
          <h1 className="text-lg font-medium text-red-700">Couldn&apos;t load briefing</h1>
          <p className="text-sm text-red-600 mt-2">{error}</p>
        </div>
      </main>
    );
  }

  if (!briefing || !briefing.available || !briefing.summary) {
    return (
      <main className="p-8">
        <div className="max-w-3xl bg-white rounded-xl border border-slate-200 p-6">
          <h1 className="text-lg font-medium text-slate-900">Briefing not available</h1>
          <p className="text-sm text-slate-500 mt-2">
            {briefing?.message || "No briefing has been generated for this patient yet. Upload documents and the briefing agent will produce one."}
          </p>
        </div>
      </main>
    );
  }

  const s = briefing.summary;

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Pre-appointment briefing</h1>
            <p className="text-sm text-slate-500 mt-1">
              {s.patient.name} - DOB {s.patient.dob} - NHS {s.patient.nhs_number}
            </p>
          </div>
          <div className="flex items-start gap-3 print-hide">
            <div className="text-right text-xs text-slate-500">
              {briefing.generated_at && <div>Generated {new Date(briefing.generated_at).toLocaleString()}</div>}
              {briefing.is_stale && (
                <div className="mt-1 inline-block px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">stale</div>
              )}
            </div>
            <button
              onClick={() => window.print()}
              className="px-3 py-2 rounded-lg bg-slate-900 text-white text-sm hover:bg-slate-800 shrink-0"
              title="Open the browser print dialog. Choose 'Save as PDF' to keep a copy."
            >
              Print
            </button>
          </div>
        </header>

        {briefing.disclaimer && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-900">
            {briefing.disclaimer}
          </div>
        )}

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Active conditions ({s.conditions.length})</h2>
          </header>
          {s.conditions.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">None documented.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {s.conditions.map((c, i) => (
                <li key={i} className="px-5 py-3 flex justify-between">
                  <span className="text-slate-900">{c.name}</span>
                  {c.icd10_code && <span className="text-xs font-mono text-slate-500">{c.icd10_code}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Current medications ({s.medications.length})</h2>
          </header>
          {s.medications.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">None documented.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {s.medications.map((m, i) => (
                <li key={i} className="px-5 py-3 flex justify-between gap-4">
                  <span className="text-slate-900">{m.drug}</span>
                  <span className="text-sm text-slate-500">{m.dose || "-"}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Open flags ({s.open_flags.length})</h2>
          </header>
          {s.open_flags.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No open flags.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {s.open_flags.map((f, i) => (
                <li key={i} className="px-5 py-3">
                  <div className="flex items-start gap-3">
                    <SeverityBadge severity={f.severity} />
                    <div className="min-w-0">
                      <div className="text-sm text-slate-900">{f.description}</div>
                      <div className="text-xs text-slate-500 mt-1">{f.category}</div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
'''

target = Path("frontend/app/patients/[id]/briefing/page.tsx")
target.write_text(content, encoding="utf-8", newline="\n")
print(f"Wrote {target}")
print(f"Lines: {len(content.splitlines())}")
print(f"First 3 bytes: {open(target, 'rb').read(3).hex()}")