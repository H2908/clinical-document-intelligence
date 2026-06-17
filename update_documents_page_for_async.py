"""Update frontend/app/patients/[id]/documents/page.tsx for async backend.

Three upload components (DocumentUpload, LabUpload, NoteCompose) now:
  1. Call upload, get back job_id
  2. Show 'Processing in background...' message
  3. Poll the job via api.pollJob with onProgress callback
  4. Show final message when job completes (or error if failed)
  5. Call onUploaded() to refresh document list on success

Delete handler:
  1. Returns immediately with regen_job_id from the response
  2. Refreshes doc list (document is already deleted server-side)
  3. Polls regen job in background, shows toast on completion

Atomic anchored replacement.
"""
from pathlib import Path
import re

p = Path("frontend/app/patients/[id]/documents/page.tsx")
src = p.read_text(encoding="utf-8")

# ============================================================================
# 1. Update StatusMsg to handle a wider range of states
# ============================================================================
old_status_msg = '''function StatusMsg({ busy, error, message }: { busy: boolean; error: string | null; message: string | null }) {
  if (busy)    return <p className="text-sm text-slate-500">Processing\u2026 NLP + agents run synchronously; this can take 30\u201360 s.</p>;
  if (error)   return <p className="text-sm text-red-600">{error}</p>;
  if (message) return <p className="text-sm text-emerald-700">{message}</p>;
  return null;
}'''

new_status_msg = '''function StatusMsg({ busy, busyMessage, error, message }: { busy: boolean; busyMessage?: string | null; error: string | null; message: string | null }) {
  if (busy)    return <p className="text-sm text-slate-500">{busyMessage ?? "Working\u2026"}</p>;
  if (error)   return <p className="text-sm text-red-600">{error}</p>;
  if (message) return <p className="text-sm text-emerald-700">{message}</p>;
  return null;
}'''

if old_status_msg not in src:
    print("[FAIL] StatusMsg anchor not found")
    raise SystemExit(1)
src = src.replace(old_status_msg, new_status_msg)

# ============================================================================
# 2. DocumentUpload submit handler - swap synchronous for async-with-polling
# ============================================================================
old_doc_submit = '''function DocumentUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile]     = useState<File | null>(null);
  const [type, setType]     = useState("clinic_letter");
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const res = await api.uploadDocument(patientId, { file, type, document_date: date, source: source || undefined });
      setMsg(res.message); setFile(null); onUploaded();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };'''

new_doc_submit = '''function DocumentUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
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
    setBusyMsg("Uploading to S3\u2026");
    try {
      const res = await api.uploadDocument(patientId, { file, type, document_date: date, source: source || undefined });
      setBusyMsg("Document received. Processing in background (NLP + agents, 30\u201390 s)\u2026");
      setFile(null);
      onUploaded(); // document list refreshes immediately; status will show 'pending'

      const finalJob = await api.pollJob(res.job_id, {
        onProgress: (job) => {
          if (job.status === "running") setBusyMsg("Running NLP and agent pipeline\u2026");
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
  };'''

if old_doc_submit not in src:
    print("[FAIL] DocumentUpload submit anchor not found")
    raise SystemExit(1)
src = src.replace(old_doc_submit, new_doc_submit)

# Update DocumentUpload's StatusMsg call to pass busyMessage
old_doc_status = '''      <div className="col-span-2"><StatusMsg busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Uploading\u2026" : "Upload document"}'''
new_doc_status = '''      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working\u2026" : "Upload document"}'''
if old_doc_status not in src:
    print("[FAIL] DocumentUpload StatusMsg call anchor not found")
    raise SystemExit(1)
src = src.replace(old_doc_status, new_doc_status)

# ============================================================================
# 3. LabUpload submit handler
# ============================================================================
old_lab_submit = '''function LabUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [file, setFile]     = useState<File | null>(null);
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const res = await api.uploadLab(patientId, { file, document_date: date, source: source || undefined });
      setMsg(res.message); setFile(null); onUploaded();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };'''

new_lab_submit = '''function LabUpload({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
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
    setBusyMsg("Uploading lab report\u2026");
    try {
      const res = await api.uploadLab(patientId, { file, document_date: date, source: source || undefined });
      setBusyMsg("Lab received. Extracting observations + running agents (30\u201390 s)\u2026");
      setFile(null);
      onUploaded();

      const finalJob = await api.pollJob(res.job_id, {
        onProgress: (job) => {
          if (job.status === "running") setBusyMsg("Parsing lab values, extracting entities, running agents\u2026");
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
  };'''

