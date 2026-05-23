# CONTRACT.md

**Clinical Document Intelligence — Team Agreement**

This document is the **single source of truth** for how Member A (Data Engineer) and Member B (ML Engineer) work together. Both members read this before starting any task.

> ⚠️ **Rule:** If something here changes, BOTH members must agree and update this doc. Never change schemas/APIs unilaterally.

---

## 1. Snowflake Table Schemas

All tables use `STRING` for IDs (UUIDs), `DATE` for dates, `TIMESTAMP_NTZ` for timestamps.

### 1.1 RAW layer — `raw_documents`

Stores raw uploaded files from S3 (auto-ingested via Snowpipe).

```sql
CREATE OR REPLACE TABLE raw_documents (
    raw_id          STRING DEFAULT UUID_STRING() PRIMARY KEY,
    s3_key          STRING NOT NULL,
    file_type       STRING,              -- 'pdf', 'image', 'text', 'hl7'
    file_size_bytes NUMBER,
    raw_content     STRING,              -- text content (for text files)
    metadata        VARIANT,             -- JSON metadata from S3
    ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    processed       BOOLEAN DEFAULT FALSE
);
```

### 1.2 CORE layer — main tables

#### `patient`
```sql
CREATE OR REPLACE TABLE patient (
    patient_id      STRING PRIMARY KEY,
    nhs_number      STRING UNIQUE NOT NULL,
    first_name      STRING NOT NULL,
    last_name       STRING NOT NULL,
    dob             DATE NOT NULL,
    sex             STRING(1),           -- 'M' or 'F'
    address         STRING,
    city            STRING,
    postcode        STRING,
    gp_practice     STRING,
    registered_date DATE,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

#### `document`
```sql
CREATE OR REPLACE TABLE document (
    doc_id          STRING PRIMARY KEY,
    patient_id      STRING NOT NULL REFERENCES patient(patient_id),
    filename        STRING NOT NULL,
    doc_type        STRING,              -- 'GP_Referral', 'Cardiology_Letter', etc.
    s3_key          STRING NOT NULL,
    document_date   DATE,                -- date written in document
    uploaded_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    processed_at    TIMESTAMP_NTZ,
    processing_status STRING DEFAULT 'pending'  -- 'pending', 'processing', 'completed', 'failed'
);
```

#### `entity`
Stores ALL extracted entities from NLP (diagnoses, medications, observations, dates).

```sql
CREATE OR REPLACE TABLE entity (
    entity_id       STRING PRIMARY KEY,
    doc_id          STRING NOT NULL REFERENCES document(doc_id),
    patient_id      STRING NOT NULL REFERENCES patient(patient_id),
    entity_type     STRING NOT NULL,     -- 'diagnosis', 'medication', 'observation', 'allergy', 'referral'
    entity_value    STRING NOT NULL,     -- "Type 2 diabetes mellitus"
    code            STRING,              -- ICD-10 or BNF code
    code_system     STRING,              -- 'ICD10', 'BNF', 'SNOMED'
    event_date      DATE,
    dose            STRING,              -- for medications
    unit            STRING,              -- for observations
    value           STRING,              -- for observations
    negated         BOOLEAN DEFAULT FALSE, -- NegEx detection
    confidence      FLOAT,               -- NLP confidence score
    source_text     STRING,              -- original text span
    source_offset_start NUMBER,          -- char position in document
    source_offset_end   NUMBER,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

#### `flag`
Risk flags raised by LLM agents.

```sql
CREATE OR REPLACE TABLE flag (
    flag_id         STRING PRIMARY KEY,
    patient_id      STRING NOT NULL REFERENCES patient(patient_id),
    source_doc_id   STRING REFERENCES document(doc_id),
    severity        STRING NOT NULL,     -- 'HIGH', 'MEDIUM', 'LOW'
    category        STRING NOT NULL,     -- 'ALLERGY_CONFLICT', 'OVERDUE_REFERRAL', 'DRUG_SAFETY', etc.
    description     STRING NOT NULL,
    related_entity_id STRING REFERENCES entity(entity_id),
    status          STRING DEFAULT 'open', -- 'open', 'resolved', 'dismissed'
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    resolved_at     TIMESTAMP_NTZ,
    resolved_by     STRING
);
```

#### `contradiction`
Cross-document contradictions detected by LLM.

```sql
CREATE OR REPLACE TABLE contradiction (
    contradiction_id STRING PRIMARY KEY,
    patient_id      STRING NOT NULL REFERENCES patient(patient_id),
    severity        STRING NOT NULL,     -- 'HIGH', 'MEDIUM', 'LOW'
    category        STRING NOT NULL,     -- 'ALLERGY', 'MEDICATION', 'DIAGNOSIS'
    doc_a_id        STRING NOT NULL REFERENCES document(doc_id),
    doc_a_statement STRING NOT NULL,
    doc_b_id        STRING NOT NULL REFERENCES document(doc_id),
    doc_b_statement STRING NOT NULL,
    ai_recommendation STRING,
    status          STRING DEFAULT 'open',
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    resolved_at     TIMESTAMP_NTZ
);
```

#### `summary`
LLM-generated summaries (briefings).

```sql
CREATE OR REPLACE TABLE summary (
    summary_id      STRING PRIMARY KEY,
    patient_id      STRING NOT NULL REFERENCES patient(patient_id),
    summary_type    STRING,              -- 'briefing', 'timeline', 'discharge'
    content         STRING NOT NULL,
    generated_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    model_used      STRING               -- 'claude-opus-4-7'
);
```

### 1.3 MART layer — views for frontend

```sql
-- For Screen 1: Patient list
CREATE OR REPLACE VIEW v_patient_list AS
SELECT 
    p.patient_id,
    p.first_name || ' ' || p.last_name AS name,
    p.dob,
    p.sex,
    p.nhs_number,
    DATEDIFF(year, p.dob, CURRENT_DATE) AS age,
    COUNT(DISTINCT CASE WHEN f.status='open' THEN f.flag_id END) AS open_flags,
    COUNT(DISTINCT c.contradiction_id) AS contradictions,
    COUNT(DISTINCT d.doc_id) AS documents
FROM patient p
LEFT JOIN flag f ON f.patient_id = p.patient_id
LEFT JOIN contradiction c ON c.patient_id = p.patient_id  
LEFT JOIN document d ON d.patient_id = p.patient_id
GROUP BY p.patient_id, p.first_name, p.last_name, p.dob, p.sex, p.nhs_number;

-- For Screen 2: Overview
CREATE OR REPLACE VIEW v_patient_overview AS
SELECT 
    p.*,
    COUNT(DISTINCT d.doc_id) AS total_documents,
    COUNT(DISTINCT CASE WHEN f.status='open' THEN f.flag_id END) AS open_flags,
    COUNT(DISTINCT c.contradiction_id) AS contradictions,
    MAX(d.uploaded_at) AS last_updated
FROM patient p
LEFT JOIN document d ON d.patient_id = p.patient_id
LEFT JOIN flag f ON f.patient_id = p.patient_id
LEFT JOIN contradiction c ON c.patient_id = p.patient_id
GROUP BY p.patient_id, p.nhs_number, p.first_name, p.last_name, p.dob, 
         p.sex, p.address, p.city, p.postcode, p.gp_practice, 
         p.registered_date, p.created_at, p.updated_at;

-- For Screen 3: Timeline
CREATE OR REPLACE VIEW v_timeline AS
SELECT 
    e.entity_id,
    e.patient_id,
    e.event_date,
    e.entity_type AS event_type,
    e.entity_value AS description,
    e.code,
    d.filename AS source_pdf,
    d.doc_id
FROM entity e
JOIN document d ON d.doc_id = e.doc_id
WHERE e.negated = FALSE
ORDER BY e.event_date DESC;

-- For Screen 2/4: Active flags
CREATE OR REPLACE VIEW v_active_flags AS
SELECT 
    f.*,
    d.filename AS source_pdf
FROM flag f
LEFT JOIN document d ON d.doc_id = f.source_doc_id
WHERE f.status = 'open'
ORDER BY 
    CASE f.severity 
        WHEN 'HIGH' THEN 1 
        WHEN 'MEDIUM' THEN 2 
        WHEN 'LOW' THEN 3 
    END,
    f.created_at DESC;

-- For Screen 2: Active conditions  
CREATE OR REPLACE VIEW v_active_conditions AS
SELECT 
    patient_id,
    entity_value AS condition_name,
    code,
    event_date AS diagnosed_date
FROM entity
WHERE entity_type = 'diagnosis'
  AND negated = FALSE;

-- For Screen 2: Current medications
CREATE OR REPLACE VIEW v_current_medications AS
SELECT 
    e.patient_id,
    e.entity_value AS drug_name,
    e.dose,
    e.event_date AS start_date,
    e.code AS bnf_code,
    f.description AS flag_warning
FROM entity e
LEFT JOIN flag f ON f.related_entity_id = e.entity_id AND f.status = 'open'
WHERE e.entity_type = 'medication'
  AND e.negated = FALSE;

-- For Screen 5: Contradictions
CREATE OR REPLACE VIEW v_contradictions AS
SELECT 
    c.*,
    da.filename AS doc_a_filename,
    da.document_date AS doc_a_date,
    db.filename AS doc_b_filename,
    db.document_date AS doc_b_date
FROM contradiction c
JOIN document da ON da.doc_id = c.doc_a_id
JOIN document db ON db.doc_id = c.doc_b_id
WHERE c.status = 'open';
```

---

## 2. NLP Worker JSON Output Format

This is the **JSON contract** between ML pipeline and DE database.

When the worker finishes processing a document, it outputs JSON in this **exact** format:

```json
{
  "doc_id": "abc-123-def",
  "patient_id": "p001",
  "processing_status": "completed",
  "processed_at": "2026-05-22T10:30:00Z",
  
  "document_metadata": {
    "filename": "Cardiology_28Feb2024.pdf",
    "doc_type": "Cardiology_Letter",
    "document_date": "2024-02-28",
    "page_count": 2,
    "extraction_method": "pymupdf"
  },
  
  "entities": [
    {
      "entity_type": "diagnosis",
      "entity_value": "Dilated cardiomyopathy",
      "code": "I42.0",
      "code_system": "ICD10",
      "event_date": "2024-02-28",
      "negated": false,
      "confidence": 0.95,
      "source_text": "dilated cardiomyopathy",
      "source_offset_start": 90,
      "source_offset_end": 112
    },
    {
      "entity_type": "medication",
      "entity_value": "Bisoprolol 2.5 mg",
      "code": "02.04.00.00",
      "code_system": "BNF",
      "dose": "2.5 mg OD",
      "event_date": "2024-02-28",
      "negated": false,
      "confidence": 0.92,
      "source_text": "bisoprolol 2.5 mg",
      "source_offset_start": 130,
      "source_offset_end": 147
    },
    {
      "entity_type": "observation",
      "entity_value": "LVEF",
      "value": "32",
      "unit": "%",
      "event_date": "2024-02-28",
      "negated": false,
      "confidence": 0.98,
      "source_text": "LVEF 32%",
      "source_offset_start": 200,
      "source_offset_end": 208
    },
    {
      "entity_type": "allergy",
      "entity_value": "Penicillin",
      "event_date": "2019-01-01",
      "negated": false,
      "confidence": 0.97,
      "source_text": "penicillin allergy",
      "source_offset_start": 50,
      "source_offset_end": 68
    }
  ],
  
  "flags": [
    {
      "severity": "MEDIUM",
      "category": "DRUG_SAFETY",
      "description": "Metformin 1 g BD continues despite eGFR below threshold",
      "related_entity_index": 1
    }
  ],
  
  "contradictions_detected": [
    {
      "severity": "HIGH",
      "category": "ALLERGY",
      "compared_doc_id": "xyz-789",
      "this_doc_statement": "Patient reports penicillin allergy",
      "other_doc_statement": "NKDA — no known drug allergies",
      "ai_recommendation": "Verify allergy status with patient directly"
    }
  ],
  
  "summary": "65yo male with dilated cardiomyopathy (LVEF 32%). Started on bisoprolol and spironolactone. Refer to heart failure nurse within 2 weeks.",
  
  "errors": []
}
```

### Field rules

| Field | Required | Notes |
|-------|----------|-------|
| `doc_id` | ✅ | UUID, matches `document.doc_id` |
| `patient_id` | ✅ | Must exist in `patient` table |
| `entities[].entity_type` | ✅ | Enum: `diagnosis`, `medication`, `observation`, `allergy`, `referral` |
| `entities[].code` | ⚠️ | Required for diagnosis (ICD10) and medication (BNF) |
| `entities[].negated` | ✅ | Boolean, comes from NegEx |
| `entities[].confidence` | ✅ | Float 0.0-1.0 |
| `flags[].severity` | ✅ | Enum: `HIGH`, `MEDIUM`, `LOW` |
| `errors[]` | ✅ | Empty list if successful |

### Failure case

If processing fails, return:
```json
{
  "doc_id": "abc-123",
  "patient_id": "p001",
  "processing_status": "failed",
  "errors": [
    {
      "stage": "ocr",
      "message": "Tesseract failed to extract text from page 2"
    }
  ]
}
```

---

## 3. API Endpoint Signatures

Base URL: `http://localhost:8000/api/v1`

All endpoints require `X-API-Key` header (except `/health`).

### 3.1 Health check

```
GET /health

Response 200:
{
  "status": "ok",
  "snowflake": "connected",
  "version": "1.0.0"
}
```

### 3.2 Upload document

```
POST /documents
Content-Type: multipart/form-data

Request:
- file: binary (PDF/image) OR
- text: string (for plain text)
- patient_id: string (required)
- doc_type: string (optional)

Response 201:
{
  "doc_id": "abc-123-def",
  "patient_id": "p001",
  "s3_key": "raw/p001/abc-123-def.pdf",
  "status": "queued",
  "estimated_processing_time_seconds": 60
}

Response 400: Bad request (missing patient_id, invalid file type)
Response 413: File too large (>10MB)
```

### 3.3 List patients

```
GET /patients?search=string&limit=20&offset=0

Response 200:
[
  {
    "id": "p001",
    "name": "Mohammed Al-Rashidi",
    "age_sex": "54M",
    "dob": "12/03/1970",
    "nhs_number": "485 621 3847",
    "counts": {
      "open_flags": 3,
      "contradictions": 1,
      "documents": 3
    }
  }
]
```

### 3.4 Patient overview (Screen 2)

```
GET /patients/{patient_id}

Response 200:
{
  "patient": {
    "id": "p001",
    "name": "Mohammed Al-Rashidi",
    "dob": "12/03/1970",
    "nhs_number": "485 621 3847"
  },
  "stats": {
    "total_documents": 3,
    "open_flags": 3,
    "contradictions": 1,
    "last_updated": "25mo ago"
  },
  "active_conditions": [
    {"name": "Dilated cardiomyopathy", "code": "I42.0"},
    {"name": "Type 2 diabetes mellitus", "code": "E11"}
  ],
  "current_medications": [
    {
      "drug": "Bisoprolol",
      "dose": "2.5 mg OD",
      "started": "2023-11-02",
      "flag": null
    },
    {
      "drug": "Metformin",
      "dose": "1 g BD",
      "started": "2019-04-10",
      "flag": "eGFR below recommended threshold"
    }
  ],
  "top_open_flags": [
    {
      "id": "flag-123",
      "severity": "HIGH",
      "category": "ALLERGY CONFLICT",
      "description": "Allergy status conflicts between GP letter and cardiology letter"
    }
  ]
}

Response 404: Patient not found
```

### 3.5 Patient timeline (Screen 3)

```
GET /patients/{patient_id}/timeline?event_type=all

Query params:
- event_type: 'all' | 'diagnoses' | 'medications' | 'flags' | 'referrals' | 'observations'

Response 200:
[
  {
    "id": "ent-001",
    "date": "10 Apr 2024",
    "type": "observation",
    "description": "eGFR 42 mL/min/1.73m²",
    "code": null,
    "source_pdf": "DM_Review_10Apr2024.pdf",
    "doc_id": "doc-123"
  },
  {
    "id": "ent-002",
    "date": "28 Feb 2024",
    "type": "diagnosis",
    "description": "Dilated cardiomyopathy diagnosed",
    "code": "I42.0",
    "source_pdf": "Cardiology_28Feb2024.pdf",
    "doc_id": "doc-456"
  }
]
```

### 3.6 Patient flags (Screen 4)

```
GET /patients/{patient_id}/flags?status=open

Response 200:
[
  {
    "id": "flag-001",
    "severity": "HIGH",
    "category": "ALLERGY CONFLICT",
    "description": "Allergy status conflicts...",
    "source_pdf": "Cardiology_28Feb2024.pdf",
    "doc_id": "doc-456",
    "status": "open",
    "created_at": "2024-02-28T10:30:00Z"
  }
]
```

### 3.7 Resolve flag

```
PATCH /flags/{flag_id}/resolve

Response 200:
{
  "flag_id": "flag-001",
  "status": "resolved",
  "resolved_at": "2026-05-22T15:00:00Z"
}
```

### 3.8 Contradictions (Screen 5)

```
GET /patients/{patient_id}/contradictions

Response 200:
[
  {
    "id": "contra-001",
    "severity": "HIGH",
    "category": "ALLERGY",
    "doc_a": {
      "id": "doc-123",
      "filename": "GP_Referral_14Jan2024.pdf",
      "date": "14 Jan 2024",
      "statement": "NKDA — no known drug allergies recorded."
    },
    "doc_b": {
      "id": "doc-456",
      "filename": "Cardiology_28Feb2024.pdf",
      "date": "28 Feb 2024",
      "statement": "Penicillin allergy — patient reports rash on exposure in 2019."
    },
    "ai_recommendation": "Two recent documents disagree about drug allergy status...",
    "status": "open"
  }
]
```

### 3.9 Pre-appointment briefing (Screen 6)

```
GET /patients/{patient_id}/briefing

Response 200:
{
  "patient": {
    "name": "Mohammed Al-Rashidi",
    "age": 54,
    "sex": "M",
    "dob": "12/03/1970",
    "nhs_number": "485 621 3847"
  },
  "generated_at": "2026-05-22T19:26:23Z",
  "active_conditions": [
    {"name": "Dilated cardiomyopathy", "code": "I42.0"},
    ...
  ],
  "current_medications": [...],
  "recent_results": [
    {"test": "eGFR", "value": "42", "unit": "mL/min/1.73m²", "date": "10 Apr 2024"}
  ],
  "open_flags": {
    "high": 2,
    "medium": 1,
    "low": 0,
    "items": [...]
  },
  "last_documents": [
    {"filename": "GP_Referral_14Jan2024.pdf", "date": "14 Jan 2024"}
  ]
}
```

### 3.10 Source documents (Screen 7)

```
GET /patients/{patient_id}/documents

Response 200:
[
  {
    "doc_id": "doc-123",
    "filename": "GP_Referral_14Jan2024.pdf",
    "doc_type": "Referral",
    "source": "EMIS Web",
    "document_date": "14 Jan 2024"
  }
]
```

```
GET /documents/{doc_id}

Response 200:
{
  "doc_id": "doc-123",
  "filename": "Cardiology_28Feb2024.pdf",
  "text": "Patient reports penicillin allergy — rash on exposure 2019...",
  "entities": [
    {
      "start": 8,
      "end": 45,
      "type": "conflict",
      "text": "reports penicillin allergy",
      "code": null
    },
    {
      "start": 90,
      "end": 112,
      "type": "diagnosis",
      "text": "dilated cardiomyopathy",
      "code": "I42.0"
    }
  ]
}
```

---

## 4. Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient with id p999 does not exist",
    "details": {}
  }
}
```

Common error codes:
- `INVALID_API_KEY` (401)
- `PATIENT_NOT_FOUND` (404)
- `DOCUMENT_NOT_FOUND` (404)
- `INVALID_FILE_TYPE` (400)
- `FILE_TOO_LARGE` (413)
- `PROCESSING_FAILED` (500)
- `SNOWFLAKE_ERROR` (503)

---

## 5. Environment Variables

Both members use this `.env`:

```bash
# Snowflake (Member A provides)
SNOWFLAKE_ACCOUNT=xxx.eu-west-2.aws
SNOWFLAKE_USER=clinical_user
SNOWFLAKE_PASSWORD=xxx
SNOWFLAKE_DATABASE=CLINICAL_DI
SNOWFLAKE_SCHEMA=CORE
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=DEVELOPER

