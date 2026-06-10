"""
Timeline endpoint - reads chronological events from CORE.timeline_event.
Dedupes on (event_date, event_type, title) to handle re-runs.
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


@router.get("/patients/{patient_id}/timeline")
def get_timeline(
    patient_id: str,
    event_type: str | None = Query(None, description="Optional filter (Diagnosis, Drug, Conflict, Document)"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    """
    Return distinct timeline events for a patient. Dedupes on
    (event_date, event_type, title), keeping the most recent row.
    Ordered newest first.
    """
    try:
        conn = _conn()
    except Exception:
        log.exception("Snowflake connect failed for timeline read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    sql = """
        SELECT event_id, event_date, event_type, title,
               icd10_code, source_document_id, created_at
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY event_date, event_type, title
                       ORDER BY created_at DESC
                   ) AS rn
            FROM clinical_db.core.timeline_event
            WHERE patient_id = %s
        )
        WHERE rn = 1
    """
    params: list = [patient_id]
    if event_type:
        sql += " AND event_type = %s"
        params.append(event_type)
    sql += " ORDER BY event_date DESC NULLS LAST, created_at DESC LIMIT %s"
    params.append(limit)

    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
        events = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        log.exception("CORE.timeline_event read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    for ev in events:
        if ev.get("event_date"):
            ev["event_date"] = ev["event_date"].isoformat()
        if ev.get("created_at"):
            ev["created_at"] = ev["created_at"].isoformat()

    return {
        "patient_id": patient_id,
        "count": len(events),
        "events": events,
    }