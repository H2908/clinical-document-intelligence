-- snowflake_connection.sql — clinical-intelligence project
-- Run as ACCOUNTADMIN immediately after account creation
-- ─────────────────────────────────────────────────────────

-- ── Step 1: Warehouse ────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS clinical_wh
  WITH WAREHOUSE_SIZE   = 'X-SMALL'
  AUTO_SUSPEND          = 60
  AUTO_RESUME           = TRUE
  INITIALLY_SUSPENDED   = TRUE
  COMMENT = 'Clinical Intelligence platform warehouse';

-- ── Step 2: Database ─────────────────────────────────────
CREATE DATABASE IF NOT EXISTS clinical_db
  COMMENT = 'Clinical Document Intelligence platform';

-- ── Step 3: Schemas (mirrors database/ folder) ───────────
USE DATABASE clinical_db;

CREATE SCHEMA IF NOT EXISTS raw
  COMMENT = 'Raw ingestion layer — Snowpipe lands here';

CREATE SCHEMA IF NOT EXISTS staging
  COMMENT = 'Typed / cleaned staging layer';

CREATE SCHEMA IF NOT EXISTS core
  COMMENT = 'Core entities: patient, document, entity, flag, observation';

CREATE SCHEMA IF NOT EXISTS mart
  COMMENT = 'Patient summary and aggregated views';

-- ── Step 4: Role ─────────────────────────────────────────
CREATE ROLE IF NOT EXISTS clinical_role
  COMMENT = 'Application role for clinical-intelligence services';

-- ── Step 5: Privileges ───────────────────────────────────
GRANT USAGE ON WAREHOUSE clinical_wh           TO ROLE clinical_role;
GRANT USAGE ON DATABASE  clinical_db           TO ROLE clinical_role;

-- raw: needs STAGE + PIPE for Snowpipe
GRANT USAGE, CREATE TABLE, CREATE VIEW,
      CREATE STAGE, CREATE PIPE
  ON SCHEMA clinical_db.raw                    TO ROLE clinical_role;

-- staging: tables + views only
GRANT USAGE, CREATE TABLE, CREATE VIEW
  ON SCHEMA clinical_db.staging                TO ROLE clinical_role;

-- core: stored procedures + sequences for write paths
GRANT USAGE, CREATE TABLE, CREATE VIEW,
      CREATE PROCEDURE, CREATE SEQUENCE
  ON SCHEMA clinical_db.core                   TO ROLE clinical_role;

-- mart: read + write summary tables
GRANT USAGE, CREATE TABLE, CREATE VIEW
  ON SCHEMA clinical_db.mart                   TO ROLE clinical_role;

-- ── Step 6: Service account ──────────────────────────────
-- Used by Python connectors (snowflake_writer.py, db.py)
CREATE USER IF NOT EXISTS clinical_svc
  PASSWORD            = '<REPLACE_WITH_STRONG_PASSWORD>'
  DEFAULT_ROLE        = clinical_role
  DEFAULT_WAREHOUSE   = clinical_wh
  DEFAULT_NAMESPACE   = clinical_db.core
  MUST_CHANGE_PASSWORD = FALSE
  COMMENT = 'Service account for clinical-intelligence app';

GRANT ROLE clinical_role TO USER clinical_svc;

-- ── Step 7: Verification ─────────────────────────────────
-- Run these after to confirm everything is in place
SELECT CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_ROLE();
SHOW SCHEMAS IN DATABASE clinical_db;
SHOW GRANTS TO ROLE clinical_role;