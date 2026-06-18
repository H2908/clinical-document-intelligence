-- write_flags.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_FLAGS
-- Bulk inserts risk flags into CORE.flag.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_WRITE_FLAGS(patient_id VARCHAR, flags VARIANT) -> STRING
--
-- Called by: snowflake_writer.write_flags() / flag_agent
-- Writes to: CORE.flag
--
-- UPDATED: now also writes provenance_hash — an audit fingerprint of
-- the flag's source, computed by flag_agent. Nullable and backwards
-- compatible: flags without a hash still write fine.
--
-- Each object in the flags array:
--   {
--     "severity":           "HIGH|MEDIUM|LOW",
--     "category":           "ALLERGY CONFLICT",
--     "description":        "doctor-readable text",
--     "source_document_id": "doc_77ab",      ← required (provenance)
--     "provenance_hash":    "a1b2c3..."      ← NEW, nullable (audit hash)
--   }
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_WRITE_FLAGS(
    PATIENT_ID  STRING,
    FLAGS       VARIANT
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!PATIENT_ID) throw new Error("patient_id is required");
    if (!FLAGS)      throw new Error("flags array is required");

    var flags = FLAGS;
    if (flags.length === 0) {
        return "OK: 0 flags written";
    }

    var inserted = 0;

    for (var i = 0; i < flags.length; i++) {
        var f = flags[i];

        // Provenance is required — every flag must trace to a document
        if (!f.source_document_id) {
            throw new Error("flag at index " + i + " is missing source_document_id (provenance required)");
        }

        var flag_id = "flag_" + PATIENT_ID.replace("pat_", "") + "_" + Date.now() + "_" + i;

        var stmt = snowflake.createStatement({
            sqlText: `
                INSERT INTO clinical_db.core.flag (
                    flag_id, patient_id, severity, category,
                    description, source_document_id, provenance_hash,
                    status, created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, 'open', CURRENT_TIMESTAMP()
                )
            `,
            binds: [
                flag_id,
                PATIENT_ID,
                f.severity           || null,
                f.category           || null,
                f.description        || null,
                f.source_document_id,
                f.provenance_hash    || null     // NEW — nullable audit hash
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " flags written for patient " + PATIENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_WRITE_FLAGS(STRING, VARIANT) TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- DELETE FROM clinical_db.core.flag WHERE patient_id = 'pat_test001';
-- CALL SP_WRITE_FLAGS('pat_test001', PARSE_JSON('[
--   {"severity":"HIGH","category":"ALLERGY CONFLICT",
--    "description":"Test flag with hash","source_document_id":"doc_test001",
--    "provenance_hash":"a1b2c3d4e5f6"}
-- ]'));
-- SELECT flag_id, description, provenance_hash FROM clinical_db.core.flag
-- WHERE patient_id = 'pat_test001';