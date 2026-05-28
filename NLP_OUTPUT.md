# NLP Output Contract — Clinical Document Intelligence

**Status:** v1 (GTV scope)
**Owner:** NLP / Agents — *you* (produced) · Storage — *partner* (consumed)
**Pairs with:** `DB_SCHEMA.md` (every field below maps to a CORE column) and
`API_CONTRACT.md` (the API ultimately serves this data).

This is the single JSON object the worker produces after processing one
document. It is stored verbatim in `RAW.nlp_output.payload`, then unpacked into
CORE by the stored procedures. **This shape is part of the seam — no silent
changes.**

---

## 1. Pipeline that produces it

```
document (from S3)
  -> parsers       -> extracted_text
  -> nlp/medical_ner       -> entities
  -> nlp/negation_detector -> sets entity.negated
  -> nlp/date_normaliser   -> sets entity.normalised_value for dates
  -> agents/flag_agent          -> flags
  -> agents/contradiction_agent -> contradictions
  -> (derive)      -> conditions, medications, observations, timeline_events
  -> ONE json object  ->  RAW.nlp_output  ->  stored procs  ->  CORE
```

The NLP layer (scispaCy) fills `entities`. The agent layer (Claude) fills
`flags` and `contradictions`. `conditions` / `medications` / `observations` are
derived from non-negated entities. The worker assembles all of it into the
object below.

---

## 2. Full output object

```json
{
  "nlp_version": "1.0.0",
  "document_id": "doc_77ab",
  "patient_id": "pat_8f3a",
  "processed_at": "2026-05-26T22:44:00Z",
  "status": "processed",
  "error_message": null,

  "document": {
    "doc_type": "clinic_letter",
    "extracted_text": "Patient reports penicillin allergy - rash on exposure 2019. Avoid beta-lactams. Echocardiogram on 28 Feb 2024 confirms dilated cardiomyopathy with LVEF 32%. Commenced bisoprolol 2.5 mg once daily.",
    "image_url": null
  },

  "entities": [
    {
      "entity_type": "Drug",
      "text": "bisoprolol 2.5 mg",
      "start_offset": 150,
      "end_offset": 167,
      "negated": false,
      "icd10_code": null,
      "normalised_value": "bisoprolol"
    },
    {
      "entity_type": "Diagnosis",
      "text": "dilated cardiomyopathy",
      "start_offset": 108,
      "end_offset": 130,
      "negated": false,
      "icd10_code": "I42.0",
      "normalised_value": null
    },
    {
      "entity_type": "Diagnosis",
      "text": "penicillin allergy",
      "start_offset": 16,
      "end_offset": 34,
      "negated": false,
      "icd10_code": null,
      "normalised_value": null
    },
    {
      "entity_type": "Date",
      "text": "28 Feb 2024",
      "start_offset": 80,
      "end_offset": 91,
      "negated": false,
      "icd10_code": null,
      "normalised_value": "2024-02-28"
    }
  ],

  "conditions": [
    { "name": "Dilated cardiomyopathy", "icd10_code": "I42.0" }
  ],

  "medications": [
    {
      "drug": "Bisoprolol",
      "dose": "2.5 mg OD",
      "started": "2024-02-28",
      "flag_text": null
    }
  ],

  "observations": [
    {
      "test": "LVEF",
      "value": "32",
      "unit": "%",
      "observation_date": "2024-02-28"
    }
  ],

  "flags": [
    {
      "severity": "HIGH",
      "category": "ALLERGY CONFLICT",
      "description": "Allergy status conflicts between GP letter (NKDA) and cardiology letter (penicillin allergy). Verify before prescribing antibiotics.",
      "source_document_id": "doc_77ab"
    }
  ],

  "contradictions": [
    {
      "severity": "HIGH",
      "category": "ALLERGY",
      "doc_a_id": "doc_11",
      "doc_a_statement": "NKDA - no known drug allergies recorded.",
      "doc_b_id": "doc_77ab",
      "doc_b_statement": "Penicillin allergy - patient reports rash on exposure 2019. Avoid beta-lactams.",
      "explanation": "Two recent documents disagree about drug allergy status. The cardiology record is more recent and patient-reported. Recommend confirming directly with the patient."
    }
  ],

  "timeline_events": [
    {
      "event_date": "2024-02-28",
      "event_type": "Diagnosis",
      "title": "Dilated cardiomyopathy diagnosed",
      "icd10_code": "I42.0"
    },
    {
      "event_date": "2024-02-28",
      "event_type": "Medication",
      "title": "Started Bisoprolol 2.5 mg OD",
      "icd10_code": null
    }
  ]
}
```

---

## 3. Field rules

### Top level

