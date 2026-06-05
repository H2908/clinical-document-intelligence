-- medication_reconciliation.sql — clinical-intelligence
-- View listing all medications per patient with their source document.
-- Used to spot duplicate or conflicting medications across documents.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE VIEW VW_MEDICATION_RECONCILIATION AS
SELECT
    m.medication_id,
    m.patient_id,
    m.drug,
    m.dose,
    m.started,
    m.flag_text,
    m.source_document_id,
    d.file_name              AS source_document_name,
    d.document_date          AS source_document_date,
    -- count how many times this drug appears for the patient
    COUNT(*) OVER (
        PARTITION BY m.patient_id, LOWER(m.drug)
    )                        AS occurrence_count
FROM core.medication m
LEFT JOIN core.document d
    ON m.source_document_id = d.document_id;

-- ── Verification ─────────────────────────────────────────────────
--   SELECT * FROM VW_MEDICATION_RECONCILIATION WHERE patient_id = 'pat_test001';