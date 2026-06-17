-- ============================================================================
-- Provenance hash column for CORE.flag
-- Requested by: ML/Backend side (Phase 4 L2, audit agent)
-- Date: 2026-06-18
-- Estimated cost: < 1 second (DDL + ALTER PROC)
-- ============================================================================

-- Step 1. Add the nullable column to CORE.flag.
--         Nullable because existing rows have no hash; new writes will
--         populate it from the incoming JSON's "provenance_hash" key.
ALTER TABLE clinical_db.core.flag
    ADD COLUMN provenance_hash VARCHAR(64) NULL
        COMMENT 'SHA-256 hex digest of flag provenance + content (see agents/audit_agent.py)';

-- Step 2. Update SP_WRITE_FLAGS to copy the field from the incoming
--         array element into the new column. The exact body depends on
--         the current proc definition; if you can paste the current proc
--         we can supply the minimal diff.
--
-- Expected diff: in the JSON-to-row mapping inside the proc, add:
--
--     ...
--     value:provenance_hash::VARCHAR AS provenance_hash,
--     ...
--
-- where `value` is the iterator over the input array. The column should
-- map to the new flag.provenance_hash column in the INSERT/MERGE statement.

-- Step 3. Verification query - confirm column added and procedure updated.
-- After steps 1-2, the next held-out smoke run from the ML side will
-- write flags with provenance_hash populated. To confirm post-run:
--
--     SELECT COUNT(*) AS total_flags,
--            COUNT(provenance_hash) AS hashed_flags,
--            COUNT(*) - COUNT(provenance_hash) AS unhashed_flags
--     FROM clinical_db.core.flag;
--
-- For flags written before this migration, provenance_hash is NULL and
-- they are reported as 'no_stored_hash' (not 'mismatch') by the audit
-- agent. That is correct behaviour - they are pre-instrumentation data
-- and unverifiable rather than tampered.