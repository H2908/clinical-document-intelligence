-- write_entities.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_ENTITIES
-- Bulk inserts NLP-extracted entities into CORE.entity.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_WRITE_ENTITIES(document_id STRING, patient_id STRING, entities VARIANT)
--
-- Called by: snowflake_writer.py
-- Writes to: CORE.entity
--
-- UPDATED: now also writes bnf_code (British National Formulary drug
-- code). Nullable — only drug entities carry one. Backwards compatible.
--
-- NOTE on negated: Snowflake JS procs can't bind booleans, so we inject
-- the boolean as a TRUE/FALSE string literal directly into the SQL.
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
    if (!DOCUMENT_ID) throw new Error("document_id is required");
    if (!PATIENT_ID)  throw new Error("patient_id is required");
    if (!ENTITIES)    throw new Error("entities array is required");

    var entities = ENTITIES;

    if (entities.length === 0) {
        return "OK: 0 entities written";
    }

    var inserted = 0;

    for (var i = 0; i < entities.length; i++) {
        var e = entities[i];

        // negated is patient-safety critical — must be explicitly set
        if (e.negated === undefined || e.negated === null) {
            throw new Error("entity at index " + i + " is missing negated field");
        }

        var entity_id = "ent_" + DOCUMENT_ID.replace("doc_", "") + "_" + i;

        // Convert boolean to string literal for Snowflake (can't bind booleans)
        var negated_str = e.negated ? "TRUE" : "FALSE";

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
                    bnf_code,
                    created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, ` + negated_str + `, :8, :9, :10,
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
                e.icd10_code         || null,
                e.normalised_value   || null,
                e.bnf_code           || null        // NEW — nullable, drugs only
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " entities written for document " + DOCUMENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_WRITE_ENTITIES(STRING, STRING, VARIANT)
    TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- DELETE FROM clinical_db.core.entity WHERE document_id = 'doc_test001';
-- CALL SP_WRITE_ENTITIES('doc_test001', 'pat_test001', PARSE_JSON('[
--   {"entity_type":"Drug","text":"bisoprolol 2.5 mg","start_offset":150,
--    "end_offset":167,"negated":false,"icd10_code":null,
--    "normalised_value":"bisoprolol","bnf_code":"0205051R0"}
-- ]'));
-- SELECT entity_id, text, bnf_code FROM clinical_db.core.entity
-- WHERE document_id = 'doc_test001';