-- 03_core.sql — clinical-intelligence
-- CORE + MART layers: source of truth.
-- Matches DB_SCHEMA.md v1 (locked).
-- Run AFTER 01_raw.sql and 02_staging.sql.
--
-- Table creation order (respects FK dependencies):
--   1. patient
--   2. document
--   3. entity
--   4. condition
--   5. medication
--   6. observation
--   7. flag
--   8. contradiction
--   9. timeline_event
--   10. MART.patient_summary
--
-- Note: Snowflake does not enforce FK constraints but they are
-- declared as documentation and optimizer hints.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;

-- ══════════════════════════════════════════════════════════════════
-- CORE LAYER
-- ══════════════════════════════════════════════════════════════════

USE SCHEMA core;

-- ── 1. patient ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient (
    patient_id      STRING          NOT NULL,   -- PK. pat_<uuid>. Set by API.
    name            STRING          NOT NULL,
    dob             DATE            NOT NULL,
    nhs_number      STRING          NOT NULL,   -- stored with spaces e.g. "485 621 3847"
    sex             STRING          NOT NULL,   -- M | F | Other
    created_at      TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    last_updated    TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
                                                -- bumped on every document processed
    PRIMARY KEY (patient_id),
    UNIQUE (nhs_number)
)
COMMENT = 'One row per patient.';

-- ── 2. document ──────────────────────────────────────────────────
-- Promoted from RAW once processed. The clean record the API reads.
CREATE TABLE IF NOT EXISTS document (
    document_id     STRING          NOT NULL,   -- PK. doc_<uuid>. Set by API.
    patient_id      STRING          NOT NULL,   -- FK → patient
    file_name       STRING          NOT NULL,
    doc_type        STRING          NOT NULL,   -- referral|clinic_letter|gp_note|
                                                -- clinician_note|lab_report|imaging
    source          STRING,                     -- nullable. e.g. "Trust EPR"
    document_date   DATE,
    s3_key          STRING          NOT NULL,
    image_url       STRING,                     -- presigned URL for imaging docs. Nullable.
    extracted_text  STRING,                     -- clean full text. Empty for pure-image docs.
    status          STRING          NOT NULL DEFAULT 'processed',
                                                -- processed | failed
    created_at      TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (document_id),
    FOREIGN KEY (patient_id) REFERENCES patient (patient_id)
)
COMMENT = 'Clean document record promoted from RAW after processing.';

-- ── 3. entity ────────────────────────────────────────────────────
-- One row per NLP-extracted span.
-- start_offset/end_offset index into document.extracted_text —
-- powers source highlighting in the Documents page.
CREATE TABLE IF NOT EXISTS entity (
    entity_id       STRING          NOT NULL,   -- PK. ent_<uuid>. Set by SP.
    document_id     STRING          NOT NULL,   -- FK → document. Provenance.
    patient_id      STRING          NOT NULL,   -- FK → patient. Denormalised for speed.
    entity_type     STRING          NOT NULL,   -- Diagnosis | Drug | Date | Conflict
    text            STRING          NOT NULL,   -- exact span text
    start_offset    INT             NOT NULL,   -- char offset into extracted_text
    end_offset      INT             NOT NULL,   -- char offset into extracted_text
    negated         BOOLEAN         NOT NULL,   -- PATIENT-SAFETY CRITICAL. Never nullable.
                                                -- TRUE = "no chest pain", must NOT become
                                                -- a condition/flag
    icd10_code      STRING,                     -- for Diagnosis entities. Nullable.
    normalised_value STRING,                    -- ISO date for Date; drug name for Drug.
    bnf_code            STRING,                 ---- BNF drug code. Nullable — drugs only.
    created_at      TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (entity_id),
    FOREIGN KEY (document_id) REFERENCES document (document_id),
    FOREIGN KEY (patient_id)  REFERENCES patient  (patient_id)
)
COMMENT = 'NLP-extracted spans. negated is NOT NULL — patient-safety critical.';

-- ── 4. condition ─────────────────────────────────────────────────
-- Active conditions, deduplicated per patient.
-- Derived from non-negated Diagnosis entities only.
CREATE TABLE IF NOT EXISTS condition (
    condition_id        STRING          NOT NULL,   -- PK. cond_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    name                STRING          NOT NULL,
    icd10_code          STRING,                     -- nullable
    source_document_id  STRING          NOT NULL,   -- FK → document. First doc it appeared in.
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (condition_id),
    FOREIGN KEY (patient_id)         REFERENCES patient  (patient_id),
    FOREIGN KEY (source_document_id) REFERENCES document (document_id)
)
COMMENT = 'Active conditions per patient. Derived from non-negated Diagnosis entities only.';

-- ── 5. medication ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medication (
    medication_id       STRING          NOT NULL,   -- PK. med_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    drug                STRING          NOT NULL,
    dose                STRING,                     -- e.g. "1 g BD". Nullable.
    started             DATE,                       -- nullable
    flag_text           STRING,                     -- amber warning. e.g. "eGFR below threshold".
                                                    -- Nullable.
    source_document_id  STRING          NOT NULL,   -- FK → document
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (medication_id),
    FOREIGN KEY (patient_id)         REFERENCES patient  (patient_id),
    FOREIGN KEY (source_document_id) REFERENCES document (document_id)
)
COMMENT = 'Medications per patient.';

