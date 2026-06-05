"""
Snowflake reader — reads patient state from CORE for the agent orchestrator.

Owner: DE member (this file drafted by ML, needs DE review for column-name
       alignment with the actual schema).
Used by: agents/orchestrator.py

Contract: see docs/DB_SCHEMA.md §7.
"""

from __future__ import annotations
import os
import logging
from typing import Any

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helper — mirrors snowflake_writer._get_connection style
# ---------------------------------------------------------------------------

def _get_connection():
    """Build a Snowflake connection from env vars. Schema='core' for reads."""
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "clinical_db",
        schema    = "core",
        warehouse = "clinical_wh",
        role      = os.environ["SNOWFLAKE_ROLE"],
    )


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    """Convert a cursor result into a list of dicts keyed by column name."""
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_entities_for_patient(patient_id: str) -> list[dict[str, Any]]:
    """
    Return every entity for this patient, joined with its document metadata.

    Each dict matches NLP_OUTPUT.md §3 plus joined document fields:
        entity_type, text, start_offset, end_offset, negated,
        icd10_code, normalised_value,
        document_id, document_date, doc_type

    See DB_SCHEMA.md §7.1.
    """
    log.info("Reading entities for patient %s", patient_id)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # NOTE for DE reviewer: column names below assume the schema in
        # database/schemas/02_core.sql. Adjust if your column names differ
        # (e.g. start_offset vs start_char).
        cur.execute("""
            SELECT
                e.entity_type,
                e.text,
                e.start_offset,
                e.end_offset,
                e.negated,
                e.icd10_code,
                e.normalised_value,
                e.document_id,
                d.document_date,
                d.doc_type
            FROM clinical_db.core.entity e
            JOIN clinical_db.core.document d
              ON e.document_id = d.document_id
            WHERE d.patient_id = %s
            ORDER BY d.document_date DESC, e.start_offset ASC
        """, (patient_id,))
        rows = _rows_to_dicts(cur)
        log.info("Found %d entities for %s", len(rows), patient_id)
        return rows
    except Exception as e:
        log.exception("read_entities_for_patient failed for %s", patient_id)
        raise RuntimeError(f"read_entities_for_patient failed: {e}") from e
    finally:
        conn.close()


def read_documents_for_patient(patient_id: str) -> list[dict[str, Any]]:
    """
    Return every document for this patient, ordered newest first.

    Each dict: {document_id, doc_type, document_date, source, status,
                file_name, s3_key, uploaded_at}.

    See DB_SCHEMA.md §7.2.
    """
    log.info("Reading documents for patient %s", patient_id)
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                document_id,
                doc_type,
                document_date,
                source,
                status,
                file_name,
                s3_key,
                created_at
            FROM clinical_db.core.document
            WHERE patient_id = %s
            ORDER BY document_date DESC, created_at DESC
        """, (patient_id,))
        rows = _rows_to_dicts(cur)
        log.info("Found %d documents for %s", len(rows), patient_id)
        return rows
    except Exception as e:
        log.exception("read_documents_for_patient failed for %s", patient_id)
        raise RuntimeError(f"read_documents_for_patient failed: {e}") from e
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m database.snowflake_reader <patient_id>")
        sys.exit(1)

    patient_id = sys.argv[1]
    entities = read_entities_for_patient(patient_id)
    documents = read_documents_for_patient(patient_id)

    print(json.dumps({
        "patient_id": patient_id,
        "entities_count": len(entities),
        "documents_count": len(documents),
        "first_entity": entities[0] if entities else None,
        "first_document": documents[0] if documents else None,
    }, indent=2, default=str))