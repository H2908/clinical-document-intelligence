"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, PatientCard, NewPatient } from "@/lib/api";

function timeAgo(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  const months = Math.floor(ms / (1000 * 60 * 60 * 24 * 30.44));
  if (months >= 12) return `${Math.floor(months / 12)}yr ago`;
  if (months >= 1) return `${months}mo ago`;
  const days = Math.floor(ms / (1000 * 60 * 60 * 24));
  if (days >= 1) return `${days}d ago`;
  return "Today";
}

const SearchIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
  </svg>
);

const ChevronIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
  </svg>
);

const XIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

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

  useEffect(() => { load(); }, []);

  const totalFlags   = patients.reduce((s, p) => s + p.open_flag_count, 0);
  const withFlags    = patients.filter((p) => p.open_flag_count > 0).length;

  return (
    <div className="min-h-screen flex flex-col bg-nhs-pale">
      {/* ── NHS top bar ──────────────────────────────────────── */}
      <header className="bg-nhs-blue text-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="border-2 border-white text-white text-xs font-bold px-1.5 py-0.5 leading-none tracking-widest">
              NHS
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">Clinical Document Intelligence</h1>
              <p className="text-xs text-white/70 mt-0.5">Administrative document structuring · For clinical review only</p>
            </div>
          </div>
          <div className="text-xs text-white/60">
            {new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </div>
        </div>
      </header>

      {/* ── Summary strip ────────────────────────────────────── */}
      {!loading && !error && patients.length > 0 && (
        <div className="bg-nhs-blue/10 border-b border-nhs-blue/20">
          <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-6">
            <SummaryChip value={patients.length} label="patients loaded" />
            <div className="w-px h-4 bg-slate-300" />
            <SummaryChip
              value={withFlags}
              label="with open flags"
              highlight={withFlags > 0}
            />
            <div className="w-px h-4 bg-slate-300" />
            <SummaryChip
              value={totalFlags}
              label="total open flags"
              highlight={totalFlags > 0}
            />
          </div>
        </div>
      )}

      {/* ── Main content ─────────────────────────────────────── */}
      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">

          {/* Search + Add */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
                <SearchIcon />
              </span>
              <input
                type="text"
                placeholder="Search by name or NHS number…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && load(search)}
                className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
              />
            </div>
            <button
              onClick={() => load(search)}
              className="px-4 py-2.5 rounded-lg bg-nhs-warm-grey text-white text-sm hover:bg-[#354550] transition-colors"
            >
              Search
            </button>
            <button
              onClick={() => setShowForm(!showForm)}
              className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                showForm
                  ? "bg-slate-200 text-slate-700 hover:bg-slate-300"
                  : "bg-nhs-blue text-white hover:bg-nhs-blue-dark"
              }`}
            >
              {showForm ? (
                <span className="flex items-center gap-1.5"><XIcon /> Cancel</span>
              ) : (
                "+ Add patient"
              )}
            </button>
          </div>

          {/* Add patient form */}
          {showForm && (
            <NewPatientForm onCreated={() => { setShowForm(false); load(); }} />
          )}

          {/* Patient list */}
          <section className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 text-sm">
                {search ? `Results for "${search}"` : "All patients"}
              </h2>
              {!loading && (
                <span className="text-xs text-slate-400">{patients.length} record{patients.length !== 1 ? "s" : ""}</span>
              )}
            </div>

            {loading && (
              <div className="p-8 text-center text-sm text-slate-400">Loading patients…</div>
            )}
            {error && (
              <div className="p-6 text-sm text-nhs-red bg-nhs-red-light border-t border-nhs-red/20">
                {error}
              </div>
            )}
            {!loading && !error && patients.length === 0 && (
              <div className="p-8 text-center text-sm text-slate-400">
                {search ? "No patients match that search." : "No patients yet. Add one above."}
              </div>
            )}

            <ul className="divide-y divide-slate-100">
              {patients.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/patients/${p.id}`}
                    className="flex items-center gap-4 px-5 py-4 hover:bg-nhs-pale transition-colors group"
                  >
                    {/* Risk dot */}
                    <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      p.open_flag_count > 0 ? "bg-nhs-red" : "bg-nhs-green"
                    }`} />

                    {/* Patient info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-slate-900 text-sm group-hover:text-nhs-blue transition-colors">
                        {p.name}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {p.sex} · DOB {p.dob} · NHS {p.nhs_number}
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-4 shrink-0">
                      <div className="text-right">
                        <div className="text-xs text-slate-500">{p.document_count} doc{p.document_count !== 1 ? "s" : ""}</div>
                        {p.open_flag_count > 0 ? (
                          <div className="text-xs font-semibold text-nhs-red mt-0.5">
                            {p.open_flag_count} flag{p.open_flag_count !== 1 ? "s" : ""}
                          </div>
                        ) : (
                          <div className="text-xs text-nhs-green font-medium mt-0.5">No flags</div>
                        )}
                      </div>
                      <div className="text-xs text-slate-400 w-16 text-right">
                        {timeAgo(p.last_updated)}
                      </div>
                      <span className="text-slate-300 group-hover:text-nhs-blue transition-colors">
                        <ChevronIcon />
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <p className="text-center text-xs text-slate-400">
            For administrative use only · outputs do not constitute clinical advice
          </p>
        </div>
      </main>
    </div>
  );
}

/* ── Summary chip ───────────────────────────────────────────── */
function SummaryChip({ value, label, highlight }: { value: number; label: string; highlight?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-sm font-bold ${highlight ? "text-nhs-red" : "text-nhs-blue"}`}>
        {value}
      </span>
      <span className="text-xs text-slate-600">{label}</span>
    </div>
  );
}

/* ── New patient form ───────────────────────────────────────── */
function NewPatientForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<NewPatient>({ name: "", dob: "", nhs_number: "", sex: "M" });
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
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm grid grid-cols-2 gap-3">
      <input placeholder="Full name" value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue" />
      <input type="date" value={form.dob}
        onChange={(e) => setForm({ ...form, dob: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue" />
      <input placeholder="NHS number (e.g. 485 621 3847)" value={form.nhs_number}
        onChange={(e) => setForm({ ...form, nhs_number: e.target.value })}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-nhs-blue" />
      <select value={form.sex}
        onChange={(e) => setForm({ ...form, sex: e.target.value as NewPatient["sex"] })}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue">
        <option>M</option><option>F</option><option>Other</option>
      </select>
      {error && <div className="col-span-2 text-sm text-nhs-red">{error}</div>}
      <button onClick={submit} disabled={busy || !form.name || !form.dob || !form.nhs_number}
        className="col-span-2 px-4 py-2.5 rounded-lg bg-nhs-blue text-white text-sm font-medium hover:bg-nhs-blue-dark disabled:bg-slate-300 transition-colors">
        {busy ? "Creating…" : "Create patient"}
      </button>
    </div>
  );
}
