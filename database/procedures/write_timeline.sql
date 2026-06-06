-- write_timeline.sql — clinical-intelligence
-- Stored procedure: SP_WRITE_TIMELINE
-- Rebuilds a patient's clinical timeline in CORE.timeline_event.
--
-- Signature (locked in DB_SCHEMA.md):
--   SP_WRITE_TIMELINE(patient_id VARCHAR, events VARIANT) -> STRING
--
-- Called by: briefing_agent (via worker)
-- Writes to: CORE.timeline_event
--
-- IDEMPOTENCY: delete-then-insert on patient_id. The timeline is
-- rebuilt in full every time the briefing_agent runs, so we first
-- delete all existing events for this patient, then insert the new
-- set. Running it twice produces the same result (no duplicates).
--
-- Each object in the events array matches NLP_OUTPUT.md:
--   {
--     "event_date":         "2024-02-28",
--     "event_type":         "Diagnosis|Medication|Flag|Referral|
--                            Observation|Lab|Imaging",
--     "title":              "Dilated cardiomyopathy diagnosed",
--     "icd10_code":         "I42.0",      ← nullable
--     "source_document_id": "doc_77ab"
--   }
-- ─────────────────────────────────────────────────────────────────

USE DATABASE clinical_db;
USE SCHEMA core;

CREATE OR REPLACE PROCEDURE SP_WRITE_TIMELINE(
    PATIENT_ID  STRING,
    EVENTS      VARIANT
)
RETURNS STRING
LANGUAGE JAVASCRIPT
AS
$$
    if (!PATIENT_ID) throw new Error("patient_id is required");
    if (!EVENTS)     throw new Error("events array is required");

    var events = EVENTS;

    // ── Idempotency: clear existing timeline for this patient ─────
    // The timeline is rebuilt every time, so delete first.
    var delStmt = snowflake.createStatement({
        sqlText: `DELETE FROM clinical_db.core.timeline_event
                  WHERE patient_id = :1`,
        binds: [PATIENT_ID]
    });
    delStmt.execute();

    // Empty events array is valid — patient timeline is now cleared.
    if (events.length === 0) {
        return "OK: timeline cleared, 0 events written for patient " + PATIENT_ID;
    }

    // ── Insert the new event set ──────────────────────────────────
    var inserted = 0;

    for (var i = 0; i < events.length; i++) {
        var ev = events[i];

        // Required fields
        if (!ev.event_date) {
            throw new Error("event at index " + i + " is missing event_date");
        }
        if (!ev.event_type) {
            throw new Error("event at index " + i + " is missing event_type");
        }
        if (!ev.title) {
            throw new Error("event at index " + i + " is missing title");
        }
        if (!ev.source_document_id) {
            throw new Error("event at index " + i + " is missing source_document_id (provenance required)");
        }

        // Generate event_id — like ent_xxx pattern
        var event_id = "evt_" + PATIENT_ID.replace("pat_", "") + "_" + Date.now() + "_" + i;

        var stmt = snowflake.createStatement({
            sqlText: `
                INSERT INTO clinical_db.core.timeline_event (
                    event_id, patient_id, event_date, event_type,
                    title, icd10_code, source_document_id, created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, CURRENT_TIMESTAMP()
                )
            `,
            binds: [
                event_id,
                PATIENT_ID,
                ev.event_date,
                ev.event_type,
                ev.title,
                ev.icd10_code         || null,
                ev.source_document_id
            ]
        });

        stmt.execute();
        inserted++;
    }

    return "OK: " + inserted + " timeline events written for patient " + PATIENT_ID;
$$;

GRANT USAGE ON PROCEDURE SP_WRITE_TIMELINE(STRING, VARIANT) TO ROLE clinical_role;

-- ── Test ─────────────────────────────────────────────────────────
-- Needs a test patient + document to exist first (FK on source_document_id).
--
-- CALL SP_WRITE_TIMELINE('pat_test001', PARSE_JSON('[
--   {"event_date":"2024-02-28","event_type":"Diagnosis",
--    "title":"Dilated cardiomyopathy diagnosed","icd10_code":"I42.0",
--    "source_document_id":"doc_test001"},
--   {"event_date":"2024-02-28","event_type":"Medication",
--    "title":"Started Bisoprolol 2.5 mg OD","icd10_code":null,
--    "source_document_id":"doc_test001"}
-- ]'));
--
-- SELECT * FROM clinical_db.core.timeline_event WHERE patient_id = 'pat_test001'
-- ORDER BY event_date;