-- ── 6. observation ───────────────────────────────────────────────
-- Lab values and clinical observations.
-- Feeds the Briefing page "Recent results" section.
-- value stored as STRING to handle "32%", "480", "<0.1" etc.
CREATE TABLE IF NOT EXISTS observation (
    observation_id      STRING          NOT NULL,   -- PK. obs_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    test                STRING          NOT NULL,   -- e.g. "eGFR"
    value               STRING          NOT NULL,   -- kept as string: "32%", "480"
    unit                STRING,                     -- nullable. e.g. "mL/min/1.73m2"
    observation_date    DATE            NOT NULL,
    source_document_id  STRING          NOT NULL,   -- FK → document
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (observation_id),
    FOREIGN KEY (patient_id)         REFERENCES patient  (patient_id),
    FOREIGN KEY (source_document_id) REFERENCES document (document_id)
)
COMMENT = 'Lab values and clinical observations. value is STRING to handle all formats.';

-- ── 7. flag ──────────────────────────────────────────────────────
-- Risk flags produced by the flag agent (Claude).
CREATE TABLE IF NOT EXISTS flag (
    flag_id             STRING          NOT NULL,   -- PK. flag_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    severity            STRING          NOT NULL,   -- HIGH | MEDIUM | LOW
    category            STRING          NOT NULL,   -- e.g. "ALLERGY CONFLICT"
    description         STRING          NOT NULL,
    source_document_id  STRING          NOT NULL,   -- FK → document. Provenance — required.
    provenance_hash     STRING,                     -- Audit fingerprint. Nullable. Set by flag_agent.
    status              STRING          NOT NULL DEFAULT 'open',
                                                    -- open | resolve
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    resolved_at         TIMESTAMP_NTZ,              -- nullable
    PRIMARY KEY (flag_id),
    FOREIGN KEY (patient_id)         REFERENCES patient  (patient_id),
    FOREIGN KEY (source_document_id) REFERENCES document (document_id)
)
COMMENT = 'Risk flags from the flag agent. status: open | resolved.';

-- ── 8. contradiction ─────────────────────────────────────────────
-- Cross-document conflicts found by the contradiction agent (Claude).
-- References two documents (doc_a and doc_b).
CREATE TABLE IF NOT EXISTS contradiction (
    contradiction_id    STRING          NOT NULL,   -- PK. con_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    severity            STRING          NOT NULL,   -- HIGH | MEDIUM | LOW
    category            STRING          NOT NULL,   -- e.g. "ALLERGY"
    doc_a_id            STRING          NOT NULL,   -- FK → document
    doc_a_statement     STRING          NOT NULL,   -- conflicting claim from doc A
    doc_b_id            STRING          NOT NULL,   -- FK → document
    doc_b_statement     STRING          NOT NULL,   -- conflicting claim from doc B
    explanation         STRING          NOT NULL,   -- agent reasoning + recommendation
    status              STRING          NOT NULL DEFAULT 'open',
                                                    -- open | resolved
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    resolved_at         TIMESTAMP_NTZ,              -- nullable
    PRIMARY KEY (contradiction_id),
    FOREIGN KEY (patient_id) REFERENCES patient  (patient_id),
    FOREIGN KEY (doc_a_id)   REFERENCES document (document_id),
    FOREIGN KEY (doc_b_id)   REFERENCES document (document_id)
)
COMMENT = 'Cross-document contradictions from the contradiction agent.';

-- ── 9. timeline_event ────────────────────────────────────────────
-- Pre-flattened timeline rows. Table (not view) for speed and so
-- the worker can write events directly.
CREATE TABLE IF NOT EXISTS timeline_event (
    event_id            STRING          NOT NULL,   -- PK. evt_<uuid>.
    patient_id          STRING          NOT NULL,   -- FK → patient
    event_date          DATE            NOT NULL,
    event_type          STRING          NOT NULL,   -- Diagnosis | Medication | Flag |
                                                    -- Referral | Observation | Lab | Imaging
    title               STRING          NOT NULL,
    icd10_code          STRING,                     -- nullable
    source_document_id  STRING          NOT NULL,   -- FK → document. Provenance — required.
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (event_id),
    FOREIGN KEY (patient_id)         REFERENCES patient  (patient_id),
    FOREIGN KEY (source_document_id) REFERENCES document (document_id)
)
COMMENT = 'Pre-flattened timeline. Table for speed; worker writes directly.';


-- ══════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ══════════════════════════════════════════════════════════════════
-- Run after executing this file to confirm all tables exist:
--
--   SHOW TABLES IN SCHEMA clinical_db.core;
--   -- expect: patient, document, entity, condition, medication,
--   --         observation, flag, contradiction, timeline_event
--
--   SHOW TABLES IN SCHEMA clinical_db.mart;
--   -- expect: patient_summary
--
--   DESC TABLE clinical_db.core.entity;
--   -- confirm: negated → BOOLEAN, null? = N (NOT NULL enforced)