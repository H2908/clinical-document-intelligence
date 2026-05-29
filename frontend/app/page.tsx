"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, PatientCard, NewPatient } from "@/lib/api";

export default function LandingPage() {
  const [patients, setPatients] = useState<PatientCard[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = async (q?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPatients(q);
      setPatients(data.patients);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold text-slate-900">
            Clinical Document Intelligence
          </h1>
          <p className="text-slate-600 mt-1">
            Search a patient, or add a new one.
          </p>
        </header>

        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder="Search by name or NHS number…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(search)}
            className="flex-1 px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => load(search)}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-800"
          >
            Search
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            {showForm ? "Cancel" : "+ Add new patient"}
          </button>
        </div>

        {showForm && <NewPatientForm onCreated={() => { setShowForm(false); load(); }} />}

        <section className="bg-white rounded-xl border border-slate-200">
          <div className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Recent patients</h2>
          </div>
          {loading && <div className="p-6 text-slate-500">Loading…</div>}
          {error && <div className="p-6 text-red-600">Error: {error}</div>}
          {!loading && !error && patients.length === 0 && (
            <div className="p-6 text-slate-500">No patients found.</div>
          )}
          <ul className="divide-y divide-slate-100">
            {patients.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/patients/${p.id}`}
                  className="flex items-center justify-between px-5 py-4 hover:bg-slate-50"
                >
                  <div>
                    <div className="font-medium text-slate-900">{p.name}</div>
                    <div className="text-sm text-slate-500 font-mono">
                      DOB {p.dob} · NHS {p.nhs_number}
                    </div>
                  </div>
                  <div className="text-sm text-slate-500">
                    {p.document_count} documents · {p.open_flag_count} open flags
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

function NewPatientForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<NewPatient>({
    name: "",
    dob: "",
    nhs_number: "",
    sex: "M",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.createPatient(form);
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 grid grid-cols-2 gap-3">
      <input
        placeholder="Full name"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300"
      />
      <input
        type="date"
        value={form.dob}
        onChange={(e) => setForm({ ...form, dob: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300"
      />
      <input
        placeholder="NHS number (e.g. 485 621 3847)"
        value={form.nhs_number}
        onChange={(e) => setForm({ ...form, nhs_number: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300 font-mono"
      />
      <select
        value={form.sex}
        onChange={(e) =>
          setForm({ ...form, sex: e.target.value as NewPatient["sex"] })
        }
        className="px-3 py-2 rounded-lg border border-slate-300"
      >
        <option>M</option>
        <option>F</option>
        <option>Other</option>
      </select>
      {error && (
        <div className="col-span-2 text-sm text-red-600">{error}</div>
      )}
      <button
        onClick={submit}
        disabled={busy || !form.name || !form.dob || !form.nhs_number}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:bg-slate-300"
      >
        {busy ? "Creating…" : "Create patient"}
      </button>
    </div>
  );
}