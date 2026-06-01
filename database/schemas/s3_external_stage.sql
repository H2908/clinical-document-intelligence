-- s3_external_stage.sql — clinical-intelligence
-- Creates the Snowflake external stage pointing to S3.
-- Requires clinical_s3_int storage integration to exist first.
-- Matches DB_SCHEMA.md v1 (locked).
-- ─────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE clinical_db;
USE SCHEMA raw;

-- ── Storage integration ──────────────────────────────────────────
-- Links Snowflake to S3 via IAM role (no access keys needed).
-- STORAGE_AWS_ROLE_ARN = clinical-snowflake-role in AWS IAM.
CREATE STORAGE INTEGRATION IF NOT EXISTS clinical_s3_int
  TYPE                      = EXTERNAL_STAGE
  STORAGE_PROVIDER          = S3
  ENABLED                   = TRUE
  STORAGE_AWS_ROLE_ARN      = 'arn:aws:iam::262981514983:role/clinical-snowflake-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://clinical-intelligence-docs/uploads/');

-- ── External stage ───────────────────────────────────────────────
-- Points to the uploads/ prefix in the S3 bucket.
-- Used by Snowpipe to read files automatically.
CREATE STAGE IF NOT EXISTS clinical_docs_stage
  STORAGE_INTEGRATION = clinical_s3_int
  URL                 = 's3://clinical-intelligence-docs/uploads/'
  FILE_FORMAT         = (TYPE = JSON);

-- ── Verification ─────────────────────────────────────────────────
-- Confirm Snowflake can see S3 bucket contents:
--   LIST @clinical_docs_stage;
-- Should return uploaded files under uploads/
