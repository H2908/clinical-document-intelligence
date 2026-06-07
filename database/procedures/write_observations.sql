-- write_observations.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_OBSERVATIONS
-- Bulk inserts lab values / observations into CORE.observation.
--
-- Matches the ACTUAL observation table columns:
--   observation_id, patient_id, test, value, unit,
--   observation_date, source_document_id, created_at
--
-- Signature:
--   SP_WRITE_OBSERVATIONS(document_id VARCHAR, patient_id VARCHAR, observations VARIANT) -> STRING
--   (document_id maps to source_document_id in the table)
--
-- Lab-row JSON shape (from API_CONTRACT.md `result`):
--   {
--     "test":  "eGFR",
--     "value": "42",            ← STRING (handles "32%", "<0.1")
--     "unit":  "mL/min/1.73m2",
--     "date":  "2026-05-20"     ← or "observation_date"; both accepted
--   }
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_WRITE_OBSERVATIONS(
    DOCUMENT_ID   STRING,
    PATIENT_ID    STRING,
    OBSERVATIONS  VARIANT
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!DOCUMENT_ID)  throw new Error("document_id is required");
    if (!PATIENT_ID)   throw new Error("patient_id is required");
    if (!OBSERVATIONS) throw new Error("observations array is required");

    var observations = OBSERVATIONS;
    if (observations.length === 0) {
        return "OK: 0 observations written";
    }

    var inserted = 0;

    for (var i = 0; i < observations.length; i++) {
        var o = observations[i];

        if (!o.test) {
            throw new Error("observation at index " + i + " is missing 'test'");
        }
        if (o.value === undefined || o.value === null) {
            throw new Error("observation at index " + i + " is missing 'value'");
        }

        var observation_id = "obs_" + DOCUMENT_ID.replace("doc_", "") + "_" + Date.now() + "_" + i;

        // accept either "observation_date" or "date" from the caller
        var obs_date = (o.observation_date !== undefined) ? o.observation_date : o.date;

        var stmt = snowflake.createStatement({
            sqlText: `
                INSERT INTO clinical_db.core.observation (
                    observation_id, patient_id, test, value, unit,
                    observation_date, source_document_id, created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, CURRENT_TIMESTAMP()
                )
            `,
            binds: [
                observation_id,
                PATIENT_ID,
                o.test,
                String(o.value),        // force string
                o.unit       || null,
                obs_date     || null,
                DOCUMENT_ID             // maps to source_document_id
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " observations written for document " + DOCUMENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_WRITE_OBSERVATIONS(STRING, STRING, VARIANT) TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- CALL SP_WRITE_OBSERVATIONS('doc_test001', 'pat_test001', PARSE_JSON('[
--   {"test":"eGFR","value":"44","unit":"mL/min/1.73m2","date":"2026-05-20"},
--   {"test":"HbA1c","value":"59","unit":"mmol/mol","date":"2026-05-20"}
-- ]'));
--
-- SELECT * FROM clinical_db.core.observation WHERE patient_id = 'pat_test001';