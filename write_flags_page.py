from pathlib import Path

content = r'''"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, Flag } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";

type FilterKey = "open" | "resolved" | "all";

export default function FlagsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [filter, setFilter] = useState<FilterKey>("open");
  const [flags, setFlags] = useState<Flag[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    const statusArg = filter === "all" ? undefined : filter;
    api
      .getFlags(patientId, statusArg)
      .then((d) => {
        if (!cancelled) {
          setFlags(d.flags);
          setOpenCount(d.open_count);
          setResolvedCount(d.resolved_count);
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
  }, [patientId, filter]);

  // Sort by severity desc (HIGH first), then by created_at desc
  const sorted = [...flags].sort((a, b) => {
    const sev = (x: string) => (x === "HIGH" ? 0 : x === "MEDIUM" ? 1 : 2);
    if (sev(a.severity) !== sev(b.severity)) return sev(a.severity) - sev(b.severity);
    return b.created_at.localeCompare(a.created_at);
  });

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Risk flags</h1>
          <p className="text-sm text-slate-500 mt-1">
            {openCount} open - {resolvedCount} resolved
          </p>
        </header>

        <div className="flex gap-2">
          <FilterBtn active={filter === "open"} onClick={() => setFilter("open")}>
            Open ({openCount})
          </FilterBtn>
          <FilterBtn active={filter === "resolved"} onClick={() => setFilter("resolved")}>
            Resolved ({resolvedCount})
          </FilterBtn>
          <FilterBtn active={filter === "all"} onClick={() => setFilter("all")}>
            All
          </FilterBtn>
        </div>

        {loading && <div className="text-slate-500">Loading flags...</div>}
        {error && <div className="text-red-600">Error: {error}</div>}

        {!loading && !error && sorted.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
            No flags for this filter.
          </div>
        )}

        {!loading && !error && sorted.length > 0 && (
          <ul className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {sorted.map((f) => (
              <li key={f.flag_id} className="px-5 py-4">
                <div className="flex items-start gap-3">
                  <SeverityBadge severity={f.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-900">{f.description}</div>
                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-2 flex-wrap">
                      <span className="inline-block px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                        {f.category}
                      </span>
                      <span className="font-mono text-slate-400">{f.source_document_id}</span>
                      <span className="text-slate-400">- {new Date(f.created_at).toLocaleDateString()}</span>
                      {f.status === "resolved" && (
                        <span className="inline-block px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
                          resolved
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}

function FilterBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm transition-colors ${
        active
          ? "bg-blue-600 text-white"
          : "bg-white border border-slate-300 text-slate-700 hover:bg-slate-100"
      }`}
    >
      {children}
    </button>
  );
}
'''

target = Path("frontend/app/patients/[id]/flags/page.tsx")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8", newline="\n")
print(f"Wrote {target}")
print(f"Lines: {len(content.splitlines())}")
print(f"First 3 bytes: {open(target, 'rb').read(3).hex()}")