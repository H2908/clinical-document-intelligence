-- query_tuning.sql — clinical-intelligence
-- Snowflake performance tuning for the CORE tables and views.
--
-- IMPORTANT — Snowflake is NOT like MySQL/Postgres:
--   * No traditional B-tree indexes (CREATE INDEX doesn't exist).
--   * Performance comes from CLUSTERING KEYS, SEARCH OPTIMIZATION,
--     micro-partition pruning, and warehouse sizing.
--
-- At GTV demo scale (small data) these won't show measurable speedup —
-- Snowflake already scans tiny data fast. They are included as the
-- CORRECT production patterns, with notes on WHEN each one matters.
--
-- Run as ACCOUNTADMIN.
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

-- ══════════════════════════════════════════════════════════════════
-- 1. CLUSTERING KEYS
-- ══════════════════════════════════════════════════════════════════
-- Every view filters by patient_id. On a LARGE table Snowflake would
-- scan all micro-partitions unless the data is clustered so rows for
-- one patient sit together. Clustering by patient_id means a query
-- for one patient prunes (skips) partitions that don't contain them.
--
-- WHEN IT MATTERS: tables in the millions of rows. Below ~1 GB
-- Snowflake recommends NOT clustering (overhead > benefit). So for
-- GTV these are documented but commented out — turning them on for
-- a tiny table would cost more (reclustering credits) than it saves.

-- ALTER TABLE entity         CLUSTER BY (patient_id);
-- ALTER TABLE document       CLUSTER BY (patient_id);
-- ALTER TABLE flag           CLUSTER BY (patient_id);
-- ALTER TABLE observation    CLUSTER BY (patient_id);
-- ALTER TABLE timeline_event CLUSTER BY (patient_id);

-- If/when these tables grow past a few million rows, uncomment the
-- ones that are queried most and monitor with:
--   SELECT SYSTEM$CLUSTERING_INFORMATION('entity', '(patient_id)');


-- ══════════════════════════════════════════════════════════════════
-- 2. SEARCH OPTIMIZATION (point lookups)
-- ══════════════════════════════════════════════════════════════════
-- For fast single-row lookups by a specific id (e.g. GET /documents/{id}
-- hitting document_id), Search Optimization Service builds a lookup
-- structure. Costs credits to maintain — worth it for high-volume
-- point queries on large tables.
--
-- WHEN IT MATTERS: frequent equality lookups on big tables.
-- GTV scale: not needed. Documented for completeness.

-- ALTER TABLE document       ADD SEARCH OPTIMIZATION ON EQUALITY(document_id);
-- ALTER TABLE entity         ADD SEARCH OPTIMIZATION ON EQUALITY(document_id);


-- ══════════════════════════════════════════════════════════════════
-- 3. HOW TO MEASURE — query profiling
-- ══════════════════════════════════════════════════════════════════
-- The right way to tune is to MEASURE first. Run a view query, then
-- inspect how much it scanned via the query history.

-- (a) run a representative query
SELECT * FROM VW_PATIENT_360 WHERE id = 'pat_test001';

-- (b) look at the most recent queries: bytes scanned, partitions
--     scanned vs total (pruning), and execution time.
SELECT
    query_id,
    LEFT(query_text, 60) AS query_preview,
    bytes_scanned,
    total_elapsed_time / 1000 AS exec_seconds,
    rows_produced
FROM TABLE(information_schema.query_history())
WHERE query_text ILIKE '%VW_PATIENT_360%'
ORDER BY start_time DESC
LIMIT 5;

-- GOOD pruning = partitions_scanned much smaller than partitions_total.
-- If a big table always scans ALL partitions for a patient_id filter,
-- that's the signal to add a clustering key (section 1).


-- ══════════════════════════════════════════════════════════════════
-- 4. WAREHOUSE TUNING
-- ══════════════════════════════════════════════════════════════════
-- clinical_wh is X-SMALL with AUTO_SUSPEND = 60. For GTV that's ideal:
--   * X-SMALL is cheapest and fast enough for demo data.
--   * AUTO_SUSPEND = 60 means we stop paying after 60s idle.
--   * AUTO_RESUME = TRUE means it wakes on the next query.
-- Scale UP (size) for heavier single queries; scale OUT (multi-cluster)
-- for many concurrent users. Neither needed at GTV scale.

-- Confirm current settings:
SHOW WAREHOUSES LIKE 'clinical_wh';


-- ══════════════════════════════════════════════════════════════════
-- SUMMARY
-- ══════════════════════════════════════════════════════════════════
-- At GTV scale the system is already fast because the data is small
-- and Snowflake prunes micro-partitions automatically. The clustering
-- and search-optimization patterns above are the correct levers to
-- pull WHEN the tables grow large — documented and ready, intentionally
-- left off to avoid paying maintenance credits on tiny tables.