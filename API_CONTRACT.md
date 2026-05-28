# API Contract — Clinical Document Intelligence

**Status:** v1 (GTV scope)
**Owners:** Frontend + API — *you* · Storage/Warehouse — *partner*
**Rule:** This file is the seam between the two halves of the project. Any change
to a request/response shape is a 2-minute conversation **first**, then both sides
update this file together. No silent changes.

---

## 1. Conventions

| Topic | Decision |
|---|---|
| Base URL | `/api` (e.g. `http://localhost:8000/api`) |
| Format | JSON only. `Content-Type: application/json` except file upload (multipart). |
| Dates | All dates are ISO 8601 strings. Date only: `YYYY-MM-DD`. Timestamps: `YYYY-MM-DDTHH:MM:SSZ` (UTC). |
| IDs | All IDs are strings. Patient: `pat_<uuid>`. Document: `doc_<uuid>`. Flag: `flag_<uuid>`. etc. |
| Auth | Every request sends header `X-API-Key: <key>`. Missing/invalid → `401`. |
| Casing | JSON keys are `snake_case`. |
| Empty lists | Always return `[]`, never `null`. |
| Missing optional values | Return `null`, not omitted. |

### Standard error shape

Every non-2xx response uses this body:

```json
{
  "error": {
    "code": "not_found",
    "message": "Patient pat_123 does not exist."
  }
}
```

| HTTP | `code` values |
|---|---|
| 400 | `bad_request`, `validation_error` |
| 401 | `unauthorized` |
| 404 | `not_found` |
| 409 | `conflict` (e.g. duplicate NHS number) |
| 422 | `unprocessable` |
| 500 | `internal_error` |

---

## 2. Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/patients` | List / search patients (landing page) |
| POST | `/api/patients` | Create a new patient |
| GET | `/api/patients/{id}` | Patient overview (stats, conditions, meds, top flags) |
| GET | `/api/patients/{id}/timeline` | Clinical timeline events |
| GET | `/api/patients/{id}/flags` | Risk flags (open + resolved) |
| GET | `/api/patients/{id}/contradictions` | Cross-document contradictions |
| GET | `/api/patients/{id}/briefing` | Pre-appointment briefing |
| GET | `/api/patients/{id}/documents` | Source document list |
| GET | `/api/documents/{id}` | One document + extracted entities |
| POST | `/api/patients/{id}/documents` | Upload a file (PDF/DOCX/image/lab) |
| POST | `/api/patients/{id}/notes` | Add a free-text clinician note |
| POST | `/api/patients/{id}/labs` | Add lab results (manual entry) |
| PATCH | `/api/flags/{id}` | Mark a flag resolved / open |
| PATCH | `/api/contradictions/{id}` | Mark a contradiction resolved / open |
| DELETE | `/api/patients/{id}` | GDPR delete (cascades) |

---

## 3. Shared object shapes

These objects appear inside multiple responses. Defined once here.

### `patient_summary_card` — used in patient list

```json
{
  "id": "pat_8f3a",
  "name": "Mohammed Al-Rashidi",
  "dob": "1970-03-12",
  "nhs_number": "485 621 3847",
  "sex": "M",
  "document_count": 3,
  "open_flag_count": 3,
  "last_updated": "2024-04-10T09:00:00Z"
}
```

### `condition`

```json
{
  "name": "Dilated cardiomyopathy",
  "icd10_code": "I42.0"
}
```

### `medication`

```json
{
  "drug": "Metformin",
  "dose": "1 g BD",
  "started": "2019-04-10",
  "flag": "eGFR below recommended threshold"
}
```
`flag` is `null` when the medication is not flagged.

### `result` — a lab / observation value

```json
{
  "test": "eGFR",
  "value": "42",
  "unit": "mL/min/1.73m2",
  "date": "2024-04-10",
  "trend": ["58", "49", "42"]
}
```
`trend` is an ordered list (oldest → newest) for sparklines. May be `[]` if only one reading.

### `flag`

```json
{
  "id": "flag_4c1d",
  "severity": "HIGH",
  "category": "ALLERGY CONFLICT",
  "description": "Allergy status conflicts between GP letter (NKDA) and cardiology letter (penicillin allergy). Verify before prescribing antibiotics.",
  "source_document_id": "doc_77ab",
  "source_document_name": "Cardiology_28Feb2024.pdf",
  "status": "open",
  "created_at": "2024-02-28T00:00:00Z"
}
```
`severity` ∈ `HIGH | MEDIUM | LOW`. `status` ∈ `open | resolved`.

### `entity` — a span extracted from a document

