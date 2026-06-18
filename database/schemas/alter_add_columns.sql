-- alter_add_columns.sql — clinical-intelligence
-- Two schema additions requested by the ML partner.
-- Run as ACCOUNTADMIN (ALTER TABLE needs DDL rights).
-- ─────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE clinical_db;
USE SCHEMA core;

-- ── 1. provenance_hash on flag ───────────────────────────────────
-- Audit hash: a fingerprint proving where each flag came from.
-- flag_agent computes the hash and persists it here.
-- Nullable so existing rows (and any flag written before the agent
-- computes a hash) remain valid.
ALTER TABLE clinical_db.core.flag
    ADD COLUMN IF NOT EXISTS provenance_hash STRING;

COMMENT ON COLUMN clinical_db.core.flag.provenance_hash IS
    'Audit fingerprint of the flag source (e.g. SHA-256 hex). Set by flag_agent.';


-- ── 2. bnf_code on entity ────────────────────────────────────────
-- BNF (British National Formulary) drug code. Only drug entities have
-- one; diagnoses/dates/etc. do not — so it is NULLABLE.
ALTER TABLE clinical_db.core.entity
    ADD COLUMN IF NOT EXISTS bnf_code STRING;

COMMENT ON COLUMN clinical_db.core.entity.bnf_code IS
    'British National Formulary drug code. Nullable — only set for drug entities.';


-- ── Verify ───────────────────────────────────────────────────────
-- DESC TABLE clinical_db.core.flag;    -- expect provenance_hash
-- DESC TABLE clinical_db.core.entity;  -- expect bnf_code