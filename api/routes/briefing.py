"""
Briefing endpoint - reads the pre-appointment summary from MART.patient_summary.
"""

import os
import json
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


@router.get("/patients/{patient_id}/briefing")
def get_briefing(patient_id: str) -> dict:
    """
    Returns the most recent pre-appointment briefing for a patient.
    Source: MART.patient_summary (refreshed by briefing_agent each upload).
    """
    try:
        conn = _conn()
    except Exception:
        log.exception("Snowflake connect failed for briefing read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT summary, generated_at, is_stale
            FROM clinical_db.mart.patient_summary
            WHERE patient_id = %s
        """, (patient_id,))
        row = cur.fetchone()
    except Exception as e:
        log.exception("patient_summary read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    if not row:
        return {
            "patient_id": patient_id,
            "available": False,
            "message": "No briefing has been generated for this patient yet.",
        }

    summary_raw, generated_at, is_stale = row
    # VARIANT comes back as a JSON string from Snowflake
    summary = json.loads(summary_raw) if isinstance(summary_raw, str) else summary_raw

    return {
        "patient_id": patient_id,
        "available": True,
        "generated_at": generated_at.isoformat() if generated_at else None,
        "is_stale": bool(is_stale) if is_stale is not None else False,
        "disclaimer": (
            "For administrative use only. This briefing is generated from "
            "extracted document data and does not constitute clinical advice."
        ),
        "summary": summary,
    }