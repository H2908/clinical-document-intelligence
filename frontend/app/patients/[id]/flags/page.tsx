"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, Flag } from "@/lib/api";

export default function FlagsPage() {
  const { id } = useParams<{ id: string }>();
  const [flags, setFlags] = useState<Flag[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [filter, setFilter] = useState<"all" | "open" | "resolved">("open");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const statusFilter = filter === "all" ? undefined : filter;
    api.getFlags(id, statusFilter)
      .then((res) => {
        setFlags(res.flags);
        setOpenCount(res.open_count);
        setResolvedCount(res.resolved_count);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, filter]);

  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const sevColors: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800 border-l-4 border-red-500",
    MEDIUM: "bg-amber-100 text-amber-800 border-l-4 border-amber-500",
    LOW: "bg-slate-100 text-slate-700 border-l-4 border-slate-400",
  };
  const sevPill: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800",
    MEDIUM: "bg-amber-100 text-amber-800",
    LOW: "bg-slate-100 text-slate-700",
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Risk flags</h1>
        <p className="text-sm text-slate-500 mt-1">
          {openCount} open · {resolvedCount} resolved
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {(["open", "resolved", "all"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
          >
            {f === "open" ? "Open" : f === "resolved" ? "Resolved" : "All"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-slate-500">Loading…</div>
      ) : flags.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
          No {filter === "all" ? "" : filter} flags.
        </div>
      ) : (
        <div className="space-y-3">
          {flags.map((f) => {
            const left = sevColors[f.severity] ?? sevColors.LOW;
            return (
              <article
                key={f.flag_id}
                className={`bg-white rounded-r-lg pl-4 pr-5 py-4 ${left}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium tracking-wide ${
                      sevPill[f.severity] ?? sevPill.LOW
                    }`}
                  >
                    {f.severity}
                  </span>
                  <span className="text-xs font-semibold uppercase text-slate-600 tracking-wide">
                    {f.category.replace(/^AI_/, "").replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-sm text-slate-800">{f.description}</p>
                {f.source_document_id && (
                  <p className="mt-2 text-xs text-blue-600 font-mono">
                    › {f.source_document_id}
                  </p>
                )}
                <div className="mt-3 flex gap-2 text-xs">
                  <button className="px-3 py-1 rounded border border-slate-200 text-slate-700 hover:bg-slate-50">
                    Mark resolved
                  </button>
                  <button className="px-3 py-1 rounded border border-slate-200 text-slate-700 hover:bg-slate-50">
                    View source
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}