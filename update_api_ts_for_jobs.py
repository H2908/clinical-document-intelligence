"""Update frontend/lib/api.ts for async backend.

Changes:
  1. Add Job type and getJob() / pollJob() helpers.
  2. uploadDocument, uploadLab, postNote now return the queued response
     shape {document_id, job_id, status: "queued", message}. The page-level
     code uses pollJob to wait for completion.

Atomic anchored replacement.
"""
from pathlib import Path

p = Path("frontend/lib/api.ts")
src = p.read_text(encoding="utf-8")

# ---- 1. Add Job type after existing types ----
if "export type Job =" not in src:
    job_type = '''
export type Job = {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  context: Record<string, any>;
  result: Record<string, any> | null;
  error: string | null;
};

'''
    # insert just before "export type PatientOverview"
    anchor = "export type PatientOverview ="
    if anchor not in src:
        print("[FAIL] PatientOverview anchor not found")
        raise SystemExit(1)
    src = src.replace(anchor, job_type + anchor, 1)

# ---- 2. Update uploadDocument return type ----
old_doc_return = '''return res.json() as Promise<{
      document_id: string;
      status: string;
      entity_count: number;
      agent_counts: Record<string, number>;
      message: string;
    }>;
  },

  uploadLab:'''
new_doc_return = '''return res.json() as Promise<{
      document_id: string;
      job_id: string;
      status: "queued";
      message: string;
    }>;
  },

  uploadLab:'''
if old_doc_return not in src:
    print("[FAIL] uploadDocument return-type anchor not found")
    raise SystemExit(1)
src = src.replace(old_doc_return, new_doc_return)

# ---- 3. Update uploadLab return type ----
old_lab_return = '''return res.json() as Promise<{
      document_id: string;
      status: string;
      observation_count: number;
      entity_count: number;
      agent_counts: Record<string, number>;
      message: string;
    }>;
  },
};'''
new_lab_return = '''return res.json() as Promise<{
      document_id: string;
      job_id: string;
      status: "queued";
      doc_type: string;
      message: string;
    }>;
  },

  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),

  pollJob: async (jobId: string, opts?: { intervalMs?: number; timeoutMs?: number; onProgress?: (job: Job) => void }): Promise<Job> => {
    const intervalMs = opts?.intervalMs ?? 2000;
    const timeoutMs = opts?.timeoutMs ?? 5 * 60 * 1000; // 5 minutes
    const start = Date.now();
    while (true) {
      const job = await request<Job>(`/jobs/${jobId}`);
      opts?.onProgress?.(job);
      if (job.status === "completed" || job.status === "failed") return job;
      if (Date.now() - start > timeoutMs) {
        throw new Error(`Job ${jobId} did not finish within ${timeoutMs / 1000}s (last status: ${job.status})`);
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  },
};'''
if old_lab_return not in src:
    print("[FAIL] uploadLab return-type anchor not found")
    raise SystemExit(1)
src = src.replace(old_lab_return, new_lab_return)

# ---- 4. Update postNote return type (in the api.postNote entry) ----
old_note_sig = '''postNote: (id: string, body: { text: string; document_date: string; source?: string | null }) =>
    request<{ document_id: string; status: string; entity_count: number; message: string }>('''
new_note_sig = '''postNote: (id: string, body: { text: string; document_date: string; source?: string | null }) =>
    request<{ document_id: string; job_id: string; status: string; entity_count: number; message: string }>('''
if old_note_sig not in src:
    print("[FAIL] postNote return-type anchor not found")
    raise SystemExit(1)
src = src.replace(old_note_sig, new_note_sig)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK api.ts updated")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")