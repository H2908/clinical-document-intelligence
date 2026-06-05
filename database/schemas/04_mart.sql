-- 04_mart.sql — clinical-intelligence
-- MART layer: pre-computed read models for fast API reads.
-- Matches DB_SCHEMA.md v1 (locked).
-- Run AFTER 03_core.sql (patient_summary references CORE.patient).
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA mart;

-- ── patient_summary ──────────────────────────────────────────────
-- Pre-computed briefing. One row per patient.
-- GET /briefing reads only this — no LLM call on the read path.
-- The worker rewrites this row whenever a new document for that
-- patient finishes processing.
-- Refresh rule:
--   1. Worker finishes document → sets is_stale = TRUE
--   2. briefing_agent rebuilds summary → sets is_stale = FALSE
CREATE TABLE IF NOT EXISTS patient_summary (
    patient_id      STRING          NOT NULL,   -- PK / FK → CORE.patient
    summary         VARIANT         NOT NULL,   -- full briefing JSON —
                                                -- matches GET /briefing response body
    generated_at    TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    is_stale        BOOLEAN         NOT NULL DEFAULT FALSE,
                                                -- TRUE = new doc landed, not yet rebuilt
    PRIMARY KEY (patient_id)
)
COMMENT = 'Pre-computed briefing. One row per patient. is_stale drives refresh.';

-- ── Verification ─────────────────────────────────────────────────
--   SHOW TABLES IN SCHEMA clinical_db.mart;
--   -- expect: patient_summary