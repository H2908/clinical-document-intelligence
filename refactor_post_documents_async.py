"""Refactor POST /patients/{patient_id}/documents to use BackgroundTasks.

The slow synchronous block (worker.process_from_s3 -> agents) moves
into a function that runs after the response is sent. The endpoint
creates a job, schedules the background task, and returns the job_id.

Atomic: anchored on the existing function body.
"""
from pathlib import Path

p = Path("api/routes/documents.py")
src = p.read_text(encoding="utf-8")

# 1. Add BackgroundTasks to FastAPI imports if not present
old_import = "from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status"
new_import = "from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks"
if old_import in src and "BackgroundTasks" not in src:
    src = src.replace(old_import, new_import)

# 2. Add jobs import after the existing imports block (after s3_uploader)
if "from api.jobs import" not in src:
    old_jobs_anchor = "from ingestion.s3_uploader import upload"
    new_jobs_anchor = ("from ingestion.s3_uploader import upload\n"
                       "from api.jobs import create_job, mark_running, mark_completed, mark_failed")
    if old_jobs_anchor not in src:
        print("[FAIL] s3_uploader import anchor not found")
        raise SystemExit(1)
    src = src.replace(old_jobs_anchor, new_jobs_anchor)

# 3. Replace the entire upload_document function body with the async version
# Anchor on the function signature + docstring + body up to the return
old_block = '''async def upload_document(
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
      3. Run NLP worker synchronously \u2014 parses, extracts entities, writes to CORE
      4. Worker invokes agent orchestrator \u2014 timeline, flags, contradictions, briefing
      5. Return summary counts to caller
    """'''

new_block = '''async def upload_document(
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
    """'''

if old_block not in src:
    print("[FAIL] upload_document signature/docstring anchor not found")
    raise SystemExit(1)
src = src.replace(old_block, new_block)

# 4. Replace the synchronous worker call (steps 3+4) and the response builder
# with: create_job + schedule background task + return immediately
old_worker_block = '''    # 3 + 4. Worker + orchestrator (synchronous for Phase 3; async in Phase 5)
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
            f"Document processed \u2014 {entity_count} entities extracted, "
            f"{agent_counts.get('flags', 0)} flags, "
            f"{agent_counts.get('contradictions', 0)} contradictions."
        )
    else:
        message = "Document received but processing failed \u2014 check logs."

    return {
        "document_id": document_id,
        "status": final_status,
        "entity_count": entity_count,
        "agent_counts": agent_counts,
        "message": message,
    }'''

new_worker_block = '''    # 3. Create a job and schedule background processing
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
        mark_failed(job_id, f"Worker pipeline failed: {e}")'''

if old_worker_block not in src:
    print("[FAIL] worker-block anchor not found")
    raise SystemExit(1)
src = src.replace(old_worker_block, new_worker_block)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK upload_document refactored to use BackgroundTasks")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")