-- 02_staging.sql — clinical-intelligence
-- STAGING layer: flatten and type the RAW VARIANT, validate, dedupe.
-- Nothing here is a source of truth — it's the typed bridge between
-- raw.document_landing and core.document. Entities/flags/observations
-- do NOT pass through staging: they arrive via stored procedures from
-- the NLP pipeline and write straight to CORE.
-- ───────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA staging;

-- ── Typed document view over RAW ────────────────────────────────
-- One typed row per landed manifest. Implemented as a view so it
-- always reflects the latest RAW contents with no extra load step.
-- The worker / a MERGE task reads this to upsert into core.document.
CREATE OR REPLACE VIEW stg_document AS
SELECT
    raw_payload:document_id::STRING       AS document_id,
    raw_payload:patient_id::STRING        AS patient_id,
    raw_payload:s3_key::STRING            AS s3_key,
    raw_payload:doc_type::STRING          AS doc_type,
    raw_payload:source_filename::STRING   AS source_filename,
    raw_payload:content_type::STRING      AS content_type,
    raw_payload:size_bytes::NUMBER        AS size_bytes,
    raw_payload:uploaded_at::TIMESTAMP_NTZ AS uploaded_at,
    ingested_at
FROM raw.document_landing
-- guard against malformed manifests missing the required keys
WHERE raw_payload:document_id IS NOT NULL
  AND raw_payload:patient_id  IS NOT NULL
  AND raw_payload:s3_key      IS NOT NULL
-- if the same document_id lands twice, keep the most recent
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY raw_payload:document_id::STRING
    ORDER BY ingested_at DESC
) = 1;

-- ── Allowed document types (reference) ──────────────────────────
-- Small reference table the staging/validation layer can join against.
CREATE TABLE IF NOT EXISTS doc_type_ref (
    doc_type     VARCHAR PRIMARY KEY,
    description  VARCHAR
)
COMMENT = 'Valid document types for validation joins.';

MERGE INTO doc_type_ref t
USING (
    SELECT 'pdf'   AS doc_type, 'PDF clinical document'        AS description UNION ALL
    SELECT 'note',  'Free-text clinical note'                                 UNION ALL
    SELECT 'lab',   'Lab report (HL7 / CSV / PDF)'                            UNION ALL
    SELECT 'image', 'Medical image (e.g. X-ray)'
) s
ON t.doc_type = s.doc_type
WHEN NOT MATCHED THEN
    INSERT (doc_type, description) VALUES (s.doc_type, s.description);