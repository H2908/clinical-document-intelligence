-- overdue_referrals.sql — clinical-intelligence
-- View identifying referral documents with no follow-up activity.
-- Used by the flag agent / briefing to surface overdue referrals.
-- GTV definition: a referral document older than 90 days with no
-- newer document for the same patient.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE VIEW VW_OVERDUE_REFERRALS AS
SELECT
    d.document_id,
    d.patient_id,
    d.file_name,
    d.document_date,
    DATEDIFF('day', d.document_date, CURRENT_DATE()) AS days_since_referral
FROM core.document d
WHERE d.doc_type = 'referral'
  AND d.document_date < DATEADD('day', -90, CURRENT_DATE())
  -- no newer document for this patient
  AND NOT EXISTS (
      SELECT 1 FROM core.document d2
      WHERE d2.patient_id = d.patient_id
        AND d2.document_date > d.document_date
  );

-- ── Verification ─────────────────────────────────────────────────
--   SELECT * FROM VW_OVERDUE_REFERRALS;