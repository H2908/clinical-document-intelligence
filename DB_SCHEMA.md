# DB Schema — Clinical Document Intelligence (Snowflake)

**Status:** v1 (GTV scope)
**Owner:** Storage/Warehouse — *partner*
**Pairs with:** `API_CONTRACT.md` (every API field traces to a column here) and
`NLP_OUTPUT.md` (the JSON the worker writes into these tables).

GTV scale: single warehouse, no clustering keys, no multi-cluster. The layering
(RAW → CORE → MART) is kept so the design does not need rewriting later — but it
is sized for a demo, not for billions of rows yet.

---

## 1. Layering

| Layer | Purpose | Written by |
|---|---|---|
| **RAW** | Landing zone. File metadata + the raw NLP JSON blob, untouched. | API (on upload) + Worker |
| **CORE** | Structured, queried tables. One row per entity / flag / etc. | Worker (via stored procs) |
| **MART** | Pre-computed read models. The briefing lives here. | Worker (refresh step) |
| **VIEWS** | Thin SQL over CORE/MART that match API response shapes. | — (read by API) |

Flow: `file → S3 → RAW.raw_documents → worker processes → CORE tables → MART.patient_summary`.

---

## 2. RAW layer

### RAW.raw_documents
The upload landing record. Also the **job queue** (status column) for the GTV.

| Column | Type | Notes |
|---|---|---|
| `document_id` | STRING | PK. `doc_<uuid>`. |
| `patient_id` | STRING | FK → CORE.patient. |
| `file_name` | STRING | Original filename. |
| `doc_type` | STRING | `referral / clinic_letter / gp_note / clinician_note / lab_report / imaging`. |
| `source` | STRING | e.g. "Trust EPR". Nullable. |
| `document_date` | DATE | Clinical date of the document. |
| `s3_key` | STRING | Location of the raw file in S3. |
| `status` | STRING | `pending / processing / processed / failed`. **This is the queue.** |
| `error_message` | STRING | Set when `status = failed`. Nullable. |
| `uploaded_at` | TIMESTAMP_NTZ | When the API received it. |
| `processed_at` | TIMESTAMP_NTZ | When the worker finished. Nullable. |

### RAW.nlp_output
The raw JSON the NLP worker produced, stored verbatim before it is unpacked
into CORE. One row per document. Keeping this means re-processing is possible
without re-running NLP.

| Column | Type | Notes |
|---|---|---|
| `document_id` | STRING | PK / FK → raw_documents. |
| `patient_id` | STRING | FK → CORE.patient. |
| `payload` | VARIANT | The full NLP JSON (see `NLP_OUTPUT.md`). |
| `nlp_version` | STRING | Version of the NLP pipeline that produced it. |
| `created_at` | TIMESTAMP_NTZ | |

---

## 3. CORE layer

### CORE.patient

| Column | Type | Notes |
|---|---|---|
| `patient_id` | STRING | PK. `pat_<uuid>`. |
| `name` | STRING | |
| `dob` | DATE | |
| `nhs_number` | STRING | Stored with spaces, e.g. `485 621 3847`. UNIQUE. |
| `sex` | STRING | `M / F / Other`. |
| `created_at` | TIMESTAMP_NTZ | |
| `last_updated` | TIMESTAMP_NTZ | Bumped whenever a document is processed. |

### CORE.document
Promoted from RAW once processed — the clean record the app reads.

| Column | Type | Notes |
|---|---|---|
| `document_id` | STRING | PK. |
| `patient_id` | STRING | FK → patient. |
| `file_name` | STRING | |
| `doc_type` | STRING | Same enum as raw_documents. |
| `source` | STRING | Nullable. |
| `document_date` | DATE | |
| `s3_key` | STRING | |
| `image_url` | STRING | Presigned/served URL for `imaging` docs. Nullable. |
| `extracted_text` | STRING | Clean full text. Empty for pure-image docs. |
| `status` | STRING | `processed / failed`. |
| `created_at` | TIMESTAMP_NTZ | |

### CORE.entity
One row per span the NLP extracted. `start`/`end` index into
`document.extracted_text` — this is what powers source highlighting.

| Column | Type | Notes |
|---|---|---|
| `entity_id` | STRING | PK. `ent_<uuid>`. |
| `document_id` | STRING | FK → document. **Provenance.** |
| `patient_id` | STRING | FK → patient. |
| `entity_type` | STRING | `Diagnosis / Drug / Date / Conflict`. |
| `text` | STRING | The exact span text. |
| `start_offset` | INT | Char offset into extracted_text. |
| `end_offset` | INT | Char offset into extracted_text. |
| `negated` | BOOLEAN | TRUE if NegEx found it negated ("no chest pain"). **Patient-safety critical.** |
| `icd10_code` | STRING | For diagnoses. Nullable. |
| `normalised_value` | STRING | e.g. ISO date for a Date entity, normalised drug name. Nullable. |
| `created_at` | TIMESTAMP_NTZ | |

