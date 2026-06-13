"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, DocumentRow } from "@/lib/api";

type TabKey = "document" | "lab" | "note";

const DOC_TYPES = [
  { value: "clinic_letter",     label: "Clinic letter" },
  { value: "referral",          label: "GP referral" },
  { value: "discharge_summary", label: "Discharge summary" },
  { value: "gp_note",           label: "GP note" },
  { value: "imaging",           label: "Imaging report" },
];

export default function DocumentsPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id ?? "";

  const [tab, setTab] = useState<TabKey>("document");
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

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

  useEffect(() => {
    loadDocs();
  }, [patientId]);

  return (
    <main className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
          <p className="text-sm text-slate-500 mt-1">
            Upload a PDF, a lab report, or type a clinician note.
          </p>
        </header>

        <section className="bg-white rounded-xl border border-slate-200">
          <div className="flex border-b border-slate-200">
            <TabBtn active={tab === "document"} onClick={() => setTab("document")}>Document</TabBtn>
            <TabBtn active={tab === "lab"} onClick={() => setTab("lab")}>Lab report</TabBtn>
            <TabBtn active={tab === "note"} onClick={() => setTab("note")}>Clinician note</TabBtn>
          </div>

          <div className="p-5">
            {tab === "document" && <DocumentUpload patientId={patientId} onUploaded={loadDocs} />}
            {tab === "lab"      && <LabUpload      patientId={patientId} onUploaded={loadDocs} />}
            {tab === "note"     && <NoteCompose    patientId={patientId} onUploaded={loadDocs} />}
          </div>
        </section>

        <section className="bg-white rounded-xl border border-slate-200">
          <header className="px-5 py-3 border-b border-slate-200">
            <h2 className="font-medium text-slate-900">Patient documents ({docs.length})</h2>
          </header>
          {loadingDocs && <div className="p-5 text-sm text-slate-500">Loading documents...</div>}
          {listError && <div className="p-5 text-sm text-red-600">Error: {listError}</div>}
          {!loadingDocs && !listError && docs.length === 0 && (
            <div className="p-5 text-sm text-slate-500">No documents yet. Upload one above.</div>
          )}
          {!loadingDocs && docs.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {docs.map((d) => (
                <li key={d.id} className="px-5 py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm text-slate-900 truncate">{d.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {d.type} - {d.source || "-"} - {d.date}
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      d.status === "processed"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {d.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-3 text-sm border-b-2 -mb-px transition-colors ${
        active ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-slate-600 hover:text-slate-900"
      }`}
    >
      {children}
    </button>
  );
}

function Status({ busy, error, message }: { busy: boolean; error: string | null; message: string | null }) {
  if (busy)   return <p className="text-sm text-slate-500">Processing... NLP + agents run synchronously; this can take 30-60s.</p>;
  if (error)  return <p className="text-sm text-red-600">{error}</p>;
  if (message) return <p className="text-sm text-emerald-700">{message}</p>;
  return null;
}

function DocumentUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState("clinic_letter");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const res = await api.uploadDocument(patientId, {
        file, type, document_date: date, source: source || undefined,
      });
      setMessage(res.message);
      setFile(null);
      onUploaded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <input type="file" accept=".pdf,.png,.jpg,.jpeg"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <select value={type} onChange={(e) => setType(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm">
        {DOC_TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}
      </select>
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source (optional, e.g. EMIS Web)" value={source}
        onChange={(e) => setSource(e.target.value)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><Status busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300">
        {busy ? "Uploading..." : "Upload document"}
      </button>
    </div>
  );
}

function LabUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const res = await api.uploadLab(patientId, {
        file, document_date: date, source: source || undefined,
      });
      setMessage(res.message);
      setFile(null);
      onUploaded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <input type="file" accept=".pdf"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source (optional, e.g. Lab Reports Portal)" value={source}
        onChange={(e) => setSource(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><Status busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300">
        {busy ? "Uploading..." : "Upload lab report"}
      </button>
    </div>
  );
}

function NoteCompose({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [text, setText] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async () => {
    const cleaned = text.trim();
    if (!cleaned) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const res = await api.postNote(patientId, {
        text: cleaned, document_date: date, source: source || null,
      });
      setMessage(res.message);
      setText("");
      onUploaded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      <textarea placeholder="Type the clinician note here. Plain text. Include condition list, medications, observations, plan." value={text}
        onChange={(e) => setText(e.target.value)} rows={8}
        className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono" />
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <input placeholder="Source label (optional)" value={source}
        onChange={(e) => setSource(e.target.value)}
        className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
      <div className="col-span-2"><Status busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!text.trim() || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300">
        {busy ? "Saving..." : "Save note"}
      </button>
    </div>
  );
}
