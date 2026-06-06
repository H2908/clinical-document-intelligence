-- delete_patient.sql — clinical-intelligence
-- Stored procedure: SP_DELETE_PATIENT
-- GDPR right-to-erasure. Permanently deletes a patient and ALL
-- their data across every table, then returns the S3 keys so the
-- caller can delete the actual files from S3.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_DELETE_PATIENT(patient_id VARCHAR) -> VARIANT
--
-- Returns: a JSON array of s3_keys that must be deleted from S3.
--
-- Called by: snowflake_writer / api delete endpoint
--
-- ⚠️  THIS IS PERMANENT. There is no undo.
--
-- Deletion order (children first, parent last — FK-safe):
--   1. entity, observation, flag, contradiction,
--      condition, medication, timeline_event   (children of document/patient)
--   2. document
--   3. mart.patient_summary
--   4. patient                                  (parent — last)
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_DELETE_PATIENT(
    PATIENT_ID  STRING
)
RETURNS VARIANT
LANGUAGE JAVASCRIPT
AS
$$
    if (!PATIENT_ID) throw new Error("patient_id is required");

    // ── Step 1: collect S3 keys BEFORE deleting anything ──────────
    // Once we delete the document rows we lose the s3_keys, so grab
    // them first and return them at the end.
    var s3_keys = [];
    var keyStmt = snowflake.createStatement({
        sqlText: `SELECT s3_key
                  FROM clinical_db.core.document
                  WHERE patient_id = :1`,
        binds: [PATIENT_ID]
    });
    var keyResult = keyStmt.execute();
    while (keyResult.next()) {
        s3_keys.push(keyResult.getColumnValue(1));
    }

    // ── Step 2: delete children (anything referencing patient/doc) ─
    // Order within this group doesn't matter — none reference each other.
    var childTables = [
        "entity",
        "observation",
        "flag",
        "contradiction",
        "condition",
        "medication",
        "timeline_event"
    ];

    var deleted_counts = {};

    for (var i = 0; i < childTables.length; i++) {
        var tbl = childTables[i];
        var stmt = snowflake.createStatement({
            sqlText: `DELETE FROM clinical_db.core.` + tbl + `
                      WHERE patient_id = :1`,
            binds: [PATIENT_ID]
        });
        var r = stmt.execute();
        r.next();
        deleted_counts[tbl] = r.getColumnValue(1);   // rows deleted
    }

    // ── Step 3: delete documents (after entities etc. are gone) ────
    var docStmt = snowflake.createStatement({
        sqlText: `DELETE FROM clinical_db.core.document
                  WHERE patient_id = :1`,
        binds: [PATIENT_ID]
    });
    var dr = docStmt.execute();
    dr.next();
    deleted_counts["document"] = dr.getColumnValue(1);

    // ── Step 4: delete the briefing summary in MART ────────────────
    var summaryStmt = snowflake.createStatement({
        sqlText: `DELETE FROM clinical_db.mart.patient_summary
                  WHERE patient_id = :1`,
        binds: [PATIENT_ID]
    });
    var sr = summaryStmt.execute();
    sr.next();
    deleted_counts["patient_summary"] = sr.getColumnValue(1);

    // ── Step 5: finally delete the patient (parent) ────────────────
    var patStmt = snowflake.createStatement({
        sqlText: `DELETE FROM clinical_db.core.patient
                  WHERE patient_id = :1`,
        binds: [PATIENT_ID]
    });
    var pr = patStmt.execute();
    pr.next();
    deleted_counts["patient"] = pr.getColumnValue(1);

    // ── Step 6: return what happened + S3 keys to delete ───────────
    return {
        "patient_id":     PATIENT_ID,
        "deleted":        true,
        "deleted_counts": deleted_counts,
        "s3_keys":        s3_keys      // caller deletes these from S3
    };
$$;

GRANT USAGE ON PROCEDURE SP_DELETE_PATIENT(STRING) TO ROLE clinical_role;

-- ── Test (CAREFUL — this permanently deletes) ────────────────────
-- Use a throwaway test patient, NOT real data.
--
-- CALL SP_DELETE_PATIENT('pat_test001');
--
-- Returns something like:
-- {
--   "patient_id": "pat_test001",
--   "deleted": true,
--   "deleted_counts": { "entity": 2, "flag": 1, "document": 0, "patient": 1, ... },
--   "s3_keys": [ "uploads/pat_test001/doc_x/file.pdf" ]
-- }
--
-- Then confirm everything is gone:
-- SELECT COUNT(*) FROM clinical_db.core.entity   WHERE patient_id = 'pat_test001';  -- 0
-- SELECT COUNT(*) FROM clinical_db.core.patient  WHERE patient_id = 'pat_test001';  -- 0