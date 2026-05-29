-- 03_core.sql — clinical-intelligence
-- CORE layer: the source of truth. patient, document, entity,
-- observation, flag, contradiction.
--
-- Key contract decisions (confirm with ML member before committing):
--   * patient_id / document_id are app-generated STRINGs (UUIDs) —
--     supplied in the {document_id, patient_id, s3_key} job payload.
--   * entity_id / observation_id / flag_id / contradiction_id are
--     DB-generated via IDENTITY (the write happens inside Snowflake).
--   * entity.is_negated is NOT NULL — negation is patient-safety
--     critical, so it must always be explicit, never assumed.
--   * Snowflake does not enforce PK/FK, but they are declared as
--     documentation and as hints to the optimizer.
-- ───────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

-- ── patient ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient (
    patient_id    STRING        NOT NULL PRIMARY KEY,
    mrn           STRING,                    -- medical record number (business key)
    first_name    STRING,
    last_name     STRING,
    date_of_birth DATE,
    sex           STRING,                    -- 'M' | 'F' | 'O' | NULL
    created_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'One row per patient.';

-- ── document ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document (
    document_id     STRING        NOT NULL PRIMARY KEY,
    patient_id      STRING        NOT NULL,
    s3_key          STRING        NOT NULL,
    doc_type        STRING,                  -- pdf | note | lab | image
    source_filename STRING,
    status          STRING        DEFAULT 'uploaded', -- uploaded|parsing|processed|failed
    uploaded_at     TIMESTAMP_NTZ,
    processed_at    TIMESTAMP_NTZ,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (patient_id) REFERENCES patient (patient_id)
)
COMMENT = 'One row per uploaded document. status tracks the worker pipeline.';

-- ── entity ──────────────────────────────────────────────────────
-- Output of the NLP pipeline (medical_ner + negation + date_normaliser).
-- Written by write_entities(). cui is nullable (filled by L2 mapping).
CREATE TABLE IF NOT EXISTS entity (
    entity_id       NUMBER        IDENTITY(1,1) PRIMARY KEY,
    document_id     STRING        NOT NULL,
    patient_id      STRING        NOT NULL,   -- denormalised for fast patient queries
    entity_text     STRING        NOT NULL,   -- surface form from the document
    entity_type     STRING        NOT NULL,   -- problem|medication|test|anatomy|...
    cui             STRING,                    -- UMLS concept id (L2, nullable)
    is_negated      BOOLEAN       NOT NULL,    -- from negation_detector — never assume
    normalized_date DATE,                      -- from date_normaliser (nullable)
    char_start      NUMBER,                    -- offset in cleaned source text
    char_end        NUMBER,
    confidence      FLOAT,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (document_id) REFERENCES document (document_id),
    FOREIGN KEY (patient_id)  REFERENCES patient  (patient_id)
)
COMMENT = 'Extracted medical entities. is_negated is mandatory (patient safety).';

-- ── observation ─────────────────────────────────────────────────
-- Structured lab / measurement rows (lab_parser output).
-- Written by write_entities() or a dedicated lab write path.
CREATE TABLE IF NOT EXISTS observation (
    observation_id   NUMBER        IDENTITY(1,1) PRIMARY KEY,
    patient_id       STRING        NOT NULL,
    document_id      STRING        NOT NULL,
    observation_type STRING        NOT NULL,   -- e.g. 'glucose', 'hba1c'
    code             STRING,                    -- LOINC / local code (nullable)
    value_numeric    FLOAT,
    value_text       STRING,                    -- for non-numeric results
    unit             STRING,
    ref_range_low    FLOAT,
    ref_range_high   FLOAT,
    abnormal_flag    STRING,                    -- 'H' | 'L' | 'N' | NULL
    observed_at      TIMESTAMP_NTZ,
    created_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (patient_id)  REFERENCES patient  (patient_id),
    FOREIGN KEY (document_id) REFERENCES document (document_id)
)
COMMENT = 'Structured lab/measurement rows.';

-- ── flag ────────────────────────────────────────────────────────
-- Risk flags and overdue referrals (flag_agent output).
-- Written by write_flags().
CREATE TABLE IF NOT EXISTS flag (
    flag_id          NUMBER        IDENTITY(1,1) PRIMARY KEY,
    patient_id       STRING        NOT NULL,
    document_id      STRING,                    -- nullable: may be cross-document
    flag_type        STRING        NOT NULL,    -- risk | overdue_referral | ...
    severity         STRING        NOT NULL,    -- low | medium | high | critical
    title            STRING        NOT NULL,
    description      STRING,
    status           STRING        DEFAULT 'active', -- active | resolved | dismissed
    created_by_agent STRING,                     -- which agent raised it
    created_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    resolved_at      TIMESTAMP_NTZ,
    FOREIGN KEY (patient_id)  REFERENCES patient  (patient_id),
    FOREIGN KEY (document_id) REFERENCES document (document_id)
)
COMMENT = 'Clinical risk flags / overdue referrals.';

-- ── contradiction ───────────────────────────────────────────────
-- Conflicts found across documents (contradiction_agent output).
-- Written by write_contradictions(). References two entities/docs.
CREATE TABLE IF NOT EXISTS contradiction (
    contradiction_id NUMBER        IDENTITY(1,1) PRIMARY KEY,
    patient_id       STRING        NOT NULL,
    document_id_a    STRING,                    -- the two sources in conflict
    document_id_b    STRING,
    claim_a          STRING        NOT NULL,    -- what source A asserts
    claim_b          STRING        NOT NULL,    -- what source B asserts
    contradiction_type STRING,                  -- medication | diagnosis | allergy | ...
    severity         STRING,                    -- low | medium | high | critical
    status           STRING        DEFAULT 'active',
    created_by_agent STRING,
    created_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (patient_id)   REFERENCES patient  (patient_id),
    FOREIGN KEY (document_id_a) REFERENCES document (document_id),
    FOREIGN KEY (document_id_b) REFERENCES document (document_id)
)
COMMENT = 'Cross-document clinical contradictions.';