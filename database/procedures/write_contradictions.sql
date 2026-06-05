-- write_contradictions.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_CONTRADICTIONS
-- Bulk inserts cross-document contradictions into CORE.contradiction.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_WRITE_CONTRADICTIONS(patient_id VARCHAR, contradictions VARIANT) -> STRING
--
-- Called by: snowflake_writer.write_contradictions()
-- Writes to: CORE.contradiction
--
-- Each object matches NLP_OUTPUT.md:
--   {
--     "severity":          "HIGH|MEDIUM|LOW",
--     "category":          "ALLERGY",
--     "doc_a_id":          "doc_11",
--     "doc_a_statement":   "NKDA - no known drug allergies.",
--     "doc_b_id":          "doc_77ab",
--     "doc_b_statement":   "Penicillin allergy - rash 2019.",
--     "explanation":       "reasoning + recommendation"
--   }
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_WRITE_CONTRADICTIONS(
    PATIENT_ID       STRING,
    CONTRADICTIONS   VARIANT
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!PATIENT_ID)     throw new Error("patient_id is required");
    if (!CONTRADICTIONS) throw new Error("contradictions array is required");

    var contradictions = CONTRADICTIONS;
    if (contradictions.length === 0) {
        return "OK: 0 contradictions written";
    }

    var inserted = 0;

    for (var i = 0; i < contradictions.length; i++) {
        var c = contradictions[i];

        var contradiction_id = "con_" + PATIENT_ID.replace("pat_", "") + "_" + Date.now() + "_" + i;

        var stmt = snowflake.createStatement({
            sqlText: `
                INSERT INTO clinical_db.core.contradiction (
                    contradiction_id, patient_id, severity, category,
                    doc_a_id, doc_a_statement, doc_b_id, doc_b_statement,
                    explanation, status, created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, :8, :9, 'open', CURRENT_TIMESTAMP()
                )
            `,
            binds: [
                contradiction_id,
                PATIENT_ID,
                c.severity         || null,
                c.category         || null,
                c.doc_a_id         || null,
                c.doc_a_statement  || null,
                c.doc_b_id         || null,
                c.doc_b_statement  || null,
                c.explanation      || null
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " contradictions written for patient " + PATIENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_WRITE_CONTRADICTIONS(STRING, VARIANT) TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- CALL SP_WRITE_CONTRADICTIONS('pat_test001', PARSE_JSON('[
--   {"severity":"HIGH","category":"ALLERGY",
--    "doc_a_id":"doc_test001","doc_a_statement":"NKDA recorded.",
--    "doc_b_id":"doc_test002","doc_b_statement":"Penicillin allergy.",
--    "explanation":"Documents disagree on allergy status."}
-- ]'));