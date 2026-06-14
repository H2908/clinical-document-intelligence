-- test_gdpr_delete.sql — clinical-intelligence
-- GDPR-delete verification: proves SP_DELETE_PATIENT fully erases a
-- patient across EVERY table, and returns the S3 keys to delete.
--
-- Run as ACCOUNTADMIN.
--
-- Pattern:
--   1. SEED a test patient with data in every table
--   2. CONFIRM the data is there (pre-delete counts)
--   3. CALL SP_DELETE_PATIENT
--   4. VERIFY zero rows remain in every table (post-delete counts)
--   5. CHECK the returned s3_keys list is correct
-- ─────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE clinical_db;
USE SCHEMA core;

-- ══════════════════════════════════════════════════════════════════
-- STEP 1 — SEED: one test patient with data in every table
-- ══════════════════════════════════════════════════════════════════

-- clean any prior run
CALL SP_DELETE_PATIENT('pat_gdpr');

INSERT INTO patient (patient_id, name, dob, nhs_number, sex)
VALUES ('pat_gdpr', 'GDPR Test Patient', '1975-06-15', '111 222 3333', 'M');

INSERT INTO document (document_id, patient_id, file_name, doc_type, s3_key, document_date, status)
VALUES
  ('doc_gdpr1', 'pat_gdpr', 'GDPR_doc1.pdf', 'referral',
   'uploads/pat_gdpr/doc_gdpr1/GDPR_doc1.pdf', '2024-01-01', 'processed'),
  ('doc_gdpr2', 'pat_gdpr', 'GDPR_doc2.pdf', 'clinic_letter',
   'uploads/pat_gdpr/doc_gdpr2/GDPR_doc2.pdf', '2024-02-01', 'processed');

INSERT INTO entity (entity_id, document_id, patient_id, entity_type, text, start_offset, end_offset, negated)
VALUES ('ent_gdpr1', 'doc_gdpr1', 'pat_gdpr', 'Diagnosis', 'test diagnosis', 0, 14, FALSE);

INSERT INTO condition (condition_id, patient_id, name, source_document_id)
VALUES ('cond_gdpr1', 'pat_gdpr', 'Test condition', 'doc_gdpr1');

INSERT INTO medication (medication_id, patient_id, drug, dose, source_document_id)
VALUES ('med_gdpr1', 'pat_gdpr', 'Test drug', '1 g BD', 'doc_gdpr1');

INSERT INTO observation (observation_id, patient_id, test, value, unit, observation_date, source_document_id)
VALUES ('obs_gdpr1', 'pat_gdpr', 'eGFR', '42', 'mL/min', '2024-02-01', 'doc_gdpr1');

INSERT INTO flag (flag_id, patient_id, severity, category, description, source_document_id, status)
VALUES ('flag_gdpr1', 'pat_gdpr', 'HIGH', 'TEST', 'Test flag', 'doc_gdpr1', 'open');

INSERT INTO contradiction (contradiction_id, patient_id, severity, category,
        doc_a_id, doc_a_statement, doc_b_id, doc_b_statement, explanation, status)
VALUES ('con_gdpr1', 'pat_gdpr', 'HIGH', 'TEST',
        'doc_gdpr1', 'statement A', 'doc_gdpr2', 'statement B', 'test', 'open');

INSERT INTO timeline_event (event_id, patient_id, event_date, event_type, title, source_document_id)
VALUES ('evt_gdpr1', 'pat_gdpr', '2024-01-01', 'Diagnosis', 'Test event', 'doc_gdpr1');

INSERT INTO clinical_db.mart.patient_summary (patient_id, summary)
VALUES ('pat_gdpr', PARSE_JSON('{"patient":{"id":"pat_gdpr"}}'));


-- ══════════════════════════════════════════════════════════════════
-- STEP 2 — PRE-DELETE: confirm data exists in every table
-- ══════════════════════════════════════════════════════════════════
SELECT 'PRE-DELETE COUNTS' AS phase,
    (SELECT COUNT(*) FROM patient        WHERE patient_id = 'pat_gdpr') AS patient,
    (SELECT COUNT(*) FROM document       WHERE patient_id = 'pat_gdpr') AS document,
    (SELECT COUNT(*) FROM entity         WHERE patient_id = 'pat_gdpr') AS entity,
    (SELECT COUNT(*) FROM condition      WHERE patient_id = 'pat_gdpr') AS condition,
    (SELECT COUNT(*) FROM medication     WHERE patient_id = 'pat_gdpr') AS medication,
    (SELECT COUNT(*) FROM observation    WHERE patient_id = 'pat_gdpr') AS observation,
    (SELECT COUNT(*) FROM flag           WHERE patient_id = 'pat_gdpr') AS flag,
    (SELECT COUNT(*) FROM contradiction  WHERE patient_id = 'pat_gdpr') AS contradiction,
    (SELECT COUNT(*) FROM timeline_event WHERE patient_id = 'pat_gdpr') AS timeline_event,
    (SELECT COUNT(*) FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_gdpr') AS patient_summary;


-- ══════════════════════════════════════════════════════════════════
-- STEP 3 — DELETE: run the GDPR cascade
-- Returns deleted_counts + s3_keys. Check s3_keys has both documents.
-- ══════════════════════════════════════════════════════════════════
CALL SP_DELETE_PATIENT('pat_gdpr');


-- ══════════════════════════════════════════════════════════════════
-- STEP 4 — POST-DELETE: every count MUST be 0
-- ══════════════════════════════════════════════════════════════════
SELECT
    'POST-DELETE VERIFICATION' AS phase,
    CASE WHEN
        (SELECT COUNT(*) FROM patient        WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM document       WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM entity         WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM condition      WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM medication     WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM observation    WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM flag           WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM contradiction  WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM timeline_event WHERE patient_id = 'pat_gdpr') = 0 AND
        (SELECT COUNT(*) FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_gdpr') = 0
    THEN 'PASS — patient fully erased' ELSE 'FAIL — data remains' END AS result;

-- Per-table post-delete counts (all should be 0)
SELECT 'POST-DELETE COUNTS' AS phase,
    (SELECT COUNT(*) FROM patient        WHERE patient_id = 'pat_gdpr') AS patient,
    (SELECT COUNT(*) FROM document       WHERE patient_id = 'pat_gdpr') AS document,
    (SELECT COUNT(*) FROM entity         WHERE patient_id = 'pat_gdpr') AS entity,
    (SELECT COUNT(*) FROM condition      WHERE patient_id = 'pat_gdpr') AS condition,
    (SELECT COUNT(*) FROM medication     WHERE patient_id = 'pat_gdpr') AS medication,
    (SELECT COUNT(*) FROM observation    WHERE patient_id = 'pat_gdpr') AS observation,
    (SELECT COUNT(*) FROM flag           WHERE patient_id = 'pat_gdpr') AS flag,
    (SELECT COUNT(*) FROM contradiction  WHERE patient_id = 'pat_gdpr') AS contradiction,
    (SELECT COUNT(*) FROM timeline_event WHERE patient_id = 'pat_gdpr') AS timeline_event,
    (SELECT COUNT(*) FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_gdpr') AS patient_summary;

-- ══════════════════════════════════════════════════════════════════
-- STEP 5 — S3 KEYS
-- The CALL in Step 3 returned s3_keys. Confirm it listed:
--   uploads/pat_gdpr/doc_gdpr1/GDPR_doc1.pdf
--   uploads/pat_gdpr/doc_gdpr2/GDPR_doc2.pdf
-- These are what the API must delete from S3 to complete erasure.
-- ══════════════════════════════════════════════════════════════════