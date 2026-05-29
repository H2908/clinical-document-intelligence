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

// ---- Types (subset of API_CONTRACT.md — extend as you wire more pages) ----
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

export type Condition = { name: string; icd10_code: string };
export type Medication = {
  drug: string;
  dose: string;
  started: string | null;
  flag: string | null;
};
export type Flag = {
  id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  description: string;
  source_document_id: string;
  source_document_name: string;
  status: "open" | "resolved";
  created_at: string;
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
};