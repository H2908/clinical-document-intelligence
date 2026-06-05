-- active_flags.sql — clinical-intelligence
-- View backing GET /api/patients/{id}/flags (Flags page).
-- Matches the `flag` object shape in API_CONTRACT.md section 3.
-- Joins flag to its source document name for provenance.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE VIEW VW_ACTIVE_FLAGS AS
SELECT
    f.flag_id                AS id,
    f.patient_id,
    f.severity,
    f.category,
    f.description,
    f.source_document_id,
    d.file_name              AS source_document_name,  -- provenance
    f.status,
    f.created_at
FROM core.flag f
LEFT JOIN core.document d
    ON f.source_document_id = d.document_id;

-- ── Verification ─────────────────────────────────────────────────
--   SELECT * FROM VW_ACTIVE_FLAGS WHERE patient_id = 'pat_test001';