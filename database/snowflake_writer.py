"""
snowflake_writer.py — clinical-intelligence
Calls Snowflake stored procedures from the worker.

Fixed signatures (from DB_SCHEMA.md):
    write_entities(document_id, patient_id, entities) -> None
    write_flags(patient_id, flags) -> None               [Phase 3]
    write_contradictions(patient_id, contradictions)     [Phase 3]
    refresh_summary(patient_id) -> None                  [Phase 3]

Called by: worker/document_processor.py
Calls:     SP_WRITE_ENTITIES, SP_WRITE_FLAGS, etc. in Snowflake
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
    file_name:str,
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
        schema    = "raw",                 # <-- raw, not core
        warehouse = "clinical_wh",
        role      = os.environ["SNOWFLAKE_ROLE"],
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clinical_db.raw.raw_documents
                (document_id, patient_id, s3_key,file_name, doc_type,
                 document_date, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (document_id, patient_id, s3_key, file_name, doc_type,
              document_date, source))
        conn.commit()
    except Exception as e:
        raise RuntimeError(
            f"insert_raw_document failed for {document_id}: {e}"
        ) from e
    finally:
        conn.close()

# ── write_entities ───────────────────────────────────────────────
def write_entities(document_id: str, patient_id: str, entities: list) -> None:
    """
    Write NLP-extracted entities to CORE.entity via SP_WRITE_ENTITIES.

    Args:
        document_id: e.g. "doc_77ab"
        patient_id:  e.g. "pat_8f3a"
        entities:    list of entity dicts matching NLP_OUTPUT.md shape
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        # Use dollar-quoting ($$) to safely pass JSON to Snowflake
        # Full path: database.schema.procedure_name
        entities_json = json.dumps(entities)
        sql = f"""CALL clinical_db.core.SP_WRITE_ENTITIES(
            '{document_id}',
            '{patient_id}',
            PARSE_JSON($${entities_json}$$)
        )"""
        result = cur.execute(sql).fetchone()
        print(f"[snowflake_writer] write_entities: {result[0]}")
    except Exception as e:
        raise RuntimeError(
            f"SP_WRITE_ENTITIES failed for document {document_id}: {e}"
        ) from e
    finally:
        conn.close()


# ── write_flags ──────────────────────────────────────────────────
def write_flags(patient_id: str, flags: list) -> None:
    """
    Write risk flags to CORE.flag via SP_WRITE_FLAGS.
    Phase 3 — stub only.
    """
    raise NotImplementedError("write_flags is a Phase 3 deliverable")


# ── write_contradictions ─────────────────────────────────────────
def write_contradictions(patient_id: str, contradictions: list) -> None:
    """
    Write contradictions to CORE.contradiction via SP_WRITE_CONTRADICTIONS.
    Phase 3 — stub only.
    """
    raise NotImplementedError("write_contradictions is a Phase 3 deliverable")


# ── refresh_summary ──────────────────────────────────────────────
def refresh_summary(patient_id: str) -> None:
    """
    Rebuild MART.patient_summary for a patient via SP_REFRESH_SUMMARY.
    Phase 3 — stub only.
    """
    raise NotImplementedError("refresh_summary is a Phase 3 deliverable")


# ── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    test_entities = [
        {
            "entity_type":      "Diagnosis",
            "text":             "dilated cardiomyopathy",
            "start_offset":     108,
            "end_offset":       130,
            "negated":          False,
            "icd10_code":       "I42.0",
            "normalised_value": None
        },
        {
            "entity_type":      "Drug",
            "text":             "bisoprolol 2.5 mg",
            "start_offset":     150,
            "end_offset":       167,
            "negated":          False,
            "icd10_code":       None,
            "normalised_value": "bisoprolol"
        }
    ]

    print("Testing write_entities...")
    write_entities("doc_test002", "pat_test001", test_entities)
    print("Done — check CORE.entity for doc_test002")