```json
{
  "text": "bisoprolol 2.5 mg",
  "type": "Drug",
  "start": 142,
  "end": 159
}
```
`type` ∈ `Diagnosis | Drug | Date | Conflict`. `start`/`end` are character
offsets into the document's `extracted_text`, used for highlighting.

### `timeline_event`

```json
{
  "id": "evt_01",
  "date": "2024-02-28",
  "type": "Diagnosis",
  "title": "Dilated cardiomyopathy diagnosed",
  "icd10_code": "I42.0",
  "source_document_id": "doc_77ab",
  "source_document_name": "Cardiology_28Feb2024.pdf"
}
```
`type` ∈ `Diagnosis | Medication | Flag | Referral | Observation | Lab | Imaging`.
`icd10_code` may be `null`.

---

## 4. Endpoints in detail

### GET /api/patients

List or search patients. Powers the landing page.

**Query params:** `search` (optional, matches name or NHS number).

**200 response:**
```json
{
  "patients": [ /* array of patient_summary_card */ ]
}
```

---

### POST /api/patients

Create a new patient.

**Request body:**
```json
{
  "name": "Daniel Osei",
  "dob": "1991-07-05",
  "nhs_number": "733 908 2210",
  "sex": "M"
}
```
`sex` ∈ `M | F | Other`.

**201 response:** the created `patient_summary_card`.
**409:** NHS number already exists.

---

### GET /api/patients/{id}

Patient overview page.

**200 response:**
```json
{
  "id": "pat_8f3a",
  "name": "Mohammed Al-Rashidi",
  "dob": "1970-03-12",
  "nhs_number": "485 621 3847",
  "sex": "M",
  "age": 54,
  "last_updated": "2024-04-10T09:00:00Z",
  "stats": {
    "document_count": 3,
    "open_flag_count": 3,
    "contradiction_count": 1
  },
  "conditions": [ /* array of condition */ ],
  "medications": [ /* array of medication */ ],
  "top_flags": [ /* array of flag, max 3, highest severity first */ ]
}
```

---

### GET /api/patients/{id}/timeline

**Query params:** `type` (optional filter — one of the `timeline_event.type` values).

**200 response:**
```json
{
  "events": [ /* array of timeline_event, newest first */ ]
}
```

---

### GET /api/patients/{id}/flags

**Query params:** `status` (optional — `open | resolved`).

**200 response:**
```json
{
  "open_count": 3,
  "resolved_count": 1,
  "flags": [ /* array of flag */ ]
}
```

---

### GET /api/patients/{id}/contradictions

**200 response:**
```json
{
  "contradictions": [
    {
      "id": "con_22",
      "severity": "HIGH",
      "category": "ALLERGY",
      "status": "open",
      "document_a": {
        "document_id": "doc_11",
        "document_name": "GP_Referral_14Jan2024.pdf",
        "date": "2024-01-14",
        "statement": "NKDA - no known drug allergies recorded."
      },
      "document_b": {
        "document_id": "doc_77ab",
        "document_name": "Cardiology_28Feb2024.pdf",
        "date": "2024-02-28",
        "statement": "Penicillin allergy - patient reports rash on exposure in 2019. Avoid beta-lactams."
      },
      "explanation": "Two recent documents disagree about drug allergy status. The cardiology record is more recent and patient-reported. Recommend confirming directly with the patient."
    }
  ]
}
```
`contradictions` is `[]` when none found (frontend shows the empty state).

---

### GET /api/patients/{id}/briefing

The pre-computed pre-appointment briefing. Served from the `patient_summary`
mart — must be a fast read, no LLM call on this path.

**200 response:**
```json
{
  "patient": {
    "id": "pat_8f3a",
    "name": "Mohammed Al-Rashidi",
    "dob": "1970-03-12",
    "nhs_number": "485 621 3847",
    "sex": "M",
    "age": 54
  },
  "generated_at": "2026-05-26T22:44:00Z",
  "disclaimer": "For administrative use only - this briefing is generated from extracted document data and does not constitute clinical advice.",
  "conditions": [ /* array of condition */ ],
  "medications": [ /* array of medication */ ],
  "recent_results": [ /* array of result */ ],
  "open_flags": [ /* array of flag */ ],
  "recent_imaging": [
    {
      "name": "Chest X-ray",
      "date": "2024-04-12",
      "report_status": "report attached",
      "document_id": "doc_91"
    }
  ],
  "last_documents": [
    { "document_id": "doc_11", "name": "GP_Referral_14Jan2024.pdf", "date": "2024-01-14" }
  ]
}
```
`recent_imaging` is `[]` when there is none.

---

### GET /api/patients/{id}/documents

