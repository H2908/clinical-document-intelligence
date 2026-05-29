-- 01_raw.sql — clinical-intelligence
-- RAW layer: Snowpipe lands here. Minimal typing, maximum fidelity.
-- The binary document stays in S3; what lands here is the upload
-- manifest (a small JSON written alongside the file) describing it.
-- ───────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA raw;

-- ── Document landing ────────────────────────────────────────────
-- Snowpipe COPY target. One row per uploaded document manifest.
-- raw_payload holds the whole JSON untyped; the metadata columns are
-- populated from Snowflake's METADATA$ pseudo-columns at COPY time so
-- we can trace every row back to its S3 object.
CREATE TABLE IF NOT EXISTS document_landing (
    raw_payload        VARIANT          NOT NULL,
    s3_file_name       VARCHAR,
    s3_file_row_number NUMBER,
    ingested_at        TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Snowpipe landing zone for upload manifests (JSON).';

-- ── HL7 landing (L2 — phase 3) ──────────────────────────────────
-- Raw HL7 messages land here as text; parsed downstream.
-- Stubbed now so the contract is fixed; populated in Phase 3.
CREATE TABLE IF NOT EXISTS raw_hl7 (
    raw_message        VARCHAR          NOT NULL,
    s3_file_name       VARCHAR,
    ingested_at        TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Raw HL7 v2 messages — L2 integration layer.';

-- ── Verification ────────────────────────────────────────────────
-- After an upload, this should return rows:
--   SELECT raw_payload:document_id::STRING AS document_id,
--          raw_payload:patient_id::STRING  AS patient_id,
--          raw_payload:s3_key::STRING      AS s3_key,
--          ingested_at
--   FROM document_landing
--   ORDER BY ingested_at DESC;