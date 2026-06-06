-- refresh_summary.sql — clinical-intelligence
-- Stored procedure: SP_REFRESH_SUMMARY
-- Rebuilds the MART.patient_summary row for one patient.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_REFRESH_SUMMARY(patient_id VARCHAR) -> STRING
--
-- Called by: snowflake_writer.refresh_summary()
-- Writes to: MART.patient_summary
--
-- The briefing_agent (Claude) builds the actual summary JSON and the
-- worker passes it in — BUT the locked signature is (patient_id) only.
-- So this version assembles the summary FROM the CORE tables directly,
-- which keeps the read path fast and the signature simple.
--
-- Refresh rule:
--   1. Worker finishes a document → sets is_stale = TRUE (separate step)
--   2. This procedure rebuilds summary → sets is_stale = FALSE
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA mart;

CREATE OR REPLACE PROCEDURE SP_REFRESH_SUMMARY(
    PATIENT_ID  STRING
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!PATIENT_ID) throw new Error("patient_id is required");

    // Build the summary JSON from CORE tables using OBJECT_CONSTRUCT.
    // MERGE so it inserts if new, updates if exists.
    var stmt = snowflake.createStatement({
        sqlText: `
            MERGE INTO clinical_db.mart.patient_summary t
            USING (
                SELECT
                    p.patient_id,
                    OBJECT_CONSTRUCT(
                        'patient', OBJECT_CONSTRUCT(
                            'id',         p.patient_id,
                            'name',       p.name,
                            'dob',        p.dob,
                            'nhs_number', p.nhs_number,
                            'sex',        p.sex
                        ),
                        'conditions', (
                            SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
                                'name', c.name, 'icd10_code', c.icd10_code))
                            FROM clinical_db.core.condition c
                            WHERE c.patient_id = p.patient_id
                        ),
                        'medications', (
                            SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
                                'drug', m.drug, 'dose', m.dose,
                                'started', m.started, 'flag', m.flag_text))
                            FROM clinical_db.core.medication m
                            WHERE m.patient_id = p.patient_id
                        ),
                        'open_flags', (
                            SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
                                'severity', f.severity, 'category', f.category,
                                'description', f.description))
                            FROM clinical_db.core.flag f
                            WHERE f.patient_id = p.patient_id AND f.status = 'open'
                        )
                    ) AS summary
                FROM clinical_db.core.patient p
                WHERE p.patient_id = :1
            ) s
            ON t.patient_id = s.patient_id
            WHEN MATCHED THEN UPDATE SET
                t.summary = s.summary,
                t.generated_at = CURRENT_TIMESTAMP(),
                t.is_stale = FALSE
            WHEN NOT MATCHED THEN INSERT
                (patient_id, summary, generated_at, is_stale)
                VALUES (s.patient_id, s.summary, CURRENT_TIMESTAMP(), FALSE)
        `,
        binds: [PATIENT_ID]
    });

    stmt.execute();
    return "OK: summary refreshed for patient " + PATIENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_REFRESH_SUMMARY(STRING) TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- CALL SP_REFRESH_SUMMARY('pat_test001');
-- SELECT * FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_test001';
----SELECT * FROM clinical_db.mart.patient_summary WHERE patient_id = 'pat_test001';
----SELECT * FROM clinical_db.core.patient WHERE patient_id = 'pat_test001';

-------INSERT INTO clinical_db.core.patient (patient_id, name, dob, nhs_number, sex)
----VALUES ('pat_test001', 'Test Patient', '1970-03-12', '485 621 3847', 'M');