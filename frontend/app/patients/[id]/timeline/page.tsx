"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api, TimelineEvent } from "@/lib/api";

const EVENT_TYPES = ["all", "diagnosis", "medication", "investigation", "procedure", "encounter"];

export default function TimelinePage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getTimeline(patientId, filter === "all" ? undefined : filter)
      .then((d) => {
        if (!cancelled) {
          setEvents(d.events);
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

  // Group by year for visual structure
  const grouped = useMemo(() => {
    const out: Record<string, TimelineEvent[]> = {};
    for (const e of events) {
      const year = e.event_date ? e.event_date.slice(0, 4) : "Undated";
      out[year] = out[year] || [];
      out[year].push(e);
    }
    return out;
  }, [events]);

  const years = Object.keys(grouped).sort((a, b) => (a === "Undated" ? 1 : b === "Undated" ? -1 : b.localeCompare(a)));

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Timeline</h1>
            <p className="text-sm text-slate-500 mt-1">
              {events.length} event{events.length === 1 ? "" : "s"} across the patient&apos;s documents.
            </p>
          </div>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>{t === "all" ? "All event types" : t}</option>
            ))}
          </select>
        </header>

        {loading && <div className="text-slate-500">Loading timeline...</div>}
        {error && <div className="text-red-600">Error: {error}</div>}

        {!loading && !error && events.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
            No events for this filter.
          </div>
        )}

        {!loading && !error && events.length > 0 && (
          <div className="space-y-8">
            {years.map((year) => (
              <section key={year}>
                <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">
                  {year}
                </h2>
                <ul className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
                  {grouped[year].map((e) => (
                    <li key={e.event_id} className="px-5 py-4 flex items-start gap-4">
                      <div className="text-xs font-mono text-slate-500 w-24 shrink-0 pt-0.5">
                        {e.event_date || "-"}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-slate-900">{e.title}</div>
                        <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                          <span className="inline-block px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                            {e.event_type}
                          </span>
                          {e.icd10_code && (
                            <span className="font-mono">{e.icd10_code}</span>
                          )}
                          <span className="font-mono text-slate-400">{e.source_document_id}</span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
