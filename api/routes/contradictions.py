"""
Contradictions endpoint - reads cross-document conflicts from CORE.contradiction.
Dedupes on (category, doc_a_id, doc_b_id) to handle re-runs.
"""

import os
import logging

import snowflake.connector
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)
router = APIRouter()


def _conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


@router.get("/patients/{patient_id}/contradictions")
def list_contradictions(patient_id: str) -> dict:
    """
    Return distinct contradictions for a patient. Dedupes on
    (category, doc_a_id, doc_b_id), keeping the most recent.
    """
    try:
        conn = _conn()
    except Exception:
        log.exception("Snowflake connect failed for contradictions read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT contradiction_id, severity, category,
                   doc_a_id, doc_a_statement,
                   doc_b_id, doc_b_statement,
                   explanation, status, created_at, resolved_at
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY category, doc_a_id, doc_b_id
                           ORDER BY created_at DESC
                       ) AS rn
                FROM clinical_db.core.contradiction
                WHERE patient_id = %s
            )
            WHERE rn = 1
            ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                     created_at DESC
        """, (patient_id,))
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
        items = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        log.exception("CORE.contradiction read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    for c in items:
        if c.get("created_at"):
            c["created_at"] = c["created_at"].isoformat()
        if c.get("resolved_at"):
            c["resolved_at"] = c["resolved_at"].isoformat()

    return {
        "patient_id": patient_id,
        "count": len(items),
        "contradictions": items,
    }