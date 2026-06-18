-- ============================================================================
-- BNF code column for CORE.entity
-- Requested by: ML/Backend side (Phase 4 L2, FHIR bundle assembly)
-- Date: 2026-06-18
-- Estimated cost: < 1 second (DDL + SP update)
-- ============================================================================

-- Step 1. Add the nullable column.
ALTER TABLE clinical_db.core.entity
    ADD COLUMN bnf_code VARCHAR(15) NULL
        COMMENT 'BNF chapter+paragraph code for Drug entities (ontology/bnf_mapper.py).';

-- Step 2. Update SP_WRITE_ENTITIES to read bnf_code from the incoming
-- JSON and bind it to the new column.
--
-- Diff inside the procedure body (database/procedures/write_entities.sql):
--
--   In the INSERT statement, add bnf_code to the column list:
--     INSERT INTO clinical_db.core.entity (
--         entity_id, document_id, patient_id, entity_type, text,
--         start_offset, end_offset, negated, icd10_code,
--         bnf_code,                          -- NEW
--         normalised_value, created_at
--     )
--
--   In the binds array, add e.bnf_code in the matching slot:
--     binds: [
--         entity_id, DOCUMENT_ID, PATIENT_ID,
--         e.entity_type || null, e.text || null,
--         e.start_offset !== undefined ? e.start_offset : null,
--         e.end_offset !== undefined ? e.end_offset : null,
--         e.negated, e.icd10_code || null,
--         e.bnf_code || null,                -- NEW
--         e.normalised_value || null
--     ]

-- Step 3. Verification. After the migration, re-running cleanup_pat_test_01_entities.py
-- on the ML side will write Drug entities with bnf_code populated. To confirm:
--
--   SELECT COUNT(*) AS total_drugs,
--          COUNT(bnf_code) AS coded_drugs,
--          ROUND(COUNT(bnf_code) * 100.0 / COUNT(*), 1) AS coverage_pct
--   FROM clinical_db.core.entity
--   WHERE entity_type = 'Drug';
--
-- Expected after re-ingest: >90% coverage (the 105-row bnf_common.csv
-- includes every drug in the synthetic dataset).