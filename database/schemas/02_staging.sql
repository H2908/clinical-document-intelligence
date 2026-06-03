-- 02_staging.sql — clinical-intelligence
-- STAGING layer: typed view over RAW.raw_documents.
-- Matches DB_SCHEMA.md v1 (locked).
-- ─────────────────────────────────────────────────────────────────
-- Note: entities, flags, contradictions, conditions, medications,
-- observations, and timeline_events do NOT pass through staging.
-- They arrive via stored procedures writing straight to CORE.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA staging;

-- ── stg_document ─────────────────────────────────────────────────
-- Typed view over RAW.raw_documents. Drops malformed rows and dedupes
-- on document_id. The worker reads this to upsert into CORE.document.
-- Implemented as a view so it always reflects latest RAW contents
-- with no extra load step.
CREATE OR REPLACE VIEW stg_document AS
SELECT
    document_id,
    patient_id,
    file_name,
    doc_type,
    source,
    document_date,
    s3_key,
    status,
    error_message,
    uploaded_at,
    processed_at
FROM raw.raw_documents
-- guard against rows missing required fields
WHERE document_id  IS NOT NULL
  AND patient_id   IS NOT NULL
  AND s3_key       IS NOT NULL
  AND file_name    IS NOT NULL
-- if same document_id appears twice, keep the most recent
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY document_id
    ORDER BY uploaded_at DESC
) = 1;

-- ── doc_type reference ───────────────────────────────────────────
-- Allowed document types. Used for validation joins.
-- Matches doc_type enum in API_CONTRACT.md and DB_SCHEMA.md.
CREATE TABLE IF NOT EXISTS doc_type_ref (
    doc_type    STRING  NOT NULL PRIMARY KEY,
    description STRING
)
COMMENT = 'Valid document types — validation reference.';

MERGE INTO doc_type_ref t
USING (
    SELECT 'referral'        AS doc_type, 'GP or specialist referral letter'  AS description UNION ALL
    SELECT 'clinic_letter',               'Outpatient clinic letter'                         UNION ALL
    SELECT 'gp_note',                     'GP consultation note'                             UNION ALL
    SELECT 'clinician_note',              'Free-text clinician note (typed directly)'        UNION ALL
    SELECT 'lab_report',                  'Lab report (HL7 / CSV / manual entry)'            UNION ALL
    SELECT 'imaging',                     'Medical image (X-ray, MRI, etc.)'
) s ON t.doc_type = s.doc_type
WHEN NOT MATCHED THEN
    INSERT (doc_type, description) VALUES (s.doc_type, s.description);