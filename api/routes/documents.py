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

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks

from database.snowflake_writer import insert_raw_document
from ingestion.s3_uploader import upload
from api.jobs import create_job, mark_running, mark_completed, mark_failed

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
# ─── GET /documents/{document_id}/file (stream from S3) ────────────
@router.get("/documents/{document_id}/file")
def stream_document_file(document_id: str):
    """Stream the original uploaded file from S3 to the browser.

    Reads s3_key from CORE.document, downloads the object from S3,
    returns a StreamingResponse with the right Content-Type and an
    inline Content-Disposition so the browser renders it (PDF in
    iframe, image in <img>).
    """
    import os
    import io
    import mimetypes
    import boto3
    import snowflake.connector
    from dotenv import load_dotenv
    from fastapi.responses import StreamingResponse

    load_dotenv()

    # 1. Look up s3_key in Snowflake
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
        log.exception("Snowflake connect failed for file stream")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT s3_key, file_name, doc_type FROM clinical_db.core.document WHERE document_id = %s",
            (document_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found",
                              "message": f"Document {document_id} not found"}},
        )

    s3_key, file_name, doc_type = row

    # Notes have a synthetic s3_key like "notes://..." with no file in S3
    if not s3_key or s3_key.startswith("notes://"):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "no_file",
                              "message": f"Document {document_id} is a typed note and has no underlying file"}},
        )

    # 2. Download from S3 to memory
    try:
        s3 = boto3.client(
            "s3",
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        buf = io.BytesIO()
        s3.download_fileobj(os.environ["AWS_S3_BUCKET"], s3_key, buf)
        buf.seek(0)
    except Exception as e:
        log.exception("S3 download failed for %s (s3_key=%s)", document_id, s3_key)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Could not fetch file from S3: {e}"}},
        )

    # 3. Pick a Content-Type from the filename, falling back to PDF
    content_type, _ = mimetypes.guess_type(file_name or s3_key)
    if not content_type:
        content_type = "application/pdf"

    safe_name = file_name or f"{document_id}.bin"
    return StreamingResponse(
        buf,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, max-age=300",
        },
    )
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    type: str = Form(...),
    source: str | None = Form(None),
) -> dict:
    """
    Upload flow (Phase 4 L2 async):
      1. Push file to S3 (synchronous - small, fast)
      2. Insert row into RAW.raw_documents (synchronous)
      3. Create a job and schedule background processing
      4. Return immediately with {document_id, job_id, status: "queued"}
      5. Background task runs worker + agents, updates job status
    Frontend polls GET /api/jobs/{job_id} for completion.
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

    # 3. Create a job and schedule background processing
    job_id = create_job(
        kind="document_upload",
        context={
            "document_id": document_id,
            "patient_id": patient_id,
            "doc_type": type,
            "s3_key": s3_key,
        },
    )
    background_tasks.add_task(
        _process_document_in_background,
        job_id=job_id,
        document_id=document_id,
        patient_id=patient_id,
        s3_key=s3_key,
        document_date=document_date,
        doc_type=type,
    )

    # 4. Return immediately with the job id
    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "message": "Document uploaded; processing in background. Poll /api/jobs/{job_id}.",
    }


def _process_document_in_background(
    job_id: str,
    document_id: str,
    patient_id: str,
    s3_key: str,
    document_date,
    doc_type: str,
) -> None:
    """Run worker + orchestrator. Updates job status throughout.

    Runs after the HTTP response has been sent. Any exception is caught
    and recorded in the job so the frontend can show a failure state
    instead of hanging.
    """
    mark_running(job_id)
    try:
        from worker.document_processor import process_from_s3
        result = process_from_s3(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            document_date=document_date,
            doc_type=doc_type,
        )
        final_status = result.get("status", "unknown")
        entity_count = len(result.get("entities", []))
        agent_counts = result.get("agent_counts", {})

        if final_status == "processed":
            message = (
                f"Document processed - {entity_count} entities extracted, "
                f"{agent_counts.get('flags', 0)} flags, "
                f"{agent_counts.get('contradictions', 0)} contradictions."
            )
        else:
            message = "Document received but processing did not complete cleanly."

        mark_completed(job_id, {
            "document_id": document_id,
            "status": final_status,
            "entity_count": entity_count,
            "agent_counts": agent_counts,
            "message": message,
        })
    except Exception as e:
        log.exception("Background processing failed for %s", document_id)
        mark_failed(job_id, f"Worker pipeline failed: {e}")
# ─── DELETE /documents/{document_id} ────────────────────────────────
@router.delete("/documents/{document_id}")
def delete_document(document_id: str, background_tasks: BackgroundTasks) -> dict:
    """Delete a document and its derived agent data, then regenerate.

    Steps:
      1. Look up s3_key + patient_id from CORE.document (404 if missing)
      2. Delete S3 object (skip if notes:// synthetic key)
      3. DELETE rows from CORE.flag, CORE.contradiction, CORE.timeline_event,
         CORE.observation, CORE.entity, CORE.document, RAW.raw_documents
         that reference this document.
      4. Re-run agent orchestrator on remaining docs (best-effort; if it
         fails the delete still succeeded).
      5. Return summary.

    No transaction. Failure mid-way leaves a partial-delete state recoverable
    by re-running the DELETE.
    """
    import os
    import boto3
    import snowflake.connector
    from dotenv import load_dotenv
    from agents.orchestrator import run_agents

    load_dotenv()

    # 1. Look up
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
        log.exception("Snowflake connect failed for delete_document")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT patient_id, s3_key FROM clinical_db.core.document WHERE document_id = %s",
            (document_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "not_found",
                                  "message": f"Document {document_id} not found"}},
            )
        patient_id, s3_key = row

        # 2. S3 delete (skip for typed notes)
        s3_deleted = False
        if s3_key and not s3_key.startswith("notes://"):
            try:
                s3 = boto3.client(
                    "s3",
                    region_name=os.environ["AWS_REGION"],
                    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                )
                s3.delete_object(Bucket=os.environ["AWS_S3_BUCKET"], Key=s3_key)
                s3_deleted = True
            except Exception as e:
                log.exception("S3 delete failed for %s (key=%s)", document_id, s3_key)
                # Continue with DB cleanup even if S3 delete fails - the
                # orphaned object can be cleaned up later via lifecycle policy.

        # 3. Cascade deletes
        # Order matters only for FK respect; CORE.document referenced by
        # entity/observation/flag/contradiction/timeline. Delete leaves first.
        deletes = []

        cur.execute(
            "DELETE FROM clinical_db.core.flag WHERE source_document_id = %s",
            (document_id,),
        )
        deletes.append(("flag",          cur.rowcount))

        cur.execute(
            "DELETE FROM clinical_db.core.contradiction WHERE doc_a_id = %s OR doc_b_id = %s",
            (document_id, document_id),
        )
        deletes.append(("contradiction", cur.rowcount))

        cur.execute(
            "DELETE FROM clinical_db.core.timeline_event WHERE source_document_id = %s",
            (document_id,),
        )
        deletes.append(("timeline_event", cur.rowcount))

        cur.execute(
            "DELETE FROM clinical_db.core.observation WHERE source_document_id = %s",
            (document_id,),
        )
        deletes.append(("observation",   cur.rowcount))

        cur.execute(
            "DELETE FROM clinical_db.core.entity WHERE document_id = %s",
            (document_id,),
        )
        deletes.append(("entity",        cur.rowcount))

        cur.execute(
            "DELETE FROM clinical_db.core.document WHERE document_id = %s",
            (document_id,),
        )
        deletes.append(("document",      cur.rowcount))

        # RAW.raw_documents DELETE requires a permission we don't currently
        # hold (partner-side TODO: GRANT DELETE on RAW.raw_documents).
        # Best-effort: try the delete; on permission failure, leave the row
        # as orphan. RAW is the ingest landing zone; nothing reads from it
        # after CORE promotion, so an orphan row is harmless.
        try:
            cur.execute(
                "DELETE FROM clinical_db.raw.raw_documents WHERE document_id = %s",
                (document_id,),
            )
            deletes.append(("raw_documents", cur.rowcount))
        except Exception as e:
            log.warning("RAW.raw_documents delete skipped (likely permission): %s", e)
            deletes.append(("raw_documents", 0))

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.exception("DELETE cascade failed for %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Delete failed: {e}"}},
        )
    finally:
        conn.close()

    # 4. Re-run agents in background. The DB cascade above is already
    # committed; the response returns immediately so the UI can update.
    # The frontend polls /api/jobs/{job_id} for regeneration completion.
    job_id = create_job(
        kind="post_delete_regen",
        context={"patient_id": patient_id, "deleted_document_id": document_id},
    )
    background_tasks.add_task(
        _rerun_agents_in_background,
        job_id=job_id,
        patient_id=patient_id,
    )

    # 5. Summary
    return {
        "deleted":           True,
        "document_id":       document_id,
        "patient_id":        patient_id,
        "s3_deleted":        s3_deleted,
        "rows_deleted":      {table: count for table, count in deletes},
        "regen_job_id":      job_id,
        "regen_status":      "queued",
        "message":           "Document deleted. Agents regenerating in background; poll /api/jobs/{job_id}.",
    }


def _rerun_agents_in_background(job_id: str, patient_id: str) -> None:
    """After a delete, re-run the orchestrator on the patient's remaining
    documents. Slow because it touches every doc; runs in background."""
    mark_running(job_id)
    try:
        from agents.orchestrator import run_agents
        agent_state = run_agents(patient_id=patient_id, document_id=None)
        agent_counts = {
            "timeline_events": len(agent_state.get("timeline_events", [])),
            "flags": len(agent_state.get("flags", [])),
            "contradictions": len(agent_state.get("contradictions", [])),
            "briefing": agent_state.get("briefing") is not None,
            "errors": len(agent_state.get("errors", [])),
        }
        mark_completed(job_id, {
            "patient_id": patient_id,
            "agent_counts": agent_counts,
            "message": "Post-delete agent regeneration complete.",
        })
    except Exception as e:
        log.exception("Post-delete agent regeneration failed for %s", patient_id)
        mark_failed(job_id, f"Agent regeneration failed: {e}")
