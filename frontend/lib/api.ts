const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ---- Shared types ----
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

// ---- Endpoints ----
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
    request<{ document_id: string; status: string; entity_count: number; message: string }>(
      `/patients/${id}/notes`,
      { method: "POST", body: JSON.stringify(body) }
    ),
};