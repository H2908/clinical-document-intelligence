"""
Document upload + retrieval endpoints.

Phase 1: GET mocks for list and detail views.
Phase 2: POST endpoint — uploads file to S3, inserts RAW row, runs NLP worker.
Phase 3: Worker invokes the agent orchestrator after entities land.
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


# ─── GET /patients/{patient_id}/documents (real Snowflake) ──────────
@router.get("/patients/{patient_id}/documents")
def list_patient_documents(patient_id: str) -> dict:
    """List a patient's documents from CORE.document, newest first."""
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
    except Exception:
        log.exception("Snowflake connect failed for documents list")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                document_id,
                file_name,
                doc_type,
                source,
                document_date,
                status
            FROM clinical_db.core.document
            WHERE patient_id = %s
            ORDER BY document_date DESC NULLS LAST, created_at DESC
        """, (patient_id,))
        rows = cur.fetchall()
    except Exception as e:
        log.exception("CORE.document read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    documents = []
    for row in rows:
        doc_id, file_name, doc_type, source, doc_date, doc_status = row
        documents.append({
            "id":     doc_id,
            "name":   file_name or doc_id,
            "type":   doc_type or "unknown",
            "source": source or "",
            "date":   doc_date.isoformat() if doc_date else "",
            "status": doc_status or "processed",
        })

    return {"documents": documents}

# ─── GET /documents/{document_id} (Phase 1 mock) ────────────────────
@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    return {
        "id": document_id,
        "name": "Cardiology_28Feb2024.pdf",
        "type": "clinic_letter",
        "source": "Trust EPR",
        "date": "2024-02-28",
        "status": "processed",
        "extracted_text": (
            "Patient reports penicillin allergy - rash on exposure 2019. "
            "Avoid beta-lactams. Echocardiogram on 28 Feb 2024 confirms "
            "dilated cardiomyopathy with LVEF 32%. Commenced bisoprolol 2.5 mg."
        ),
        "entities": [
            {"text": "penicillin allergy", "type": "Conflict", "start": 16, "end": 34},
            {"text": "dilated cardiomyopathy", "type": "Diagnosis", "start": 108, "end": 130},
            {"text": "bisoprolol 2.5 mg", "type": "Drug", "start": 165, "end": 182},
            {"text": "28 Feb 2024", "type": "Date", "start": 80, "end": 91},
        ],
        "image_url": None,
        "lab_results": None,
    }


# ─── POST /patients/{patient_id}/documents (Phase 2 + 3) ────────────
@router.post(
    "/patients/{patient_id}/documents",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    patient_id: str,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    type: str = Form(...),
    source: str | None = Form(None),
) -> dict:
    """
    Upload flow:
      1. Push file to S3
      2. Insert row into RAW.raw_documents (status='pending')
      3. Run NLP worker synchronously — parses, extracts entities, writes to CORE
      4. Worker invokes agent orchestrator — timeline, flags, contradictions, briefing
      5. Return summary counts to caller
    """
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    original_ext = Path(file.filename or "").suffix or ".pdf"
    s3_key = f"uploads/{patient_id}/{document_id}{original_ext}"
    file_name = file.filename or f"{document_id}{original_ext}"

    # 1. S3 upload
    try:
        upload(file.file, s3_key)
    except Exception as e:
        log.exception("S3 upload failed for %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 upload failed: {e}"}},
        )

    # 2. RAW row
    try:
        insert_raw_document(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            file_name=file_name,
            doc_type=type,
            document_date=document_date,
            source=source,
        )
    except Exception as e:
        log.exception("RAW insert failed for %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 ok but DB insert failed: {e}"}},
        )

    # 3 + 4. Worker + orchestrator (synchronous for Phase 3; async in Phase 5)
    from worker.document_processor import process_from_s3
    try:
        result = process_from_s3(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            document_date=document_date,
            doc_type=type,
        )
        final_status = result["status"]
        entity_count = len(result.get("entities", []))
        agent_counts = result.get("agent_counts", {})
    except Exception as e:
        log.exception("Worker pipeline failed for %s", document_id)
        final_status = "failed"
        entity_count = 0
        agent_counts = {}

    # 5. Build response
    if final_status == "processed":
        message = (
            f"Document processed — {entity_count} entities extracted, "
            f"{agent_counts.get('flags', 0)} flags, "
            f"{agent_counts.get('contradictions', 0)} contradictions."
        )
    else:
        message = "Document received but processing failed — check logs."

    return {
        "document_id": document_id,
        "status": final_status,
        "entity_count": entity_count,
        "agent_counts": agent_counts,
        "message": message,
    }