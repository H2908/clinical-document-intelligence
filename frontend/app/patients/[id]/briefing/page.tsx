"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, BriefingResponse, Observation, DocumentRow } from "@/lib/api";
import ImageViewer from "@/components/ImageViewer";
import SeverityBadge from "@/components/SeverityBadge";

function icdColor(code: string | null): string {
  if (!code) return "bg-slate-100 text-slate-600";
  const ch = code[0]?.toUpperCase();
  if (ch === "I") return "bg-blue-100 text-blue-700";
  if (ch === "E") return "bg-green-100 text-green-700";
  if (ch === "N") return "bg-purple-100 text-purple-700";
  if (ch === "C") return "bg-red-100 text-red-700";
  return "bg-slate-100 text-slate-600";
}

function fmtDate(d: string): string {
  try {
    return new Date(d).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return d;
  }
}

const WarnIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
  </svg>
);

const PrintIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" />
  </svg>
);

export default function BriefingPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [briefing, setBriefing] = useState<BriefingResponse | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewingDoc, setViewingDoc] = useState<{ id: string; name: string } | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.getBriefing(patientId),
      api.getObservations(patientId).catch(() => ({ observations: [] as Observation[], patient_id: patientId, count: 0 })),
      api.listDocuments(patientId).catch(() => ({ documents: [] as DocumentRow[] })),
    ])
      .then(([b, obs, docs]) => {
        if (!cancelled) {
          setBriefing(b);
          // Most recent 6 observations
          setObservations(
            [...obs.observations].sort((a, b) => b.observation_date.localeCompare(a.observation_date)).slice(0, 6)
          );
          // Last 3 documents received
          setDocuments(
            [...docs.documents].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3)
          );
          setError(null);
        }
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [patientId]);

  if (loading) return <main className="p-8 text-sm text-slate-500">Loading briefing...</main>;

  if (error) return (
    <main className="p-8">
      <div className="max-w-3xl bg-white rounded-xl border border-red-200 p-6">
        <h1 className="text-lg font-medium text-red-700">Couldn&apos;t load briefing</h1>
        <p className="text-sm text-red-600 mt-2">{error}</p>
      </div>
    </main>
  );

  if (!briefing || !briefing.available || !briefing.summary) return (
    <main className="p-8">
      <div className="max-w-3xl bg-white rounded-xl border border-slate-200 p-6">
        <h1 className="text-lg font-medium text-slate-900">Briefing not available</h1>
        <p className="text-sm text-slate-500 mt-2">
          {briefing?.message || "No briefing has been generated for this patient yet. Upload documents and the briefing agent will produce one."}
        </p>
      </div>
    </main>
  );

  const s = briefing.summary;

  return (
    <main className="p-8">
      <div className="max-w-3xl mx-auto space-y-5">

        {/* Title + Print */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Pre-appointment briefing</h1>
            {briefing.generated_at && (
              <p className="text-sm text-slate-500 mt-0.5">
                Generated {new Date(briefing.generated_at).toLocaleString("en-GB")}
              </p>
            )}
            {briefing.is_stale && (
              <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-xs">stale</span>
            )}
          </div>
          <button
            onClick={() => window.print()}
            className="print-hide flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 text-sm text-slate-700 hover:bg-slate-50 shrink-0"
          >
            <PrintIcon />
            Print
          </button>
        </div>

        {/* Disclaimer banner */}
        {briefing.disclaimer && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-900">
            {briefing.disclaimer}
          </div>
        )}

        {/* Patient summary line */}
        <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
          <div className="text-lg font-semibold text-slate-900">{s.patient.name}</div>
          <div className="text-sm text-slate-500 mt-0.5">
            {s.patient.sex}
            {" · DOB "}
            {s.patient.dob}
            {" · NHS "}
            {s.patient.nhs_number}
          </div>
        </div>

        {/* Active Conditions */}
        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Active conditions</h2>
          </header>
          <div className="px-5 py-4 flex flex-wrap gap-2">
            {s.conditions.length === 0 ? (
              <span className="text-sm text-slate-500">None documented.</span>
            ) : (
              s.conditions.map((c, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 text-slate-800 text-sm"
                >
                  {c.name}
                  {c.icd10_code && (
                    <span className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded ${icdColor(c.icd10_code)}`}>
                      {c.icd10_code}
                    </span>
                  )}
                </span>
              ))
            )}
          </div>
        </section>

        {/* Current Medications */}
        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Current medications</h2>
          </header>
          {s.medications.length === 0 ? (
            <p className="px-5 py-4 text-sm text-slate-500">None documented.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {s.medications.map((m, i) => (
                <li key={i} className="px-5 py-3 flex items-start justify-between gap-4">
                  <span className="text-sm text-slate-900 font-medium">{m.drug}</span>
                  <div className="text-right shrink-0">
                    <div className="text-sm text-slate-600">{m.dose || "—"}</div>
                    {m.flag && (
                      <div className="flex items-center gap-1 text-xs text-amber-700 mt-0.5 justify-end">
                        <WarnIcon />
                        {m.flag}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Recent Results */}
        {observations.length > 0 && (
          <section className="bg-white rounded-xl border border-slate-200">
            <header className="px-5 py-3 border-b border-slate-200">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recent results</h2>
            </header>
            <ul className="divide-y divide-slate-100">
              {observations.map((o) => (
                <li key={o.observation_id} className="px-5 py-3 flex items-center justify-between">
                  <span className="text-sm text-slate-900 font-medium">{o.test}</span>
                  <div className="text-right">
                    <span className="text-sm text-slate-700">
                      {o.value}{o.unit ? ` ${o.unit}` : ""}
                    </span>
                    <div className="text-xs text-slate-400 mt-0.5">{fmtDate(o.observation_date)}</div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Open Flags */}
        {s.open_flags.length > 0 && (
          <section className="bg-white rounded-xl border border-slate-200">
            <header className="px-5 py-3 border-b border-slate-200">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Open flags</h2>
            </header>
            <ul className="divide-y divide-slate-100">
              {s.open_flags.map((f, i) => (
                <li key={i} className="px-5 py-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge severity={f.severity} />
                    <span className="text-xs font-semibold tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded uppercase">
                      {f.category.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm text-slate-800">{f.description}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Last Documents Received */}
        {documents.length > 0 && (
          <section className="bg-white rounded-xl border border-slate-200">
            <header className="px-5 py-3 border-b border-slate-200">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Last documents received</h2>
            </header>
            <ul className="divide-y divide-slate-100">
              {documents.map((d) => (
                <li key={d.id} className="px-5 py-3 flex items-center justify-between">
                  <button
                    onClick={() => setViewingDoc({ id: d.id, name: d.name })}
                    className="text-sm text-blue-600 hover:underline text-left"
                  >
                    {d.name}
                  </button>
                  <span className="text-sm text-slate-500">{fmtDate(d.date)}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

      </div>

      <ImageViewer
        documentId={viewingDoc?.id ?? null}
        documentName={viewingDoc?.name ?? null}
        onClose={() => setViewingDoc(null)}
      />
    </main>
  );
}