# AWS (Member A provides)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=eu-west-2
S3_BUCKET=clinical-di-raw

# LLM (Member B provides)
ANTHROPIC_API_KEY=sk-ant-xxx

# API
API_KEY=dev-key-123
API_PORT=8000
WORKER_CONCURRENCY=2

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## 6. Coding Standards

### Python
- Format: `black` (line length 100)
- Lint: `ruff`
- Type hints required for public functions
- Docstrings: Google style

### SQL
- Lowercase keywords (`select`, not `SELECT`)
- 4-space indent
- One column per line in `SELECT`
- Always specify column names in `INSERT`

### Commits
```
<type>(<scope>): <subject>

Examples:
feat(api): add patient timeline endpoint
fix(nlp): handle empty PDF gracefully
chore(db): add index on entity.patient_id
docs(readme): update setup instructions
```

---

## 7. Mock Data Strategy

Both members start with **mock data** so neither blocks the other:

### Member A's mocks (while ML pipeline isn't ready):
- Load `nhs_data/conditions.csv` directly into `entity` table
- Map columns: `description` → `entity_value`, `icd10_code` → `code`, etc.
- This populates Snowflake without needing NLP worker

### Member B's mocks (while Snowflake isn't ready):
- Write JSON files to disk instead of calling Snowflake
- Path: `worker/output/{doc_id}.json`
- Switch to Snowflake writer later (same JSON format)

