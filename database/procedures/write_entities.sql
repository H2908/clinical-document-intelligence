-- write_entities.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_ENTITIES
-- Takes NLP-extracted entities for one document and bulk inserts
-- them into CORE.entity.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_WRITE_ENTITIES(document_id STRING, patient_id STRING, entities VARIANT)
--
-- Called by: snowflake_writer.py
-- Writes to: CORE.entity
--
-- Each object in the entities array matches NLP_OUTPUT.md shape:
--   {
--     "entity_type":     "Diagnosis|Drug|Date|Conflict",
--     "text":            "exact span text",
--     "start_offset":    108,
--     "end_offset":      130,
--     "negated":         false,   ← PATIENT-SAFETY CRITICAL
--     "icd10_code":      "I42.0", ← nullable
--     "normalised_value": null    ← nullable
--   }
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_WRITE_ENTITIES(
    DOCUMENT_ID  STRING,
    PATIENT_ID   STRING,
    ENTITIES     VARIANT
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    // ── Validation ───────────────────────────────────────────────
    if (!DOCUMENT_ID) throw new Error("document_id is required");
    if (!PATIENT_ID)  throw new Error("patient_id is required");
    if (!ENTITIES)    throw new Error("entities array is required");

    var entities = ENTITIES;

    // Empty array is valid (document had no entities)
    if (entities.length === 0) {
        return "OK: 0 entities written";
    }

    // ── Build INSERT statement ────────────────────────────────────
    // One INSERT per entity. Snowflake JS procs don't support
    // bulk binding, so we loop and execute individually.
    // For GTV scale this is fine; revisit for high volume.
    var inserted = 0;

    for (var i = 0; i < entities.length; i++) {
        var e = entities[i];

        // Validate negated is explicitly set — patient-safety critical
        if (e.negated === undefined || e.negated === null) {
            throw new Error(
                "entity at index " + i + " is missing negated field — " +
                "this is patient-safety critical and must always be set"
            );
        }

        // Generate entity_id: ent_<uuid style from document + index>
        var entity_id = "ent_" + DOCUMENT_ID.replace("doc_", "") + "_" + i;

        var stmt = snowflake.createStatement({
            sqlText: `
                INSERT INTO clinical_db.core.entity (
                    entity_id,
                    document_id,
                    patient_id,
                    entity_type,
                    text,
                    start_offset,
                    end_offset,
                    negated,
                    icd10_code,
                    normalised_value,
                    created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, :8, :9, :10,
                    CURRENT_TIMESTAMP()
                )
            `,
            binds: [
                entity_id,
                DOCUMENT_ID,
                PATIENT_ID,
                e.entity_type        || null,
                e.text               || null,
                e.start_offset       !== undefined ? e.start_offset : null,
                e.end_offset         !== undefined ? e.end_offset   : null,
                e.negated,                           // never null — validated above
                e.icd10_code         || null,
                e.normalised_value   || null
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " entities written for document " + DOCUMENT_ID;
$$;

-- ── Grant execute to clinical_role ───────────────────────────────
GRANT USAGE ON PROCEDURE SP_WRITE_ENTITIES(STRING, STRING, VARIANT)
    TO ROLE clinical_role;

-- ── Verification — test call ─────────────────────────────────────
-- Run this after creating the procedure to confirm it works.
-- Uses the test document we uploaded via Snowpipe earlier.
--
-- CALL SP_WRITE_ENTITIES(
--     'doc_test001',
--     'pat_test001',
--     PARSE_JSON('[
--         {
--             "entity_type": "Diagnosis",
--             "text": "dilated cardiomyopathy",
--             "start_offset": 108,
--             "end_offset": 130,
--             "negated": false,
--             "icd10_code": "I42.0",
--             "normalised_value": null
--         },
--         {
--             "entity_type": "Drug",
--             "text": "bisoprolol 2.5 mg",
--             "start_offset": 150,
--             "end_offset": 167,
--             "negated": false,
--             "icd10_code": null,
--             "normalised_value": "bisoprolol"
--         }
--     ]')
-- );
--
-- Then confirm entities landed:
-- SELECT * FROM clinical_db.core.entity
-- WHERE document_id = 'doc_test001';