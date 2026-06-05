-- patient_360.sql — clinical-intelligence
-- View backing GET /api/patients/{id} (Overview page).
-- Matches API_CONTRACT.md section 4 response shape.
-- Joins patient + counts + conditions + medications + top flags.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

-- ── VW_PATIENT_360 ───────────────────────────────────────────────
-- One row per patient with aggregated stats.
-- The API reads this and assembles the nested conditions/meds/flags
-- arrays (or the API can do additional view reads — agreed in
-- API_CONTRACT.md).
CREATE OR REPLACE VIEW VW_PATIENT_360 AS
SELECT
    p.patient_id                                       AS id,
    p.name,
    p.dob,
    p.nhs_number,
    p.sex,
    DATEDIFF('year', p.dob, CURRENT_DATE())            AS age,
    p.last_updated,
    -- stats
    (SELECT COUNT(*) FROM core.document d
       WHERE d.patient_id = p.patient_id)              AS document_count,
    (SELECT COUNT(*) FROM core.flag f
       WHERE f.patient_id = p.patient_id
         AND f.status = 'open')                        AS open_flag_count,
    (SELECT COUNT(*) FROM core.contradiction c
       WHERE c.patient_id = p.patient_id
         AND c.status = 'open')                        AS contradiction_count
FROM core.patient p;

-- ── Verification ─────────────────────────────────────────────────
--   SELECT * FROM VW_PATIENT_360 LIMIT 5;