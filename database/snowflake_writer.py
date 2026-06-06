"""
snowflake_writer.py - clinical-intelligence
Calls Snowflake stored procedures from the worker and agents.
"""

import os
import json
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()


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


def insert_raw_document(document_id, patient_id, s3_key, file_name, doc_type, document_date, source=None):
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
                (document_id, patient_id, s3_key, file_name, doc_type, document_date, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (document_id, patient_id, s3_key, file_name, doc_type, document_date, source))
        conn.commit()
    except Exception as e:
        raise RuntimeError("insert_raw_document failed: " + str(e)) from e
    finally:
        conn.close()


def insert_core_document(document_id, patient_id, file_name, doc_type, s3_key, document_date, source=None, extracted_text=None, status="processed"):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            MERGE INTO clinical_db.core.document AS t
            USING (
                SELECT %s AS document_id, %s AS patient_id, %s AS file_name,
                       %s AS doc_type, %s AS source, %s AS document_date,
                       %s AS s3_key, %s AS extracted_text, %s AS status
            ) AS s
            ON t.document_id = s.document_id
            WHEN MATCHED THEN UPDATE SET
                file_name = s.file_name, doc_type = s.doc_type, source = s.source,
                document_date = s.document_date, s3_key = s.s3_key,
                extracted_text = s.extracted_text, status = s.status
            WHEN NOT MATCHED THEN INSERT
                (document_id, patient_id, file_name, doc_type, source,
                 document_date, s3_key, extracted_text, status)
            VALUES
                (s.document_id, s.patient_id, s.file_name, s.doc_type, s.source,
                 s.document_date, s.s3_key, s.extracted_text, s.status)
        """, (document_id, patient_id, file_name, doc_type, source, document_date, s3_key, extracted_text, status))
        conn.commit()
    except Exception as e:
        raise RuntimeError("insert_core_document failed: " + str(e)) from e
    finally:
        conn.close()


def _call_proc(sql, label, ref_id):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        result = cur.execute(sql).fetchone()
        print("[snowflake_writer] " + label + ": " + str(result[0]))
        return result[0]
    except Exception as e:
        raise RuntimeError(label + " failed for " + ref_id + ": " + str(e)) from e
    finally:
        conn.close()


def write_entities(document_id, patient_id, entities):
    entities_json = json.dumps(entities)
    sql = "CALL clinical_db.core.SP_WRITE_ENTITIES('" + document_id + "', '" + patient_id + "', PARSE_JSON($$" + entities_json + "$$))"
    _call_proc(sql, "write_entities", document_id)


def write_observations(document_id, patient_id, observations):
    obs_json = json.dumps(observations)
    sql = "CALL clinical_db.core.SP_WRITE_OBSERVATIONS('" + document_id + "', '" + patient_id + "', PARSE_JSON($$" + obs_json + "$$))"
    _call_proc(sql, "write_observations", document_id)


def write_flags(patient_id, flags):
    flags_json = json.dumps(flags)
    sql = "CALL clinical_db.core.SP_WRITE_FLAGS('" + patient_id + "', PARSE_JSON($$" + flags_json + "$$))"
    _call_proc(sql, "write_flags", patient_id)


def write_contradictions(patient_id, contradictions):
    contras_json = json.dumps(contradictions)
    sql = "CALL clinical_db.core.SP_WRITE_CONTRADICTIONS('" + patient_id + "', PARSE_JSON($$" + contras_json + "$$))"
    _call_proc(sql, "write_contradictions", patient_id)


def write_timeline(patient_id, events):
    events_json = json.dumps(events)
    sql = "CALL clinical_db.core.SP_WRITE_TIMELINE('" + patient_id + "', PARSE_JSON($$" + events_json + "$$))"
    _call_proc(sql, "write_timeline", patient_id)


def refresh_summary(patient_id):
    sql = "CALL clinical_db.mart.SP_REFRESH_SUMMARY('" + patient_id + "')"
    _call_proc(sql, "refresh_summary", patient_id)


def delete_patient(patient_id):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        sql = "CALL clinical_db.core.SP_DELETE_PATIENT('" + patient_id + "')"
        result = cur.execute(sql).fetchone()
        payload = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        print("[snowflake_writer] delete_patient: " + str(payload))
        return payload
    except Exception as e:
        raise RuntimeError("delete_patient failed: " + str(e)) from e
    finally:
        conn.close()


if __name__ == "__main__":
    print("snowflake_writer loaded")
