-- 01_raw.sql — clinical-intelligence
-- RAW layer: landing zone and job queue.
-- Matches DB_SCHEMA.md v1 (locked).
-- Run as: ACCOUNTADMIN or clinical_role
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA raw;

-- ── raw_documents ────────────────────────────────────────────────
-- Upload landing record AND the GTV job queue (status column).
-- One row per uploaded document. Snowpipe writes here on upload.
-- The worker reads status = 'pending', processes, then updates to
-- 'processed' or 'failed'.
CREATE TABLE IF NOT EXISTS raw_documents (
    document_id     STRING          NOT NULL,   -- PK. doc_<uuid>. Set by API.
    patient_id      STRING          NOT NULL,   -- FK → CORE.patient
    file_name       STRING          NOT NULL,   -- original filename
    doc_type        STRING          NOT NULL,   -- referral|clinic_letter|gp_note|
                                                -- clinician_note|lab_report|imaging
    source          STRING,                     -- e.g. "Trust EPR". Nullable.
    document_date   DATE,                       -- clinical date of the document
    s3_key          STRING          NOT NULL,   -- location of raw file in S3
    status          STRING          NOT NULL DEFAULT 'pending',
                                                -- pending|processing|processed|failed
    error_message   STRING,                     -- set when status = failed. Nullable.
    uploaded_at     TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    processed_at    TIMESTAMP_NTZ,              -- set when worker finishes. Nullable.
    PRIMARY KEY (document_id)
)
COMMENT = 'Upload landing record and GTV job queue. One row per document.';

-- ── nlp_output ───────────────────────────────────────────────────
-- Raw NLP JSON stored verbatim before unpacking into CORE.
-- One row per document. Keeping this enables reprocessing without
-- re-running the NLP pipeline.
CREATE TABLE IF NOT EXISTS nlp_output (
    document_id     STRING          NOT NULL,   -- PK / FK → raw_documents
    patient_id      STRING          NOT NULL,   -- FK → CORE.patient
    payload         VARIANT         NOT NULL,   -- full NLP JSON (see NLP_OUTPUT.md)
    nlp_version     STRING          NOT NULL,   -- version of pipeline that produced it
    created_at      TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (document_id)
)
COMMENT = 'Verbatim NLP JSON blob. One row per document. Enables reprocessing.';

-- ── Verification ─────────────────────────────────────────────────
-- After an upload, confirm rows land here:
--   SELECT document_id, patient_id, status, uploaded_at
--   FROM raw_documents
--   ORDER BY uploaded_at DESC
--   LIMIT 10;