---

## 8. Integration Milestones

### Milestone 1: End-of-Week-1 (vertical slice)
- [ ] Member A: Patient + entity tables populated from CSV
- [ ] Member B: PDF → entities JSON working locally
- [ ] **Demo:** Upload one PDF → see entities in Snowflake

### Milestone 2: End-of-Week-2 (API works)
- [ ] Member A: All views created
- [ ] Member B: API endpoints return real data
- [ ] **Demo:** `curl /api/v1/patients/p001` returns full overview

### Milestone 3: End-of-Week-3 (frontend works)
- [ ] All 7 screens render real data
- [ ] **Demo:** Click through dashboard end-to-end

### Milestone 4: End-of-Week-4 (production-ready)
- [ ] Tests passing (especially negation detection)
- [ ] Docker compose works
- [ ] README with screenshots

---

## 9. Communication

- **Daily standup:** 9:30 AM, 15 min, on call
- **Questions:** WhatsApp group (response within 2 hours)
- **Blockers:** Tag in GitHub Issue immediately
- **Weekly review:** Sunday 7 PM, 1 hour
- **Code reviews:** PR must have approval from the other member

---

## 10. Definition of Done

A task is "done" when:
- [ ] Code merged to `main` branch
- [ ] At least one test added (if applicable)
- [ ] Documentation updated (README or CONTRACT.md)
- [ ] Other member can run it locally without help
- [ ] No `TODO` or `FIXME` left in code

---

**Last updated:** 2026-05-22
**Members:** A (Data Engineer), B (ML Engineer)

> Any change to this document requires both members' agreement. Open a PR with the changes, get review, then merge.
