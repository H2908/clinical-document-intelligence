const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail?.error?.message || `Request failed: ${res.status}`);
  }
  return res.json();
}

export type PatientCard = {
  id: string;
  name: string;
  dob: string;
  nhs_number: string;
  sex: string;
  document_count: number;
  open_flag_count: number;
  last_updated: string;
};

export type Condition = {
  name: string;
  icd10_code: string | null;
  source_document_id?: string;
};

export type Medication = {
  last_prescribed?: string | null;
  drug: string;
  dose?: string;
  started?: string | null;
  flag?: string | null;
  normalised?: string;
  source_document_id?: string;
};

export type Flag = {
  flag_id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  description: string;
  source_document_id: string;
  status: "open" | "resolved";
  created_at: string;
  resolved_at?: string | null;
};

export type Contradiction = {
  contradiction_id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  doc_a_id: string;
  doc_a_statement: string;
  doc_b_id: string;
  doc_b_statement: string;
  explanation: string;
  status: "open" | "resolved";
  created_at: string;
};

export type TimelineEvent = {
  event_id: string;
  event_date: string | null;
  event_type: string;
  title: string;
  icd10_code: string | null;
  source_document_id: string;
  created_at: string;
};

export type Observation = {
  observation_id: string;
  test: string;
  value: string;
  unit: string;
  observation_date: string;
  source_document_id: string;
  created_at: string;
};

export type Note = {
  document_id: string;
  doc_type: string;
  document_date: string;
  source: string | null;
  status: string;
  extracted_text: string;
  created_at: string;
};

export type BriefingSummary = {
  patient: {
    id: string;
    name: string;
    dob: string;
    nhs_number: string;
    sex: string;
  };
  conditions: Condition[];
  medications: Medication[];
  open_flags: Array<{
    severity: "HIGH" | "MEDIUM" | "LOW";
    category: string;
    description: string;
    source_document_id?: string;
  }>;
};

export type BriefingResponse = {
  patient_id: string;
  available: boolean;
  generated_at?: string;
  is_stale?: boolean;
  disclaimer?: string;
  summary?: BriefingSummary;
  message?: string;
};


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

export type PatientOverview = PatientCard & {
  age: number;
  stats: {
    document_count: number;
    open_flag_count: number;
    contradiction_count: number;
  };
  conditions: Condition[];
  medications: Medication[];
  top_flags: Flag[];
};

export type NewPatient = {
  name: string;
  dob: string;
  nhs_number: string;
  sex: "M" | "F" | "Other";
};

export type DocumentRow = {
  id: string;
  name: string;
  type: string;
  source: string;
  date: string;
  status: string;
};

export const api = {
  listPatients: (search?: string) =>
    request<{ patients: PatientCard[] }>(
      `/patients${search ? `?search=${encodeURIComponent(search)}` : ""}`
    ),
  getPatient: (id: string) => request<PatientOverview>(`/patients/${id}`),
  createPatient: (body: NewPatient) =>
    request<PatientCard>("/patients", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deletePatient: (id: string) =>
    request<{ deleted: boolean; patient_id: string }>(`/patients/${id}`, { method: "DELETE" }),

  getBriefing: (id: string) =>
    request<BriefingResponse>(`/patients/${id}/briefing`),

  getFlags: (id: string, status?: "open" | "resolved") =>
    request<{ patient_id: string; open_count: number; resolved_count: number; flags: Flag[] }>(
      `/patients/${id}/flags${status ? `?status=${status}` : ""}`
    ),

  getContradictions: (id: string) =>
    request<{ patient_id: string; count: number; contradictions: Contradiction[] }>(
      `/patients/${id}/contradictions`
    ),

  getTimeline: (id: string, eventType?: string, limit = 200) => {
    const qs = new URLSearchParams();
    if (eventType) qs.set("event_type", eventType);
    qs.set("limit", String(limit));
    return request<{ patient_id: string; count: number; events: TimelineEvent[] }>(
      `/patients/${id}/timeline?${qs.toString()}`
    );
  },

  getObservations: (id: string) =>
    request<{ patient_id: string; count: number; observations: Observation[] }>(
      `/patients/${id}/labs`
    ),

  getNotes: (id: string) =>
    request<{ patient_id: string; count: number; notes: Note[] }>(
      `/patients/${id}/notes`
    ),

  postNote: (id: string, body: { text: string; document_date: string; source?: string | null }) =>
    request<{ document_id: string; job_id: string; status: string; entity_count: number; message: string }>(
      `/patients/${id}/notes`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  listDocuments: (id: string) =>
    request<{ documents: DocumentRow[] }>(`/patients/${id}/documents`),

  uploadDocument: async (
    id: string,
    args: { file: File; type: string; document_date: string; source?: string }
  ) => {
    const form = new FormData();
    form.append("file", args.file);
    form.append("type", args.type);
    form.append("document_date", args.document_date);
    if (args.source) form.append("source", args.source);
    const res = await fetch(`${API_URL}/patients/${id}/documents`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail?.error?.message || body?.error?.message || `Upload failed: ${res.status}`);
    }
    return res.json() as Promise<{
      document_id: string;
      job_id: string;
      status: "queued";
      message: string;
    }>;
  },

  uploadLab: async (
    id: string,
    args: { file: File; document_date: string; source?: string }
  ) => {
    const form = new FormData();
    form.append("file", args.file);
    form.append("document_date", args.document_date);
    if (args.source) form.append("source", args.source);
    const res = await fetch(`${API_URL}/patients/${id}/labs`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail?.error?.message || body?.error?.message || `Lab upload failed: ${res.status}`);
    }
    return res.json() as Promise<{
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
};