if old_lab_submit not in src:
    print("[FAIL] LabUpload submit anchor not found")
    raise SystemExit(1)
src = src.replace(old_lab_submit, new_lab_submit)

old_lab_status = '''      <div className="col-span-2"><StatusMsg busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Uploading\u2026" : "Upload lab report"}'''
new_lab_status = '''      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!file || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working\u2026" : "Upload lab report"}'''
if old_lab_status not in src:
    print("[FAIL] LabUpload StatusMsg call anchor not found")
    raise SystemExit(1)
src = src.replace(old_lab_status, new_lab_status)

# ============================================================================
# 4. NoteCompose submit handler
# ============================================================================
old_note_submit = '''function NoteCompose({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
  const [text, setText]     = useState("");
  const [date, setDate]     = useState(() => new Date().toISOString().slice(0, 10));
  const [source, setSource] = useState("");
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [message, setMsg]   = useState<string | null>(null);

  const submit = async () => {
    const cleaned = text.trim();
    if (!cleaned) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const res = await api.postNote(patientId, { text: cleaned, document_date: date, source: source || null });
      setMsg(res.message); setText(""); onUploaded();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };'''

new_note_submit = '''function NoteCompose({ patientId, onUploaded }: { patientId: string; onUploaded: () => void }) {
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
    setBusyMsg("Saving note + extracting entities\u2026");
    try {
      const res = await api.postNote(patientId, { text: cleaned, document_date: date, source: source || null });
      setText("");
      onUploaded();

      // Note saves and extracts entities synchronously; agents run in background
      if (res.job_id) {
        setBusyMsg(`Note saved (${res.entity_count} entities). Agents running in background\u2026`);
        const finalJob = await api.pollJob(res.job_id, {
          onProgress: (job) => {
            if (job.status === "running") setBusyMsg(`Agents running on ${res.entity_count} entities\u2026`);
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
  };'''

if old_note_submit not in src:
    print("[FAIL] NoteCompose submit anchor not found")
    raise SystemExit(1)
src = src.replace(old_note_submit, new_note_submit)

old_note_status = '''      <div className="col-span-2"><StatusMsg busy={busy} error={error} message={message} /></div>
      <button onClick={submit} disabled={!text.trim() || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Saving\u2026" : "Save note"}'''
new_note_status = '''      <div className="col-span-2"><StatusMsg busy={busy} busyMessage={busyMsg} error={error} message={message} /></div>
      <button onClick={submit} disabled={!text.trim() || busy}
        className="col-span-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-slate-300 transition-colors">
        {busy ? "Working\u2026" : "Save note"}'''
if old_note_status not in src:
    print("[FAIL] NoteCompose StatusMsg call anchor not found")
    raise SystemExit(1)
src = src.replace(old_note_status, new_note_status)

# ============================================================================
# 5. Delete handler - response now carries regen_job_id; poll in background
# ============================================================================
old_delete = '''  const handleDelete = async (doc: DocumentRow, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = window.confirm(
      `Delete "${doc.name}"?\\n\\nThis removes the document, its extracted entities, ` +
      `observations, and any flags/contradictions/timeline events that cite it. ` +
      `Agents will re-run on the remaining documents (takes 10\u201330 seconds).\\n\\nThis action cannot be undone.`
    );
    if (!ok) return;
    setDeleting(doc.id);
    try {
      const res = await fetch(`${API_URL}/documents/${doc.id}`, { method: "DELETE", cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail?.error?.message || `Delete failed: ${res.status}`);
      }
      await loadDocs();
    } catch (err) {
      alert(`Delete failed: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  };'''

new_delete = '''  const handleDelete = async (doc: DocumentRow, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = window.confirm(
      `Delete "${doc.name}"?\\n\\nThis removes the document, its extracted entities, ` +
      `observations, and any flags/contradictions/timeline events that cite it. ` +
      `Agents will re-run in the background on the remaining documents.\\n\\nThis action cannot be undone.`
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
  };'''

if old_delete not in src:
    print("[FAIL] handleDelete anchor not found")
    raise SystemExit(1)
src = src.replace(old_delete, new_delete)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK page.tsx updated")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")