### CORE.condition
Active conditions, deduplicated per patient (derived from non-negated Diagnosis entities).

| Column | Type | Notes |
|---|---|---|
| `condition_id` | STRING | PK. |
| `patient_id` | STRING | FK → patient. |
| `name` | STRING | |
| `icd10_code` | STRING | Nullable. |
| `source_document_id` | STRING | FK → document. First doc it appeared in. |
| `created_at` | TIMESTAMP_NTZ | |

### CORE.medication

| Column | Type | Notes |
|---|---|---|
| `medication_id` | STRING | PK. |
| `patient_id` | STRING | FK → patient. |
| `drug` | STRING | |
| `dose` | STRING | e.g. "1 g BD". |
| `started` | DATE | Nullable. |
| `flag_text` | STRING | Amber warning text, e.g. "eGFR below threshold". Nullable. |
| `source_document_id` | STRING | FK → document. |
| `created_at` | TIMESTAMP_NTZ | |

### CORE.observation
Lab values and clinical observations — feeds the Briefing's "Recent results".

| Column | Type | Notes |
|---|---|---|
| `observation_id` | STRING | PK. |
| `patient_id` | STRING | FK → patient. |
| `test` | STRING | e.g. "eGFR". |
| `value` | STRING | Kept as string (values like "32%", "480"). |
| `unit` | STRING | Nullable. |
| `observation_date` | DATE | |
| `source_document_id` | STRING | FK → document. |
| `created_at` | TIMESTAMP_NTZ | |

### CORE.flag
Risk flags produced by the flag agent.

| Column | Type | Notes |
|---|---|---|
| `flag_id` | STRING | PK. `flag_<uuid>`. |
| `patient_id` | STRING | FK → patient. |
| `severity` | STRING | `HIGH / MEDIUM / LOW`. |
| `category` | STRING | e.g. "ALLERGY CONFLICT". |
| `description` | STRING | |
| `source_document_id` | STRING | FK → document. **Provenance.** |
| `status` | STRING | `open / resolved`. Default `open`. |
| `created_at` | TIMESTAMP_NTZ | |
| `resolved_at` | TIMESTAMP_NTZ | Nullable. |

### CORE.contradiction
Cross-document conflicts. References two documents.

| Column | Type | Notes |
|---|---|---|
| `contradiction_id` | STRING | PK. `con_<uuid>`. |
| `patient_id` | STRING | FK → patient. |
| `severity` | STRING | `HIGH / MEDIUM / LOW`. |
| `category` | STRING | e.g. "ALLERGY". |
| `doc_a_id` | STRING | FK → document. |
| `doc_a_statement` | STRING | The conflicting claim from doc A. |
| `doc_b_id` | STRING | FK → document. |
| `doc_b_statement` | STRING | The conflicting claim from doc B. |
| `explanation` | STRING | Agent's reasoning + recommendation. |
| `status` | STRING | `open / resolved`. Default `open`. |
| `created_at` | TIMESTAMP_NTZ | |
| `resolved_at` | TIMESTAMP_NTZ | Nullable. |

### CORE.timeline_event
Pre-flattened timeline rows. Could be a view, but a table keeps the Timeline
page fast and lets the worker write events directly.

| Column | Type | Notes |
|---|---|---|
| `event_id` | STRING | PK. |
| `patient_id` | STRING | FK → patient. |
| `event_date` | DATE | |
| `event_type` | STRING | `Diagnosis / Medication / Flag / Referral / Observation / Lab / Imaging`. |
| `title` | STRING | |
| `icd10_code` | STRING | Nullable. |
| `source_document_id` | STRING | FK → document. |
| `created_at` | TIMESTAMP_NTZ | |

---

## 4. MART layer

### MART.patient_summary
The **pre-computed briefing**. One row per patient. The worker rewrites this
row whenever a new document for that patient is processed. `GET /briefing`
reads only this — no LLM on the read path.

| Column | Type | Notes |
|---|---|---|
| `patient_id` | STRING | PK / FK → patient. |
| `summary` | VARIANT | Full briefing JSON — matches the `GET /briefing` response body. |
| `generated_at` | TIMESTAMP_NTZ | When this row was last rebuilt. |
| `is_stale` | BOOLEAN | TRUE when a new doc landed but summary not yet rebuilt. |

