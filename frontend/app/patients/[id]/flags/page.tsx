"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, Flag } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";
import ImageViewer from "@/components/ImageViewer";

const ChevronIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M8.25 4.5l7.5 7.5-7.5 7.5" />
  </svg>
);

const DocIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
  </svg>
);

const borderColor = (sev: string) =>
  sev === "HIGH"
    ? "border-l-red-500"
    : sev === "MEDIUM"
    ? "border-l-orange-400"
    : "border-l-yellow-400";

const sevOrder = (s: string) => (s === "HIGH" ? 0 : s === "MEDIUM" ? 1 : 2);

type ViewingDoc = { id: string; name: string };

export default function FlagsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [allFlags, setAllFlags] = useState<Flag[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<ViewingDoc | null>(null);

  const load = () => {
    if (!patientId) return;
    setLoading(true);
    api
      .getFlags(patientId)
      .then((d) => {
        setAllFlags(d.flags);
        setOpenCount(d.open_count);
        setResolvedCount(d.resolved_count);
        setError(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [patientId]);

  const handleResolve = (flagId: string) => {
    setAllFlags((prev) =>
      prev.map((f) => f.flag_id === flagId ? { ...f, status: "resolved" as const } : f)
    );
    setOpenCount((c) => Math.max(0, c - 1));
    setResolvedCount((c) => c + 1);
  };

  const open = allFlags
    .filter((f) => f.status === "open")
    .sort((a, b) => sevOrder(a.severity) - sevOrder(b.severity) || b.created_at.localeCompare(a.created_at));

  const resolved = allFlags
    .filter((f) => f.status === "resolved")
    .sort((a, b) =>
      (b.resolved_at || b.created_at).localeCompare(a.resolved_at || a.created_at)
    );

  return (
    <main className="p-8">
      <div className="max-w-3xl mx-auto space-y-4">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Risk flags</h1>
          <p className="text-sm text-slate-500 mt-1">
            {openCount} open · {resolvedCount} resolved
          </p>
        </header>

        {loading && <p className="text-sm text-slate-500">Loading flags...</p>}
        {error && <p className="text-sm text-red-600">Error: {error}</p>}

        {!loading && !error && open.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
            No open flags.
          </div>
        )}

        {open.map((f) => (
          <FlagCard
            key={f.flag_id}
            flag={f}
            leftBorder={borderColor(f.severity)}
            onViewDoc={(docId) => setViewingDoc({ id: docId, name: docId })}
            onResolve={() => handleResolve(f.flag_id)}
          />
        ))}

        {resolvedCount > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <button
              onClick={() => setShowResolved((v) => !v)}
              className="w-full flex items-center justify-between px-5 py-4 text-sm text-slate-700 hover:bg-slate-50"
            >
              <span>Show resolved ({resolvedCount})</span>
              <ChevronIcon className={`transition-transform ${showResolved ? "rotate-90" : ""}`} />
            </button>
            {showResolved && (
              <div className="border-t border-slate-100 space-y-3 p-4">
                {resolved.map((f) => (
                  <FlagCard
                    key={f.flag_id}
                    flag={f}
                    leftBorder="border-l-slate-300"
                    onViewDoc={(docId) => setViewingDoc({ id: docId, name: docId })}
                    onResolve={() => {}}
                    isResolved
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <ImageViewer
        documentId={viewingDoc?.id ?? null}
        documentName={viewingDoc?.name ?? null}
        onClose={() => setViewingDoc(null)}
      />
    </main>
  );
}

function FlagCard({
  flag,
  leftBorder,
  onViewDoc,
  onResolve,
  isResolved,
}: {
  flag: Flag;
  leftBorder: string;
  onViewDoc: (docId: string) => void;
  onResolve: () => void;
  isResolved?: boolean;
}) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 border-l-4 ${leftBorder}`}>
      <div className="px-5 pt-4 pb-3">
        <div className="flex items-center gap-2 mb-2">
          <SeverityBadge severity={flag.severity} />
          <span className="text-xs font-semibold tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded uppercase">
            {flag.category.replace(/_/g, " ")}
          </span>
          {isResolved && (
            <span className="ml-auto text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
              resolved
            </span>
          )}
        </div>

        <p className="text-sm text-slate-800 leading-relaxed">{flag.description}</p>

        {flag.source_document_id && (
          <button
            onClick={() => onViewDoc(flag.source_document_id)}
            className="flex items-center gap-1.5 mt-2 text-xs text-blue-600 hover:text-blue-800 hover:underline"
          >
            <DocIcon />
            {flag.source_document_id}
          </button>
        )}
      </div>

      {!isResolved && (
        <div className="px-5 pb-4">
          <button
            onClick={onResolve}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Mark resolved
          </button>
        </div>
      )}
    </div>
  );
}
