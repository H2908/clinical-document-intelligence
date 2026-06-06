"""
snowflake_writer.py — clinical-intelligence
Calls Snowflake stored procedures from the worker and agents.

All Phase 3 procedures are now implemented (no more stubs).

Functions:
    insert_raw_document(...)            -> None   (API, on upload)
    insert_core_document(...)           -> None   (worker, after processing)
    write_entities(doc, pat, entities)  -> None   -> SP_WRITE_ENTITIES
    write_observations(doc, pat, obs)   -> None   -> SP_WRITE_OBSERVATIONS
    write_flags(pat, flags)             -> None   -> SP_WRITE_FLAGS
    write_contradictions(pat, contras)  -> None   -> SP_WRITE_CONTRADICTIONS
    write_timeline(pat, events)         -> None   -> SP_WRITE_TIMELINE
    refresh_summary(pat)                -> None   -> SP_REFRESH_SUMMARY
    delete_patient(pat)                 -> dict   -> SP_DELETE_PATIENT (GDPR)

Called by: worker/document_processor.py, agents/*
"""

import os
import json
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()


# ── Snowflake connection ─────────────────────────────────────────
def _get_connection():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "clinical_db",
        schema    = "core",
        warehouse = "clinical_wh",
        role      = os.environ["SNOWFLAKE_ROLE"],
    )


# ── insert_raw_document ──────────────────────────────────────────
def insert_raw_document(
    document_id: str,
    patient_id: str,
    s3_key: str,
    file_name: str,
    doc_type: str,
    document_date,           # datetime.date
    source: str | None = None,
) -> None:
    """
    Insert one row into RAW.raw_documents with status='pending'.
    Called by api/routes/documents.py after the S3 upload succeeds.
    """
    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "clinical_db",
        schema    = "raw",
        warehouse = "clinical_wh",
        role      = os.environ["SNOWFLAKE_ROLE"],
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clinical_db.raw.raw_documents
                (document_id, patient_id, s3_key, file_name, doc_type,
                 document_date, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (document_id, patient_id, s3_key, file_name, doc_type,
              document_date, source))
        conn.commit()
    except Exception as e:
        raise RuntimeError(f"insert_raw_document failed for {document_id}: {e}") from e
    finally:
        conn.close()

# ── insert_core_document ─────────────────────────────────────────
def insert_core_document(
    document_id: str,
    patient_id: str,
    file_name: str,
    doc_type: str,
    s3_key: str,
    document_date,            # datetime.date
    source: str | None = None,
    extracted_text: str | None = None,
    status: str = "processed",
) -> None:
    """
    Promote a document from RAW to CORE after processing succeeds.
    Idempotent via MERGE — re-processing the same document_id updates
    the existing row rather than failing or duplicating.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            MERGE INTO clinical_db.core.document AS t
            USING (
                SELECT
                    %s AS document_id,
                    %s AS patient_id,
                    %s AS file_name,
                    %s AS doc_type,
                    %s AS source,
                    %s AS document_date,
                    %s AS s3_key,
                    %s AS extracted_text,
                    %s AS status
            ) AS s
            ON t.document_id = s.document_id
            WHEN MATCHED THEN UPDATE SET
                file_name       = s.file_name,
                doc_type        = s.doc_type,
                source          = s.source,
                document_date   = s.document_date,
                s3_key          = s.s3_key,
                extracted_text  = s.extracted_text,
                status          = s.status
            WHEN NOT MATCHED THEN INSERT (
                document_id, patient_id, file_name, doc_type, source,
                document_date, s3_key, extracted_text, status
            )
            VALUES (
                s.document_id, s.patient_id, s.file_name, s.doc_type, s.source,
                s.document_date, s.s3_key, s.extracted_text, s.status
            )
        """, (document_id, patient_id, file_name, doc_type, source,
              document_date, s3_key, extracted_text, status))
        conn.commit()
    except Exception as e:
        raise RuntimeError(
            f"insert_core_document failed for {document_id}: {e}"
        ) from e
    finally:
        conn.close()

# ── write_entities ───────────────────────────────────────────────
def write_entities(document_id: str, patient_id: str, entities: list) -> None:
    """
    Write NLP-extracted entities to CORE.entity via SP_WRITE_ENTITIES.

# ── insert_core_document ─────────────────────────────────────────
def insert_core_document(
    document_id: str,
    patient_id: str,
    file_name: str,
    doc_type: str,
    s3_key: str,
    document_date,            # datetime.date
    source: str | None = None,
    extracted_text: str | None = None,
    status: str = "processed",
) -> None:
    """
    Promote a document from RAW to CORE after processing succeeds.
    Idempotent via MERGE — re-processing the same document_id updates
    the existing row rather than failing or duplicating.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            MERGE INTO clinical_db.core.document AS t
            USING (
                SELECT
                    %s AS document_id,
                    %s AS patient_id,
                    %s AS file_name,
                    %s AS doc_type,
                    %s AS source,
                    %s AS document_date,
                    %s AS s3_key,
                    %s AS extracted_text,
                    %s AS status
            ) AS s
            ON t.document_id = s.document_id
            WHEN MATCHED THEN UPDATE SET
                file_name       = s.file_name,
                doc_type        = s.doc_type,
                source          = s.source,
                document_date   = s.document_date,
                s3_key          = s.s3_key,
                extracted_text  = s.extracted_text,
                status          = s.status
            WHEN NOT MATCHED THEN INSERT (
                document_id, patient_id, file_name, doc_type, source,
                document_date, s3_key, extracted_text, status
            )
            VALUES (
                s.document_id, s.patient_id, s.file_name, s.doc_type, s.source,
                s.document_date, s.s3_key, s.extracted_text, s.status
            )
        """, (document_id, patient_id, file_name, doc_type, source,
              document_date, s3_key, extracted_text, status))
        conn.commit()
    except Exception as e:
        raise RuntimeError(f"insert_core_document failed for {document_id}: {e}") from e
    finally:
        conn.close()


# ── Internal helper: call a procedure that takes one VARIANT array ─
def _call_proc_with_array(proc_call_sql: str, label: str, ref_id: str):
    """Run a CALL statement and print/return the status string."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        result = cur.execute(proc_call_sql).fetchone()
        print(f"[snowflake_writer] {label}: {result[0]}")
        return result[0]
    except Exception as e:
        raise RuntimeError(f"{label} failed for {ref_id}: {e}") from e
    finally:
        conn.close()


