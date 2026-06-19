"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, PatientOverview } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

function timeAgo(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  const months = Math.floor(ms / (1000 * 60 * 60 * 24 * 30.44));
  if (months >= 12) return `${Math.floor(months / 12)}yr ago`;
  if (months >= 1) return `${months}mo ago`;
  const days = Math.floor(ms / (1000 * 60 * 60 * 24));
  if (days >= 1) return `${days}d ago`;
  return "Today";
}

function icdColor(code: string | null): string {
  if (!code) return "bg-slate-100 text-slate-600";
  const ch = code[0]?.toUpperCase();
  if (ch === "I") return "bg-blue-100 text-blue-700";
  if (ch === "E") return "bg-green-100 text-green-700";
  if (ch === "N") return "bg-purple-100 text-purple-700";
  if (ch === "C") return "bg-red-100 text-red-700";
  if (ch === "J") return "bg-cyan-100 text-cyan-700";
  return "bg-slate-100 text-slate-600";
}

const WarnIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
  </svg>
);

export default function PatientOverviewPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";
  const [patient, setPatient] = useState<PatientOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getPatient(patientId)
      .then((p) => { if (!cancelled) { setPatient(p); setError(null); } })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [patientId]);

  if (loading) return <main className="p-8 text-sm text-slate-500">Loading overview...</main>;
  if (error || !patient) return (
    <main className="p-8">
      <div className="max-w-3xl bg-white rounded-xl border border-red-200 p-6">
        <h1 className="text-lg font-medium text-red-700">Couldn&apos;t load overview</h1>
        <p className="text-sm text-red-600 mt-2">{error || "Patient not found."}</p>
      </div>
    </main>
  );

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-5">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">{patient.name}</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Patient record overview · last updated {timeAgo(patient.last_updated)}
          </p>
        </header>

        {/* Stats row */}
        <section className="grid grid-cols-4 gap-4">
          <StatCard
            value={patient.stats.document_count}
            label="Documents"
            sub={patient.stats.document_count === 0 ? "None uploaded" : ""}
          />
          <StatCard
            value={patient.stats.open_flag_count}
            label="Open flags"
            sub={patient.stats.open_flag_count > 0 ? "Review before appointment" : "All clear"}
            alert={patient.stats.open_flag_count > 0 ? "high" : "ok"}
          />
          <StatCard
            value={patient.stats.contradiction_count}
            label="Contradictions"
            sub={patient.stats.contradiction_count > 0 ? "Needs clinical review" : "None detected"}
            alert={patient.stats.contradiction_count > 0 ? "medium" : "ok"}
          />
          <StatCard
            value={timeAgo(patient.last_updated)}
            label="Last updated"
            sub=""
          />
        </section>

        {/* Active Conditions */}
        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Active conditions</h2>
          </header>
          <div className="px-5 py-4 flex flex-wrap gap-2">
            {patient.conditions.length === 0 ? (
              <span className="text-sm text-slate-500">No conditions documented.</span>
            ) : (
              patient.conditions.map((c, i) => (
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
          <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Current medications</h2>
            {patient.medications.length > 0 && (
              <span className="text-xs text-slate-500">{patient.medications.length} active</span>
            )}
          </header>
          {patient.medications.length === 0 ? (
            <p className="px-5 py-4 text-sm text-slate-500">No medications documented.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-400 border-b border-slate-100">
                    <th className="px-5 py-2 text-left font-medium">Drug</th>
                    <th className="px-5 py-2 text-left font-medium">Dose</th>
                    <th className="px-5 py-2 text-left font-medium">Last prescribed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {patient.medications.map((m, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-5 py-3 text-slate-900 font-medium">{m.drug}</td>
                      <td className="px-5 py-3 text-slate-600">{m.dose || "—"}</td>
                      <td className="px-5 py-3 text-slate-500 text-xs font-mono">{m.last_prescribed || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Top Open Flags */}
        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Top open flags</h2>
            <Link href={`/patients/${patientId}/flags`} className="text-xs text-blue-600 hover:underline">
              View all
            </Link>
          </header>
          {patient.top_flags.length === 0 ? (
            <p className="px-5 py-4 text-sm text-slate-500">No open flags.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {patient.top_flags.map((f) => (
                <li key={f.flag_id} className="px-5 py-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge severity={f.severity} />
                    <span className="text-xs font-semibold tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded uppercase">
                      {f.category.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700">{f.description}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

function StatCard({
  label,
  value,
  sub,
  alert,
}: {
  label: string;
  value: number | string;
  sub?: string;
  alert?: "high" | "medium" | "ok";
}) {
  const border =
    alert === "high"   ? "border-l-4 border-l-nhs-red   bg-nhs-red-light" :
    alert === "medium" ? "border-l-4 border-l-nhs-yellow bg-nhs-yellow-light" :
    "bg-white";
  const valueColor =
    alert === "high"   ? "text-nhs-red" :
    alert === "medium" ? "text-[#7a5200]" :
    "text-slate-900";
  const subColor =
    alert === "ok" ? "text-nhs-green" :
    alert === "high" ? "text-nhs-red/80" :
    "text-slate-500";

  return (
    <div className={`rounded-xl border border-slate-200 px-5 py-4 ${border}`}>
      <div className={`text-2xl font-bold ${valueColor}`}>{value}</div>
      <div className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wide">{label}</div>
      {sub && <div className={`text-xs mt-1 ${subColor}`}>{sub}</div>}
    </div>
  );
}