**200 response:**
```json
{
  "documents": [
    {
      "id": "doc_77ab",
      "name": "Cardiology_28Feb2024.pdf",
      "type": "clinic_letter",
      "source": "Trust EPR",
      "date": "2024-02-28",
      "status": "processed"
    }
  ]
}
```
`type` ∈ `referral | clinic_letter | gp_note | clinician_note | lab_report | imaging`.
`status` ∈ `pending | processing | processed | failed`.

---

### GET /api/documents/{id}

One document with its extracted text and entities for the Documents page.

**200 response:**
```json
{
  "id": "doc_77ab",
  "name": "Cardiology_28Feb2024.pdf",
  "type": "clinic_letter",
  "source": "Trust EPR",
  "date": "2024-02-28",
  "status": "processed",
  "extracted_text": "Patient reports penicillin allergy - rash on exposure 2019. Avoid beta-lactams. ...",
  "entities": [ /* array of entity */ ],
  "image_url": null,
  "lab_results": null
}
```
- For `imaging` documents: `image_url` is set, `extracted_text`/`entities` may be empty.
- For `lab_report` documents: `lab_results` is an array of `result`, `entities` may be empty.

---

### POST /api/patients/{id}/documents

Upload a file. **Multipart**, not JSON.

**Form fields:**
| Field | Required | Notes |
|---|---|---|
| `file` | yes | PDF, DOCX, image (PNG/JPG) |
| `document_date` | yes | `YYYY-MM-DD` |
| `type` | yes | one of the `document.type` values |
| `source` | no | free text, e.g. "Trust EPR" |

**202 response** (accepted, processing happens async):
```json
{
  "document_id": "doc_new",
  "status": "pending",
  "message": "Added to record - processing entities."
}
```

> **Worker job contract.** On upload the API pushes the file to S3 and enqueues a job.
> The job payload is fixed: `{ "document_id": "doc_new", "patient_id": "pat_8f3a", "s3_key": "uploads/pat_8f3a/doc_new.pdf" }`.
> The worker reads everything else itself. This payload shape is part of the seam.

---

### POST /api/patients/{id}/notes

Add a free-text clinician note. JSON (no file). The note skips the parser and
goes straight to NLP.

**Request body:**
```json
{
  "text": "Patient seen today, reports improved exercise tolerance. BP 128/78.",
  "document_date": "2026-05-26",
  "source": "Dr Smith"
}
```

**202 response:** same shape as document upload (`document_id`, `status`, `message`).
The created document has `type: "clinician_note"`.

---

### POST /api/patients/{id}/labs

Add lab results by manual entry (the Lab tab's table).

**Request body:**
```json
{
  "document_date": "2026-05-26",
  "source": "Manual entry",
  "results": [
    { "test": "eGFR", "value": "44", "unit": "mL/min/1.73m2", "date": "2026-05-20" },
    { "test": "HbA1c", "value": "59", "unit": "mmol/mol", "date": "2026-05-20" }
  ]
}
```

**202 response:** same shape as document upload. The created document has
`type: "lab_report"`.

---

### PATCH /api/flags/{id}

**Request body:**
```json
{ "status": "resolved" }
```
`status` ∈ `open | resolved`.

**200 response:** the updated `flag`.

---

### PATCH /api/contradictions/{id}

**Request body:**
```json
{ "status": "resolved" }
```

**200 response:** the updated contradiction object.

---

### DELETE /api/patients/{id}

GDPR delete. Cascades: removes the patient, all documents, entities, flags,
contradictions, briefing, and S3 objects.

**200 response:**
```json
{ "deleted": true, "patient_id": "pat_8f3a" }
```

---

## 5. Page → endpoint map

Quick reference for the frontend — which call each screen makes.

| Page | Calls |
|---|---|
| Landing | `GET /patients`, `POST /patients` |
| Overview | `GET /patients/{id}` |
| Timeline | `GET /patients/{id}/timeline` |
| Flags | `GET /patients/{id}/flags`, `PATCH /flags/{id}` |
| Contradictions | `GET /patients/{id}/contradictions`, `PATCH /contradictions/{id}` |
| Briefing | `GET /patients/{id}/briefing` |
| Documents | `GET /patients/{id}/documents`, `GET /documents/{id}` |
| Upload | `POST /patients/{id}/documents`, `POST /patients/{id}/notes`, `POST /patients/{id}/labs` |

---

## 6. Open questions (resolve before Phase 3)

- [ ] Polling vs websockets for document `status` going `pending → processed`?
      (GTV: frontend polls `GET /documents/{id}` every few seconds — simplest.)
- [ ] Pagination on `GET /patients` — needed for GTV demo? (Probably not; revisit if list grows.)
- [ ] Auth: single shared API key for the demo, or per-user? (GTV: single shared key.)