# ── write_entities ───────────────────────────────────────────────
def write_entities(document_id: str, patient_id: str, entities: list) -> None:
    """Write NLP entities to CORE.entity via SP_WRITE_ENTITIES."""
    entities_json = json.dumps(entities)
    sql = (f"CALL clinical_db.core.SP_WRITE_ENTITIES("
           f"'{document_id}', '{patient_id}', PARSE_JSON($${entities_json}$$))")
    _call_proc_with_array(sql, "write_entities", document_id)


# ── write_observations ───────────────────────────────────────────
def write_observations(document_id: str, patient_id: str, observations: list) -> None:
    """Write lab values to CORE.observation via SP_WRITE_OBSERVATIONS."""
    obs_json = json.dumps(observations)
    sql = (f"CALL clinical_db.core.SP_WRITE_OBSERVATIONS("
           f"'{document_id}', '{patient_id}', PARSE_JSON($${obs_json}$$))")
    _call_proc_with_array(sql, "write_observations", document_id)


# ── write_flags ──────────────────────────────────────────────────
def write_flags(patient_id: str, flags: list) -> None:
    """Write risk flags to CORE.flag via SP_WRITE_FLAGS."""
    flags_json = json.dumps(flags)
    sql = (f"CALL clinical_db.core.SP_WRITE_FLAGS("
           f"'{patient_id}', PARSE_JSON($${flags_json}$$))")
    _call_proc_with_array(sql, "write_flags", patient_id)


# ── write_contradictions ─────────────────────────────────────────
def write_contradictions(patient_id: str, contradictions: list) -> None:
    """Write contradictions to CORE.contradiction via SP_WRITE_CONTRADICTIONS."""
    contras_json = json.dumps(contradictions)
    sql = (f"CALL clinical_db.core.SP_WRITE_CONTRADICTIONS("
           f"'{patient_id}', PARSE_JSON($${contras_json}$$))")
    _call_proc_with_array(sql, "write_contradictions", patient_id)


# ── write_timeline ───────────────────────────────────────────────
def write_timeline(patient_id: str, events: list) -> None:
    """
    Rebuild CORE.timeline_event via SP_WRITE_TIMELINE.
    Idempotent — delete-then-insert on patient_id.
    """
    events_json = json.dumps(events)
    sql = (f"CALL clinical_db.core.SP_WRITE_TIMELINE("
           f"'{patient_id}', PARSE_JSON($${events_json}$$))")
    _call_proc_with_array(sql, "write_timeline", patient_id)


# ── refresh_summary ──────────────────────────────────────────────
def refresh_summary(patient_id: str) -> None:
    """Rebuild MART.patient_summary via SP_REFRESH_SUMMARY."""
    sql = f"CALL clinical_db.mart.SP_REFRESH_SUMMARY('{patient_id}')"
    _call_proc_with_array(sql, "refresh_summary", patient_id)


# ── delete_patient ───────────────────────────────────────────────
def delete_patient(patient_id: str) -> dict:
    """
    GDPR erasure cascade via SP_DELETE_PATIENT.
    Returns a dict including 's3_keys' the API must delete from S3.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        sql = f"CALL clinical_db.core.SP_DELETE_PATIENT('{patient_id}')"
        result = cur.execute(sql).fetchone()
        # result[0] is a VARIANT (JSON) — parse to dict
        payload = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        print(f"[snowflake_writer] delete_patient: {payload}")
        return payload
    except Exception as e:
        raise RuntimeError(f"delete_patient failed for {patient_id}: {e}") from e
    finally:
        conn.close()


# ── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    test_entities = [
        {"entity_type": "Diagnosis", "text": "dilated cardiomyopathy",
         "start_offset": 108, "end_offset": 130, "negated": False,
         "icd10_code": "I42.0", "normalised_value": None},
        {"entity_type": "Drug", "text": "bisoprolol 2.5 mg",
         "start_offset": 150, "end_offset": 167, "negated": False,
         "icd10_code": None, "normalised_value": "bisoprolol"},
    ]
    print("Testing write_entities...")
    write_entities("doc_test002", "pat_test001", test_entities)
    print("Done — check CORE.entity for doc_test002")