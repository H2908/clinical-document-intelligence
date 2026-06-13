from pathlib import Path

content = r'''"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, Contradiction } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

export default function ContradictionsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getContradictions(patientId)
      .then((d) => {
        if (!cancelled) {
          setContradictions(d.contradictions);
          setCount(d.count);
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

  // Sort by severity desc, then by created_at desc
  const sorted = [...contradictions].sort((a, b) => {
    const sev = (x: string) => (x === "HIGH" ? 0 : x === "MEDIUM" ? 1 : 2);
    if (sev(a.severity) !== sev(b.severity)) return sev(a.severity) - sev(b.severity);
    return b.created_at.localeCompare(a.created_at);
  });

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Cross-document contradictions</h1>
          <p className="text-sm text-slate-500 mt-1">
            {count} contradiction{count === 1 ? "" : "s"} detected across the patient&apos;s documents.
          </p>
        </header>

        {loading && <div className="text-slate-500">Loading contradictions...</div>}
        {error && <div className="text-red-600">Error: {error}</div>}

        {!loading && !error && sorted.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
            No contradictions detected. The contradiction agent returns [] when documents don&apos;t disagree.
          </div>
        )}

        {!loading && !error && sorted.length > 0 && (
          <ul className="space-y-4">
            {sorted.map((c) => (
              <li key={c.contradiction_id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <header className="px-5 py-3 border-b border-slate-200 flex items-center gap-3">
                  <SeverityBadge severity={c.severity} />
                  <span className="inline-block px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-xs">
                    {c.category}
                  </span>
                  <span className="text-xs text-slate-500 ml-auto">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                  {c.status === "resolved" && (
                    <span className="inline-block px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs">
                      resolved
                    </span>
                  )}
                </header>

                <div className="px-5 py-4 grid grid-cols-2 gap-4 border-b border-slate-200">
                  <div>
                    <div className="text-xs font-mono text-slate-400 mb-1">{c.doc_a_id}</div>
                    <div className="text-sm text-slate-900">{c.doc_a_statement}</div>
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400 mb-1">{c.doc_b_id}</div>
                    <div className="text-sm text-slate-900">{c.doc_b_statement}</div>
                  </div>
                </div>

                <div className="px-5 py-3 bg-amber-50 border-t border-amber-100">
                  <div className="text-xs font-medium text-amber-900 mb-1">Why these disagree</div>
                  <div className="text-sm text-amber-900">{c.explanation}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
'''

target = Path("frontend/app/patients/[id]/contradictions/page.tsx")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8", newline="\n")
print(f"Wrote {target}")
print(f"Lines: {len(content.splitlines())}")
print(f"First 3 bytes: {open(target, 'rb').read(3).hex()}")