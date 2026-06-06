-- contradiction_log.sql — clinical-intelligence
-- View backing GET /api/patients/{id}/contradictions (Contradictions page).
-- Matches the contradiction response in API_CONTRACT.md section 4.
-- Joins both documents (A and B) for their names and dates.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE VIEW VW_CONTRADICTION_LOG AS
SELECT
    c.contradiction_id       AS id,
    c.patient_id,
    c.severity,
    c.category,
    c.status,
    -- document A
    c.doc_a_id               AS document_a_id,
    da.file_name             AS document_a_name,
    da.document_date         AS document_a_date,
    c.doc_a_statement        AS document_a_statement,
    -- document B
    c.doc_b_id               AS document_b_id,
    db.file_name             AS document_b_name,
    db.document_date         AS document_b_date,
    c.doc_b_statement        AS document_b_statement,
    c.explanation,
    c.created_at
FROM core.contradiction c
LEFT JOIN core.document da ON c.doc_a_id = da.document_id
LEFT JOIN core.document db ON c.doc_b_id = db.document_id;

-- ── Verification ─────────────────────────────────────────────────
--   SELECT * FROM VW_CONTRADICTION_LOG WHERE patient_id = 'pat_test001';