"""
Lab report upload + retrieval endpoints.

POST /patients/{patient_id}/labs — uploads a lab PDF; same chain as the
generic documents endpoint but forces doc_type='lab_report' so the worker
runs the lab parser and persists observations to CORE.observation.

GET /patients/{patient_id}/labs — returns the patient's observation list
from CORE.observation, ordered newest first.
"""

import logging
import uuid
from pathlib import Path
from datetime import date

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from database.snowflake_writer import insert_raw_document
from ingestion.s3_uploader import upload

log = logging.getLogger(__name__)
router = APIRouter()


# ---- POST /patients/{patient_id}/labs ----
@router.post(
    "/patients/{patient_id}/labs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_lab_report(
    patient_id: str,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    source: str | None = Form(None),
) -> dict:
    """
    Upload flow for lab reports:
      1. Push PDF to S3
      2. Insert row into RAW.raw_documents (doc_type='lab_report')
      3. Run NLP worker synchronously - lab_parser extracts observations,
         medical_ner extracts any clinical entities present in the report
      4. Worker invokes agent orchestrator
      5. Return summary counts (observation_count + entity_count + agent_counts)
    """
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    original_ext = Path(file.filename or "").suffix or ".pdf"
    s3_key = f"uploads/{patient_id}/{document_id}{original_ext}"
    file_name = file.filename or f"{document_id}{original_ext}"

    # 1. S3 upload
    try:
        upload(file.file, s3_key)
    except Exception as e:
        log.exception("S3 upload failed for lab %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 upload failed: {e}"}},
        )

    # 2. RAW row - doc_type forced to 'lab_report'
    try:
        insert_raw_document(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            file_name=file_name,
            doc_type="lab_report",
            document_date=document_date,
            source=source,
        )
    except Exception as e:
        log.exception("RAW insert failed for lab %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 ok but DB insert failed: {e}"}},
        )

    # 3 + 4. Worker + orchestrator
    from worker.document_processor import process_from_s3
    try:
        result = process_from_s3(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            document_date=document_date,
            doc_type="lab_report",
        )
        final_status = result["status"]
        entity_count = len(result.get("entities", []))
        observation_count = len(result.get("observations", []))
        agent_counts = result.get("agent_counts", {})
    except Exception as e:
        log.exception("Worker pipeline failed for lab %s", document_id)
        final_status = "failed"
        entity_count = 0
        observation_count = 0
        agent_counts = {}

    # 5. Response
    if final_status == "processed":
        message = (
            f"Lab report processed - {observation_count} observations, "
            f"{entity_count} entities, "
            f"{agent_counts.get('flags', 0)} flags."
        )
    else:
        message = "Lab report received but processing failed - check logs."

    return {
        "document_id": document_id,
        "status": final_status,
        "doc_type": "lab_report",
        "observation_count": observation_count,
        "entity_count": entity_count,
        "agent_counts": agent_counts,
        "message": message,
    }


# ---- GET /patients/{patient_id}/labs ----
@router.get("/patients/{patient_id}/labs")
def list_patient_observations(patient_id: str) -> dict:
    """
    Return all lab observations for a patient from CORE.observation,
    newest first. Phase 3 task 7 deliverable.
    """
    import os
    import snowflake.connector
    from dotenv import load_dotenv

    load_dotenv()

    try:
        conn = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            database="clinical_db",
            warehouse="clinical_wh",
            role=os.environ["SNOWFLAKE_ROLE"],
        )
    except Exception as e:
        log.exception("Snowflake connect failed for labs read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                observation_id,
                test,
                value,
                unit,
                observation_date,
                source_document_id,
                created_at
            FROM clinical_db.core.observation
            WHERE patient_id = %s
            ORDER BY observation_date DESC NULLS LAST, created_at DESC
        """, (patient_id,))
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
        observations = [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        log.exception("CORE.observation read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    # Serialise dates and timestamps to strings for JSON
    for obs in observations:
        if obs.get("observation_date") is not None:
            obs["observation_date"] = obs["observation_date"].isoformat()
        if obs.get("created_at") is not None:
            obs["created_at"] = obs["created_at"].isoformat()

    return {
        "patient_id": patient_id,
        "count": len(observations),
        "observations": observations,
    }