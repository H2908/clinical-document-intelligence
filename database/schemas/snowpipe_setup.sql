-- snowpipe_setup.sql — clinical-intelligence
-- Creates the Snowpipe that auto-ingests JSON manifests from S3
-- into RAW.raw_documents whenever a file lands in the bucket.
-- Requires s3_external_stage.sql to be run first.
-- Matches DB_SCHEMA.md v1 (locked).
-- ─────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE clinical_db;
USE SCHEMA raw;

-- ── Snowpipe ─────────────────────────────────────────────────────
-- AUTO_INGEST = TRUE means S3 notifies Snowpipe via SQS whenever
-- a new file lands under uploads/. No manual trigger needed.
CREATE PIPE IF NOT EXISTS clinical_docs_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO raw_documents (
    document_id,
    patient_id,
    file_name,
    doc_type,
    source,
    document_date,
    s3_key,
    status,
    uploaded_at
  )
  FROM (
    SELECT
      $1:document_id::STRING,
      $1:patient_id::STRING,
      $1:file_name::STRING,
      $1:doc_type::STRING,
      $1:source::STRING,
      $1:document_date::DATE,
      $1:s3_key::STRING,
      'pending',
      $1:uploaded_at::TIMESTAMP_NTZ
    FROM @clinical_docs_stage
  )
  FILE_FORMAT = (TYPE = JSON);

-- ── After creating the pipe ───────────────────────────────────────
-- Run DESC PIPE to get the notification_channel ARN.
-- Use that ARN to set up the S3 event notification in AWS:
--   S3 → clinical-intelligence-docs → Properties →
--   Event notifications → Create event notification:
--     Prefix: uploads/
--     Events: All object create events
--     Destination: SQS → Enter SQS queue ARN → paste notification_channel
--
--   DESC PIPE clinical_docs_pipe;

-- ── Verification ─────────────────────────────────────────────────
-- After uploading a JSON manifest, confirm it lands here:
--   SELECT document_id, patient_id, file_name, status, uploaded_at
--   FROM raw.raw_documents
--   ORDER BY uploaded_at DESC
--   LIMIT 10;