| Field | Type | Rule |
|---|---|---|
| `nlp_version` | string | Version of the pipeline. Goes into `RAW.nlp_output.nlp_version`. |
| `document_id` | string | Must match the job's `document_id`. |
| `patient_id` | string | Must match the job's `patient_id`. |
| `processed_at` | string | ISO timestamp, UTC. |
| `status` | string | `processed` or `failed`. |
| `error_message` | string \| null | Set only when `status = failed`; all arrays then `[]`. |

### `entities[]` — from `nlp/medical_ner` + `negation_detector` + `date_normaliser`

| Field | Type | Rule |
|---|---|---|
| `entity_type` | string | `Diagnosis \| Drug \| Date \| Conflict`. |
| `text` | string | Exact span as it appears in `extracted_text`. |
| `start_offset` / `end_offset` | int | Char offsets into `extracted_text`. `extracted_text[start:end]` must equal `text`. |
| `negated` | bool | **Patient-safety critical.** TRUE if NegEx found negation ("no penicillin allergy"). Negated entities must NOT become conditions/flags. |
| `icd10_code` | string \| null | Set for diagnoses where mapping succeeded. |
| `normalised_value` | string \| null | For `Date`: ISO date. For `Drug`: normalised drug name. Else null. |

### `conditions[]` / `medications[]` / `observations[]` — derived

Built from **non-negated** entities only. A diagnosis entity with
`negated: true` ("no history of diabetes") must never appear in `conditions`.
Field shapes match `condition` / `medication` / `result` in `API_CONTRACT.md`.

### `flags[]` — from `agents/flag_agent` (Claude)

| Field | Type | Rule |
|---|---|---|
| `severity` | string | `HIGH \| MEDIUM \| LOW`. |
| `category` | string | Short uppercase label. |
| `description` | string | One or two sentences, doctor-readable. |
| `source_document_id` | string | The document this flag was raised from. **Provenance — required.** |

### `contradictions[]` — from `agents/contradiction_agent` (Claude)

| Field | Type | Rule |
|---|---|---|
| `severity` | string | `HIGH \| MEDIUM \| LOW`. |
| `category` | string | Short uppercase label. |
| `doc_a_id` / `doc_b_id` | string | The two conflicting documents. One is usually the current document. |
| `doc_a_statement` / `doc_b_statement` | string | The conflicting claim from each, quoted/paraphrased. |
| `explanation` | string | Reasoning + recommendation. Should weight recency and `doc_type` (a clinician note outranks an old letter). |

### `timeline_events[]` — derived

| Field | Type | Rule |
|---|---|---|
| `event_date` | string | ISO date. |
| `event_type` | string | `Diagnosis \| Medication \| Flag \| Referral \| Observation \| Lab \| Imaging`. |
| `title` | string | Short, e.g. "Started Bisoprolol 2.5 mg OD". |
| `icd10_code` | string \| null | |

---

## 4. The three new document types

The same object shape is produced for every document type — only which arrays
are populated changes.

| Doc type | What the worker does | Populated arrays |
|---|---|---|
| `clinician_note` | Skips parser (text is already clean). NER runs on the typed text directly. | `entities`, derived `conditions`/`medications`, `flags`, `timeline_events` |
| `lab_report` | Parses lab file (or takes manual-entry rows) straight into `observations`. NER may be skipped. | `observations`, `timeline_events` (type `Lab`) |
| `imaging` | Stores image; `extracted_text` empty, `image_url` set. If a text report is attached, that report is run through NER. | `timeline_events` (type `Imaging`); `entities` only if a report was attached |

For `lab_report` and `imaging`, unused arrays are simply `[]` — never `null`.

---

## 5. Failure case

If processing fails at any stage, the worker still produces a valid object:

```json
{
  "nlp_version": "1.0.0",
  "document_id": "doc_77ab",
  "patient_id": "pat_8f3a",
  "processed_at": "2026-05-26T22:44:00Z",
  "status": "failed",
  "error_message": "PDF could not be parsed: file is encrypted.",
  "document": { "doc_type": "clinic_letter", "extracted_text": "", "image_url": null },
  "entities": [],
  "conditions": [],
  "medications": [],
  "observations": [],
  "flags": [],
  "contradictions": [],
  "timeline_events": []
}
```

The worker then sets `RAW.raw_documents.status = 'failed'` and writes
`error_message`. The document still appears in the UI with a `failed` status so
nothing silently disappears.

---

## 6. Validation checklist (worker enforces before writing)

- [ ] `document_id` and `patient_id` match the job payload.
- [ ] `status` is `processed` or `failed`; if `failed`, all arrays are `[]`.
- [ ] For every entity: `extracted_text[start_offset:end_offset] == text`.
- [ ] No entity with `negated: true` appears in `conditions`.
- [ ] Every `flag` has a non-null `source_document_id`.
- [ ] Every `severity` is one of `HIGH / MEDIUM / LOW`.
- [ ] Every `entity_type` / `event_type` / `doc_type` is in its allowed set.
- [ ] All arrays present (use `[]`, never `null`, never omitted).
