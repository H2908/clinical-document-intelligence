-- test_views.sql — clinical-intelligence
-- Automated tests for the five CORE views.
-- Each test inserts known data, queries the view, and checks the
-- result. Run as ACCOUNTADMIN (needs write access to seed test data).
--
-- Views tested:
--   VW_PATIENT_360
--   VW_ACTIVE_FLAGS
--   VW_CONTRADICTION_LOG
--   VW_OVERDUE_REFERRALS
--   VW_MEDICATION_RECONCILIATION
--
-- Pattern: each test uses a dedicated test patient (pat_vtest_*) so
-- it never collides with real data, and cleans up at the end.
-- ─────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE clinical_db;
USE SCHEMA core;

-- ══════════════════════════════════════════════════════════════════
-- SETUP — seed a known test patient with documents, flags, etc.
-- ══════════════════════════════════════════════════════════════════

-- clean any prior test run first
DELETE FROM flag           WHERE patient_id = 'pat_vtest';
DELETE FROM contradiction  WHERE patient_id = 'pat_vtest';
DELETE FROM medication     WHERE patient_id = 'pat_vtest';
DELETE FROM document       WHERE patient_id = 'pat_vtest';
DELETE FROM patient        WHERE patient_id = 'pat_vtest';

-- patient
INSERT INTO patient (patient_id, name, dob, nhs_number, sex)
VALUES ('pat_vtest', 'View Test Patient', '1980-01-15', '999 888 7777', 'F');

-- two documents (one an old referral for the overdue test)
INSERT INTO document (document_id, patient_id, file_name, doc_type, s3_key, document_date, status)
VALUES
  ('doc_vtest1', 'pat_vtest', 'Referral_old.pdf', 'referral',
   'uploads/pat_vtest/doc_vtest1/Referral_old.pdf', '2023-01-01', 'processed'),
  ('doc_vtest2', 'pat_vtest', 'Cardiology.pdf', 'clinic_letter',
   'uploads/pat_vtest/doc_vtest2/Cardiology.pdf', '2024-02-28', 'processed');

-- one open flag
INSERT INTO flag (flag_id, patient_id, severity, category, description, source_document_id, status)
VALUES ('flag_vtest1', 'pat_vtest', 'HIGH', 'ALLERGY CONFLICT',
        'Test flag for view testing', 'doc_vtest2', 'open');

-- one contradiction
INSERT INTO contradiction (contradiction_id, patient_id, severity, category,
        doc_a_id, doc_a_statement, doc_b_id, doc_b_statement, explanation, status)
VALUES ('con_vtest1', 'pat_vtest', 'HIGH', 'ALLERGY',
        'doc_vtest1', 'NKDA recorded', 'doc_vtest2', 'Penicillin allergy',
        'Documents disagree on allergy', 'open');

-- two medications (same drug twice → duplicate detection)
INSERT INTO medication (medication_id, patient_id, drug, dose, source_document_id)
VALUES
  ('med_vtest1', 'pat_vtest', 'Metformin', '1 g BD', 'doc_vtest1'),
  ('med_vtest2', 'pat_vtest', 'Metformin', '500 mg OD', 'doc_vtest2');


-- ══════════════════════════════════════════════════════════════════
-- TEST 1 — VW_PATIENT_360
-- Expect: 1 row, document_count=2, open_flag_count=1, contradiction_count=1
-- ══════════════════════════════════════════════════════════════════
SELECT
    'TEST 1: VW_PATIENT_360' AS test_name,
    CASE WHEN document_count = 2
          AND open_flag_count = 1
          AND contradiction_count = 1
         THEN 'PASS' ELSE 'FAIL' END AS result,
    document_count, open_flag_count, contradiction_count
FROM VW_PATIENT_360
WHERE id = 'pat_vtest';


-- ══════════════════════════════════════════════════════════════════
-- TEST 2 — VW_ACTIVE_FLAGS
-- Expect: 1 row, with source_document_name joined (not null)
-- ══════════════════════════════════════════════════════════════════
SELECT
    'TEST 2: VW_ACTIVE_FLAGS' AS test_name,
    CASE WHEN COUNT(*) = 1
          AND MAX(source_document_name) = 'Cardiology.pdf'
         THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS flag_rows
FROM VW_ACTIVE_FLAGS
WHERE patient_id = 'pat_vtest';


-- ══════════════════════════════════════════════════════════════════
-- TEST 3 — VW_CONTRADICTION_LOG
-- Expect: 1 row with both document names joined
-- ══════════════════════════════════════════════════════════════════
SELECT
    'TEST 3: VW_CONTRADICTION_LOG' AS test_name,
    CASE WHEN COUNT(*) = 1
          AND MAX(document_a_name) = 'Referral_old.pdf'
          AND MAX(document_b_name) = 'Cardiology.pdf'
         THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS contradiction_rows
FROM VW_CONTRADICTION_LOG
WHERE patient_id = 'pat_vtest';


-- ══════════════════════════════════════════════════════════════════
-- TEST 4 — VW_OVERDUE_REFERRALS
-- Expect: doc_vtest1 (referral from 2023, >90 days, has a newer doc)
-- NOTE: the view excludes referrals that HAVE a newer document.
-- doc_vtest2 (2024) is newer, so doc_vtest1 should NOT appear.
-- This tests the "no follow-up" logic correctly returns 0 here.
-- ══════════════════════════════════════════════════════════════════
SELECT
    'TEST 4: VW_OVERDUE_REFERRALS' AS test_name,
    CASE WHEN COUNT(*) = 0
         THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS overdue_rows,
    'doc_vtest1 has a newer doc so is NOT overdue' AS note
FROM VW_OVERDUE_REFERRALS
WHERE patient_id = 'pat_vtest';


-- ══════════════════════════════════════════════════════════════════
-- TEST 5 — VW_MEDICATION_RECONCILIATION
-- Expect: 2 rows, both Metformin, occurrence_count=2 (duplicate detected)
-- ══════════════════════════════════════════════════════════════════
SELECT
    'TEST 5: VW_MEDICATION_RECONCILIATION' AS test_name,
    CASE WHEN COUNT(*) = 2
          AND MAX(occurrence_count) = 2
         THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS med_rows, MAX(occurrence_count) AS max_occurrence
FROM VW_MEDICATION_RECONCILIATION
WHERE patient_id = 'pat_vtest';


-- ══════════════════════════════════════════════════════════════════
-- CLEANUP — remove all test data
-- ══════════════════════════════════════════════════════════════════
DELETE FROM flag           WHERE patient_id = 'pat_vtest';
DELETE FROM contradiction  WHERE patient_id = 'pat_vtest';
DELETE FROM medication     WHERE patient_id = 'pat_vtest';
DELETE FROM document       WHERE patient_id = 'pat_vtest';
DELETE FROM patient        WHERE patient_id = 'pat_vtest';

-- All five tests should show result = 'PASS'.