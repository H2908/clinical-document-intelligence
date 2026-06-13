"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, PatientOverview } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

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
      .then((p) => {
        if (!cancelled) {
          setPatient(p);
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
    return <main className="p-8 text-slate-500">Loading overview...</main>;
  }

  if (error || !patient) {
    return (
      <main className="p-8">
        <div className="max-w-3xl bg-white rounded-xl border border-red-200 p-6">
          <h1 className="text-lg font-medium text-red-700">
            Couldn&apos;t load overview
          </h1>
          <p className="text-sm text-red-600 mt-2">
            {error || "Patient not found."}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">
            {patient.name}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Age {patient.age} · {patient.sex} · NHS {patient.nhs_number}
          </p>
        </header>

        <section className="grid grid-cols-3 gap-4">
          <StatCard label="Documents" value={patient.stats.document_count} />
          <StatCard label="Open flags" value={patient.stats.open_flag_count} />
          <StatCard
            label="Contradictions"
            value={patient.stats.contradiction_count}
          />
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Active conditions</h2>
          </header>
          {patient.conditions.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">
              No conditions documented.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {patient.conditions.map((c, i) => (
                <li key={i} className="px-5 py-3 flex justify-between">
                  <span className="text-slate-900">{c.name}</span>
                  {c.icd10_code && (
                    <span className="text-xs font-mono text-slate-500">
                      {c.icd10_code}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Current medications</h2>
          </header>
          {patient.medications.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">
              No medications documented.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {patient.medications.map((m, i) => (
                <li key={i} className="px-5 py-3 flex justify-between gap-4">
                  <span className="text-slate-900">{m.drug}</span>
                  <span className="text-sm text-slate-500">
                    {m.dose || "-"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-medium text-slate-900">Top open flags</h2>
            <span className="text-xs text-slate-500">
              Up to 3 shown - see Flags tab for full list
            </span>
          </header>
          {patient.top_flags.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No open flags.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {patient.top_flags.map((f) => (
                <li key={f.flag_id} className="px-5 py-3">
                  <div className="flex items-start gap-3">
                    <SeverityBadge severity={f.severity} />
                    <div className="min-w-0">
                      <div className="text-sm text-slate-900">
                        {f.description}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {f.category}
                      </div>
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

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}