> **Refresh rule:** when the worker finishes a document, it sets
> `is_stale = TRUE`, then rebuilds the summary and sets it back to `FALSE`.
> `is_stale` is the GTV stand-in for an event-driven refresh.

---

## 5. Views (read by the API)

Each view is shaped to match an `API_CONTRACT.md` response so the API can
`SELECT *` and return it almost directly.

| View | Backs endpoint | Notes |
|---|---|---|
| `VW_PATIENT_LIST` | `GET /patients` | patient + document/flag counts. |
| `VW_PATIENT_360` | `GET /patients/{id}` | patient + conditions + meds + top 3 flags. |
| `VW_ACTIVE_FLAGS` | `GET /patients/{id}/flags` | flag joined to document name. |
| `VW_CONTRADICTION_LOG` | `GET /patients/{id}/contradictions` | contradiction joined to both doc names. |
| `VW_TIMELINE` | `GET /patients/{id}/timeline` | timeline_event joined to document name, newest first. |
| `VW_DOCUMENT_LIST` | `GET /patients/{id}/documents` | document list. |

---

## 6. Stored procedures (called by the worker)

The worker never writes tables directly — it calls these. Fixed signatures =
part of the seam.

| Procedure | Signature (conceptual) | Writes |
|---|---|---|
| `SP_WRITE_DOCUMENT` | `(document_id, ...fields, extracted_text)` | CORE.document |
| `SP_WRITE_ENTITIES` | `(document_id, patient_id, entities_json)` | CORE.entity (bulk) |
| `SP_WRITE_CLINICAL` | `(document_id, patient_id, conditions_json, meds_json, observations_json)` | condition / medication / observation |
| `SP_WRITE_FLAGS` | `(patient_id, flags_json)` | CORE.flag (bulk) |
| `SP_WRITE_CONTRADICTIONS` | `(patient_id, contradictions_json)` | CORE.contradiction (bulk) |
| `SP_WRITE_TIMELINE` | `(patient_id, events_json)` | CORE.timeline_event (bulk) |
| `SP_REFRESH_SUMMARY` | `(patient_id)` | MART.patient_summary |
| `SP_SET_FLAG_STATUS` | `(flag_id, status)` | CORE.flag |
| `SP_SET_CONTRADICTION_STATUS` | `(contradiction_id, status)` | CORE.contradiction |
| `SP_DELETE_PATIENT` | `(patient_id)` | cascades all tables + returns S3 keys to delete |

### 6.1 SP_WRITE_ENTITIES — LOCKED (Phase 2)

**Python signature** (in `database/snowflake_writer.py`):

```python
def write_entities(
    document_id: str,          # 'doc_'
    patient_id: str,           # 'pat_'
    entities: list[dict],      # each dict matches NLP_OUTPUT.md §3
) -> None
```

**Behaviour**
- Calls `SP_WRITE_ENTITIES(document_id, patient_id, entities_json)` in Snowflake
- Entity dicts are JSON-serialised and passed via `PARSE_JSON`
- Idempotent: re-processing the same `document_id` does not create duplicate rows
  (stored procedure does DELETE-then-INSERT keyed on `document_id`)

**Errors**
- Raises `RuntimeError` if the stored procedure fails for any reason
- The worker catches this and marks `raw_documents.status = 'failed'`

**Caller**
- `worker/document_processor.py::process_from_s3` (Phase 2)
- `worker/main.py` queue-polling loop (Phase 3+)

**Owner** — DE member

### 6.2 Other procedures
Signatures sketched in the table above. Will be locked in Phase 3 task list as
each is implemented and used end-to-end.
---

## 7. Provenance rule

Every `entity`, `flag`, `contradiction`, `timeline_event`, `condition`,
`medication`, and `observation` carries a `source_document_id`. A doctor must
always be able to click any item back to the document — and for entities, the
exact `start_offset`/`end_offset` span — it came from. Do not add a derived
table without a source link.
## 7. Read API (called by the agent orchestrator)

The orchestrator reads patient state via `database/snowflake_reader.py`.
Two functions, locked signatures:

### 7.1 read_entities_for_patient

```python
def read_entities_for_patient(patient_id: str) -> list[dict]:
    """Returns every entity for this patient, joined with its document metadata."""
```

Each returned dict:
- entity_type, text, start_offset, end_offset, negated, icd10_code, normalised_value (from CORE.entity)
- document_id, document_date, doc_type (from CORE.document, joined)

### 7.2 read_documents_for_patient

```python
def read_documents_for_patient(patient_id: str) -> list[dict]:
    """Returns documents for this patient, newest first."""
```

Each dict: document_id, doc_type, document_date, source, status.

Owner: DE member.
Caller: agents/orchestrator.py::_read_patient_state.