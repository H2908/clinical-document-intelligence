"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, DocumentRow } from "@/lib/api";
import ImageViewer from "@/components/ImageViewer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

type TabKey = "document" | "lab" | "note";

const DOC_TYPES = [
  { value: "clinic_letter",     label: "Clinic letter" },
  { value: "referral",          label: "GP referral" },
  { value: "discharge_summary", label: "Discharge summary" },
  { value: "gp_note",           label: "GP note" },
  { value: "imaging",           label: "Imaging report" },
];

function fmtDate(d: string): string {
  try {
    return new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch { return d; }
}

export default function DocumentsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [tab, setTab] = useState<TabKey>("document");
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<DocumentRow | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const loadDocs = async () => {
    if (!patientId) return;
    setLoadingDocs(true);
    setListError(null);
    try {
      const data = await api.listDocuments(patientId);
      setDocs(data.documents);
    } catch (e) {
      setListError((e as Error).message);
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => { loadDocs(); }, [patientId]);

  const handleDelete = async (doc: DocumentRow, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = window.confirm(
      `Delete "${doc.name}"?\n\nThis removes the document, its extracted entities, ` +
      `observations, and any flags/contradictions/timeline events that cite it. ` +
      `Agents will re-run in the background on the remaining documents.\n\nThis action cannot be undone.`
    );
    if (!ok) return;
    setDeleting(doc.id);
    try {
      const res = await fetch(`${API_URL}/documents/${doc.id}`, { method: "DELETE", cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail?.error?.message || `Delete failed: ${res.status}`);
      }
      const body = await res.json();
      await loadDocs(); // document is already deleted server-side
      // Poll the regen job in background without blocking the UI
      if (body.regen_job_id) {
        api.pollJob(body.regen_job_id).then(
          (job) => {
            if (job.status === "completed") {
              loadDocs(); // refresh once agents complete - flags/timeline may have changed
            }
          },
          () => { /* swallow - delete itself succeeded */ }
        );
      }
    } catch (err) {
      alert(`Delete failed: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
          <p className="text-sm text-slate-500 mt-1">Upload a PDF, a lab report, or type a clinician note.</p>
        </header>

        {/* Upload card with tabs */}
        <section className="bg-white rounded-xl border border-slate-200">
          <div className="flex border-b border-slate-200">
            <TabBtn active={tab === "document"} onClick={() => setTab("document")}>Document</TabBtn>
            <TabBtn active={tab === "lab"}      onClick={() => setTab("lab")}>Lab report</TabBtn>
            <TabBtn active={tab === "note"}     onClick={() => setTab("note")}>Clinician note</TabBtn>
          </div>
          <div className="p-5">
            {tab === "document" && <DocumentUpload patientId={patientId} onUploaded={loadDocs} />}
            {tab === "lab"      && <LabUpload      patientId={patientId} onUploaded={loadDocs} />}
            {tab === "note"     && <NoteCompose    patientId={patientId} onUploaded={loadDocs} />}
          </div>
        </section>

        {/* Document list */}
        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Patient documents ({docs.length})</h2>
          </header>
          {loadingDocs && <div className="p-5 text-sm text-slate-500">Loading documents...</div>}
          {listError  && <div className="p-5 text-sm text-red-600">Error: {listError}</div>}
          {!loadingDocs && !listError && docs.length === 0 && (
            <div className="p-5 text-sm text-slate-500">No documents yet. Upload one above.</div>
          )}
          {!loadingDocs && docs.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {docs.map((d) => {
                const isNote     = d.type === "clinician_note";
                const isDeleting = deleting === d.id;
                return (
                  <li
                    key={d.id}
                    onClick={() => { if (!isNote && !isDeleting) setViewing(d); }}
                    className={`px-5 py-3 flex items-center justify-between gap-4 ${
                      isDeleting ? "opacity-50" : isNote ? "" : "hover:bg-slate-50 cursor-pointer"
                    }`}
                    title={isNote ? "Typed notes have no underlying file" : "Click to preview"}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-slate-900 truncate">{d.name}</div>
                      <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
                        <span>{d.type}</span>
                        {d.source && <span>· {d.source}</span>}
                        <span>· {fmtDate(d.date)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        d.status === "processed"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700"
                      }`}>
                        {d.status}
                      </span>
                      <button
                        onClick={(e) => handleDelete(d, e)}
                        disabled={isDeleting}
                        className="w-8 h-8 rounded-full text-slate-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Delete document"
                        aria-label={`Delete ${d.name}`}
                      >
                        {isDeleting ? (
                          <span className="text-xs">...</span>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" /><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>

      <ImageViewer
        documentId={viewing?.id ?? null}
        documentName={viewing?.name ?? null}
        documentType={viewing?.type ?? null}
        onClose={() => setViewing(null)}
      />
    </main>
  );
}

/* ── Shared helpers ─────────────────────────────────────── */

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-3 text-sm border-b-2 -mb-px transition-colors whitespace-nowrap ${
        active ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-slate-600 hover:text-slate-900"
      }`}
    >
      {children}
    </button>
  );
}

function StatusMsg({ busy, busyMessage, error, message }: { busy: boolean; busyMessage?: string | null; error: string | null; message: string | null }) {
  if (busy)    return <p className="text-sm text-slate-500">{busyMessage ?? "Working…"}</p>;
  if (error)   return <p className="text-sm text-red-600">{error}</p>;
  if (message) return <p className="text-sm text-emerald-700">{message}</p>;
  return null;
}

function DocumentUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile]     = useState<File | null>(null);
  const [type, setType]     = useState("clinic_letter");
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [busyMsg, setBusyMsg] = useState<string | null>(null);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMsg(null);
    setBusyMsg("Uploading to S3…");
    try {
      const res = await api.uploadDocument(patientId, { file, type, document_date: date, source: source || undefined });
      setBusyMsg("Document received. Processing in background (NLP + agents, 30–90 s)…");
      setFile(null);
      onUploaded(); // document list refreshes immediately; status will show 'pending'

      const finalJob = await api.pollJob(res.job_id, {
        onProgress: (job) => {
          if (job.status === "running") setBusyMsg("Running NLP and agent pipeline…");
        },
      });

      if (finalJob.status === "failed") {
        setError(finalJob.error || "Processing failed");
      } else {
        setMsg(finalJob.result?.message || "Document processed.");
        onUploaded(); // refresh again to show processed status
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setBusyMsg(null); }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <select value={type} onChange={(e) => setType(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm">
        {DOC_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source (optional, e.g. EMIS Web)" value={source} onChange={(e) => setSource(e.target.value)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working…" : "Upload document"}
      </button>
    </div>
  );
}

function LabUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile]     = useState<File | null>(null);
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [busyMsg, setBusyMsg] = useState<string | null>(null);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMsg(null);
    setBusyMsg("Uploading lab report…");
    try {
      const res = await api.uploadLab(patientId, { file, document_date: date, source: source || undefined });
      setBusyMsg("Lab received. Extracting observations + running agents (30–90 s)…");
      setFile(null);
      onUploaded();

      const finalJob = await api.pollJob(res.job_id, {
        onProgress: (job) => {
          if (job.status === "running") setBusyMsg("Parsing lab values, extracting entities, running agents…");
        },
      });

      if (finalJob.status === "failed") {
        setError(finalJob.error || "Lab processing failed");
      } else {
        setMsg(finalJob.result?.message || "Lab processed.");
        onUploaded();
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setBusyMsg(null); }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <input type="file" accept=".pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source (optional)" value={source} onChange={(e) => setSource(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working…" : "Upload lab report"}
      </button>
    </div>
  );
}

function NoteCompose({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [text, setText]     = useState("");
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [busyMsg, setBusyMsg] = useState<string | null>(null);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    const cleaned = text.trim();
    if (!cleaned) return;
    setBusy(true); setError(null); setMsg(null);
    setBusyMsg("Saving note + extracting entities…");
    try {
      const res = await api.postNote(patientId, { text: cleaned, document_date: date, source: source || null });
      setText("");
      onUploaded();

      // Note saves and extracts entities synchronously; agents run in background
      if (res.job_id) {
        setBusyMsg(`Note saved (${res.entity_count} entities). Agents running in background…`);
        const finalJob = await api.pollJob(res.job_id, {
          onProgress: (job) => {
            if (job.status === "running") setBusyMsg(`Agents running on ${res.entity_count} entities…`);
          },
        });
        if (finalJob.status === "failed") {
          setError(finalJob.error || "Agent processing failed");
        } else {
          setMsg(finalJob.result?.message || `Note saved with ${res.entity_count} entities.`);
          onUploaded();
        }
      } else {
        setMsg(res.message);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setBusyMsg(null); }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <textarea placeholder="Type the clinician note here. Plain text. Include condition list, medications, observations, plan."
        value={text} onChange={(e) => setText(e.target.value)} rows={8}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono" />
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source label (optional)" value={source} onChange={(e) => setSource(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!text.trim() || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working…" : "Save note"}
      </button>
    </div>
  );
}
