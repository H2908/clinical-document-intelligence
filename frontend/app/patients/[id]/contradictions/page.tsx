"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, Contradiction } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

const sevOrder = (s: string) => (s === "HIGH" ? 0 : s === "MEDIUM" ? 1 : 2);

const WarnIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="15"
    height="15"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="shrink-0 mt-0.5 text-amber-600"
  >
    <path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
  </svg>
);

export default function ContradictionsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getContradictions(patientId)
      .then((d) => { if (!cancelled) { setContradictions(d.contradictions); setError(null); } })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [patientId]);

  const handleResolve = (id: string) => {
    setContradictions((prev) =>
      prev.map((c) => c.contradiction_id === id ? { ...c, status: "resolved" as const } : c)
    );
  };

  const sorted = [...contradictions].sort(
    (a, b) => sevOrder(a.severity) - sevOrder(b.severity) || b.created_at.localeCompare(a.created_at)
  );

  return (
    <main className="p-8">
      <div className="max-w-4xl mx-auto space-y-5">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Contradictions</h1>
          <p className="text-sm text-slate-500 mt-1">
            Conflicting facts found across this patient&apos;s documents.
          </p>
        </header>

        {loading && <p className="text-sm text-slate-500">Loading contradictions...</p>}
        {error && <p className="text-sm text-red-600">Error: {error}</p>}

        {!loading && !error && sorted.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
            No contradictions detected across this patient&apos;s documents.
          </div>
        )}

        {sorted.map((c) => (
          <ContradictionCard
            key={c.contradiction_id}
            c={c}
            onResolve={() => handleResolve(c.contradiction_id)}
            patientId={patientId}
          />
        ))}
      </div>
    </main>
  );
}

function ContradictionCard({
  c,
  onResolve,
  patientId,
}: {
  c: Contradiction;
  onResolve: () => void;
  patientId: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header row */}
      <div className="px-5 py-3 flex items-center gap-2 border-b border-slate-100">
        <SeverityBadge severity={c.severity} />
        <span className="text-xs font-semibold tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded uppercase">
          {c.category.replace(/_/g, " ")}
        </span>
        {c.status === "resolved" && (
          <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
            resolved
          </span>
        )}
        <span className="ml-auto text-xs text-slate-400">Conflicting claim across documents</span>
      </div>

      {/* Two-column document comparison */}
      <div className="grid grid-cols-2 divide-x divide-slate-100">
        <div className="px-5 py-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Document A
          </p>
          <p className="text-xs font-mono text-slate-500 mb-3">{c.doc_a_id}</p>
          <p className="text-sm text-slate-800 leading-relaxed">{c.doc_a_statement}</p>
        </div>
        <div className="px-5 py-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Document B
          </p>
          <p className="text-xs font-mono text-slate-500 mb-3">{c.doc_b_id}</p>
          <p className="text-sm text-slate-800 leading-relaxed">{c.doc_b_statement}</p>
        </div>
      </div>

      {/* Explanation strip */}
      <div className="px-5 py-3 bg-amber-50 border-t border-amber-100 flex items-start gap-2">
        <WarnIcon />
        <p className="text-sm text-amber-900 leading-relaxed">{c.explanation}</p>
      </div>

      {/* Actions */}
      {c.status !== "resolved" && (
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onResolve}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Mark resolved
          </button>
          <button
            onClick={() => { window.location.href = `/patients/${patientId}/documents`; }}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
          >
            View both documents
          </button>
        </div>
      )}
    </div>
  );
}
