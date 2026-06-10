"""
Flags endpoint - reads risk flags from CORE.flag.

The flag_agent re-runs on every upload and persistence is idempotent at
the row level, not the (category, description) level. We dedupe in the
read query, keeping the newest row per (category, description) pair.
"""

import os
import logging

import snowflake.connector
from fastapi import APIRouter, HTTPException, Query
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


@router.get("/patients/{patient_id}/flags")
def list_flags(
    patient_id: str,
    status: str | None = Query(None, description="Filter by status (open/resolved). Omit for all."),
) -> dict:
    """
    Return distinct flags for a patient. Dedupes on (category, description),
    keeping the most recent row.
    """
    try:
        conn = _conn()
    except Exception:
        log.exception("Snowflake connect failed for flags read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    sql = """
        SELECT flag_id, severity, category, description,
               source_document_id, status, created_at, resolved_at
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY category, description
                       ORDER BY created_at DESC
                   ) AS rn
            FROM clinical_db.core.flag
            WHERE patient_id = %s
        )
        WHERE rn = 1
    """
    params: list = [patient_id]
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, created_at DESC"

    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
        flags = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        log.exception("CORE.flag read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    # Serialise timestamps
    for f in flags:
        if f.get("created_at"):
            f["created_at"] = f["created_at"].isoformat()
        if f.get("resolved_at"):
            f["resolved_at"] = f["resolved_at"].isoformat()

    open_count = sum(1 for f in flags if f.get("status", "open") == "open")
    resolved_count = sum(1 for f in flags if f.get("status") == "resolved")

    return {
        "patient_id": patient_id,
        "open_count": open_count,
        "resolved_count": resolved_count,
        "flags": flags,
    }