"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api, TimelineEvent } from "@/lib/api";
import ImageViewer from "@/components/ImageViewer";

const FILTERS = [
  { label: "All",         value: "all" },
  { label: "Diagnoses",   value: "Diagnosis" },
  { label: "Medications", value: "Medication" },
  { label: "Conflicts",   value: "Conflict" },
  { label: "Documents",   value: "Document" },
];

function dotColor(type: string): string {
  switch (type) {
    case "Diagnosis":  return "bg-blue-600";
    case "Medication": return "bg-green-500";
    case "Conflict":   return "bg-red-500";
    case "Document":   return "bg-slate-400";
    default:           return "bg-slate-400";
  }
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return d;
  }
}

const FunnelIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
  </svg>
);

const DocIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
  </svg>
);

type ViewingDoc = { id: string; name: string };

export default function TimelinePage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewingDoc, setViewingDoc] = useState<ViewingDoc | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getTimeline(patientId, filter === "all" ? undefined : filter, 500)
      .then((d) => { if (!cancelled) { setEvents(d.events); setError(null); } })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [patientId, filter]);

  const sorted = useMemo(() => {
    return [...events].sort((a, b) => (b.event_date ?? "").localeCompare(a.event_date ?? ""));
  }, [events]);

  return (
    <main className="p-8">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Clinical timeline</h1>
          <p className="text-sm text-slate-500 mt-1">
            Events extracted from clinical documents, newest first.
          </p>
        </header>

        {/* Filter pill bar */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-slate-400 flex items-center"><FunnelIcon /></span>
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3.5 py-1 rounded-full text-sm transition-colors ${
                filter === f.value
                  ? "bg-slate-800 text-white font-medium"
                  : "border border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading && <p className="text-sm text-slate-500">Loading timeline...</p>}
        {error && <p className="text-sm text-red-600">Error: {error}</p>}
        {!loading && !error && sorted.length === 0 && (
          <p className="text-sm text-slate-500">No events for this filter.</p>
        )}

        {/* Event list */}
        <div className="space-y-3">
          {sorted.map((e) => (
            <div key={e.event_id} className="flex items-start gap-4">
              {/* Colored dot */}
              <div className="pt-5 shrink-0">
                <div className={`w-3 h-3 rounded-full ${dotColor(e.event_type)}`} />
              </div>

              {/* Card */}
              <div className="flex-1 bg-white rounded-xl border border-slate-200 px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  {e.event_date && (
                    <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-0.5 rounded-full font-medium">
                      {fmtDate(e.event_date)}
                    </span>
                  )}
                  <span className="text-xs text-slate-500">{e.event_type}</span>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-900">{e.title}</span>
                  {e.icd10_code && (
                    <span className="text-xs font-mono font-semibold bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                      {e.icd10_code}
                    </span>
                  )}
                </div>

                {e.source_document_id && (
                  <button
                    onClick={() => setViewingDoc({ id: e.source_document_id, name: e.source_document_id })}
                    className="flex items-center gap-1.5 mt-2 text-xs text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    <DocIcon />
                    {e.source_document_id}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <ImageViewer
        documentId={viewingDoc?.id ?? null}
        documentName={viewingDoc?.name ?? null}
        onClose={() => setViewingDoc(null)}
      />
    </main>
  );
}
