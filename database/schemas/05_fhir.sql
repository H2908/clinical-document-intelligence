-- 05_fhir.sql — clinical-intelligence
-- FHIR layer: storage for FHIR R4 formatted patient data.
--
-- DE owns this file (the storage). The ML partner owns the builder
-- (fhir/fhir_builder.py) and the endpoint (api/routes/fhir.py).
--
-- FHIR R4 represents a patient as a "Bundle" — a JSON document holding
-- resources (Patient, Condition, MedicationStatement, Observation,
-- AllergyIntolerance, etc). We store that Bundle verbatim as VARIANT,
-- one row per patient, rebuilt when the patient's data changes.
--
-- Run AFTER 03_core.sql. Run as ACCOUNTADMIN or clinical_role.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA mart;

-- ── fhir_patient_bundle ──────────────────────────────────────────
-- One FHIR R4 Bundle per patient, stored as VARIANT.
-- GET /api/patients/{id}/fhir reads this. The fhir_builder writes it.
--
-- Why MART not CORE? It's a derived/exported representation of the
-- CORE data, same family as patient_summary — a read model, not a
-- source of truth.
CREATE TABLE IF NOT EXISTS fhir_patient_bundle (
    patient_id      STRING          NOT NULL,   -- PK / FK → CORE.patient
    bundle          VARIANT         NOT NULL,   -- the full FHIR R4 Bundle JSON
    fhir_version    STRING          NOT NULL DEFAULT 'R4',
                                                -- FHIR spec version used
    resource_count  NUMBER,                     -- # resources in the bundle (optional)
    generated_at    TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    is_stale        BOOLEAN         NOT NULL DEFAULT FALSE,
                                                -- TRUE = CORE changed, bundle needs rebuild
    PRIMARY KEY (patient_id)
)
COMMENT = 'FHIR R4 Bundle per patient (VARIANT). Built by fhir_builder, read by FHIR endpoint.';


-- ── Optional: per-resource FHIR columns on existing CORE tables ───
-- Some teams also keep the FHIR fragment alongside each source row,
-- so a single condition/observation can be exported individually.
-- GTV scope keeps it simple: just the patient-level bundle above.
-- If per-resource export is needed later, add a fhir_resource VARIANT
-- column to the relevant CORE tables. Left out for now to avoid
-- schema bloat.


-- ── Grants ───────────────────────────────────────────────────────
-- clinical_role needs read+write so the builder (running as the
-- service role) can MERGE bundles and the API can read them.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE clinical_db.mart.fhir_patient_bundle
    TO ROLE clinical_role;


-- ── Verification ─────────────────────────────────────────────────
--   DESC TABLE clinical_db.mart.fhir_patient_bundle;
--   -- confirm: bundle → VARIANT, patient_id → PK
--
--   -- smoke test (insert a minimal bundle, then read it back):
--   INSERT INTO clinical_db.mart.fhir_patient_bundle (patient_id, bundle, resource_count)
--   SELECT 'pat_test001',
--          PARSE_JSON('{"resourceType":"Bundle","type":"collection","entry":[]}'),
--          0;
--   SELECT patient_id, fhir_version, bundle FROM fhir_patient_bundle
--   WHERE patient_id = 'pat_test001';