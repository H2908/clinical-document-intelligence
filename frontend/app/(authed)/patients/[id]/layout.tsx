"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, PatientOverview } from "@/lib/api";
import PatientSidebar from "@/components/PatientSidebar";

export default function PatientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";
  const [patient, setPatient] = useState<PatientOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    api
      .getPatient(patientId)
      .then((p) => {
        if (!cancelled) setPatient(p);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  if (error) {
    return (
      <main className="min-h-screen bg-slate-50 p-8">
        <div className="max-w-3xl mx-auto bg-white rounded-xl border border-red-200 p-6">
          <h1 className="text-lg font-medium text-red-700">
            Couldn&apos;t load patient
          </h1>
          <p className="text-sm text-red-600 mt-2">{error}</p>
        </div>
      </main>
    );
  }

  if (!patient) {
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">
        Loading patient…
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <PatientSidebar
        patientId={patient.id}
        patientName={patient.name}
        patientDob={patient.dob}
        patientNhs={patient.nhs_number}
      />
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
