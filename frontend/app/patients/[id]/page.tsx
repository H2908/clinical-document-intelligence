"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, PatientOverview } from "@/lib/api";

export default function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<PatientOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPatient(id)
      .then(setPatient)
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!patient) return <div className="p-8 text-slate-500">Loading…</div>;

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-5xl mx-auto">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← All patients
        </Link>

        <header className="mt-4 mb-6">
          <h1 className="text-3xl font-semibold text-slate-900">
            {patient.name}
          </h1>
          <p className="text-slate-500 font-mono text-sm mt-1">
            DOB {patient.dob} · NHS {patient.nhs_number} · {patient.sex} ·{" "}
            {patient.age} years
          </p>
        </header>

        {/* Stat cards */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Total documents" value={patient.stats.document_count} />
          <StatCard label="Open flags" value={patient.stats.open_flag_count} />
          <StatCard label="Contradictions" value={patient.stats.contradiction_count} />
        </div>

        {/* Active conditions */}
        <Section title="Active conditions">
          <div className="flex flex-wrap gap-2">
            {patient.conditions.map((c) => (
              <span
                key={c.icd10_code}
                className="px-3 py-1.5 rounded-full bg-blue-50 text-blue-900 text-sm"
              >
                {c.name}{" "}
                <span className="font-mono text-blue-700 ml-1 text-xs">
                  {c.icd10_code}
                </span>
              </span>
            ))}
          </div>
        </Section>

        {/* Medications */}
        <Section title="Current medications">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-2 font-medium">Drug</th>
                <th className="py-2 font-medium">Dose</th>
                <th className="py-2 font-medium">Started</th>
                <th className="py-2 font-medium">Flag</th>
              </tr>
            </thead>
            <tbody>
              {patient.medications.map((m, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  <td className="py-2">{m.drug}</td>
                  <td className="py-2 font-mono text-slate-600">{m.dose}</td>
                  <td className="py-2 font-mono text-slate-500">
                    {m.started ?? "—"}
                  </td>
                  <td className="py-2 text-amber-700">{m.flag ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="text-3xl font-semibold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
      <h2 className="font-medium text-slate-900 mb-3">{title}</h2>
      {children}
    </section>
  );
}