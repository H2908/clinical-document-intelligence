"""Refactor POST /labs, POST /notes, DELETE /documents to use BackgroundTasks.

For labs: move worker pipeline (process_from_s3) into background, return job_id.
For notes: keep steps 1-5 synchronous (need entity count in response), move
  run_agents (step 6) into background.
For delete: keep steps 1-3 synchronous (DB cascade must commit before return),
  move agent re-run into background.

Atomic anchored replacements across two files.
"""
from pathlib import Path

# ============================================================================
# api/routes/labs.py
# ============================================================================
labs_path = Path("api/routes/labs.py")
labs_src = labs_path.read_text(encoding="utf-8")

if "BackgroundTasks" not in labs_src:
    labs_src = labs_src.replace(
        "from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status",
        "from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks",
    )
if "from api.jobs import" not in labs_src:
    labs_src = labs_src.replace(
        "from ingestion.s3_uploader import upload",
        "from ingestion.s3_uploader import upload\n"
        "from api.jobs import create_job, mark_running, mark_completed, mark_failed",
    )

old_labs_sig = '''async def upload_lab_report(
    patient_id: str,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    source: str | None = Form(None),
) -> dict:'''
new_labs_sig = '''async def upload_lab_report(
    patient_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    source: str | None = Form(None),
) -> dict:'''
if old_labs_sig not in labs_src:
    print("[FAIL] labs signature anchor not found")
    raise SystemExit(1)
labs_src = labs_src.replace(old_labs_sig, new_labs_sig)

old_labs_worker = '''    # 3 + 4. Worker + orchestrator
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
    }'''

new_labs_worker = '''    # 3. Create job and schedule background processing
    job_id = create_job(
        kind="lab_upload",
        context={
            "document_id": document_id,
            "patient_id": patient_id,
            "doc_type": "lab_report",
            "s3_key": s3_key,
        },
    )
    background_tasks.add_task(
        _process_lab_in_background,
        job_id=job_id,
        document_id=document_id,
        patient_id=patient_id,
        s3_key=s3_key,
        document_date=document_date,
    )

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "doc_type": "lab_report",
        "message": "Lab report uploaded; processing in background. Poll /api/jobs/{job_id}.",
    }


def _process_lab_in_background(
    job_id: str,
    document_id: str,
    patient_id: str,
    s3_key: str,
    document_date,
) -> None:
    mark_running(job_id)
    try:
        from worker.document_processor import process_from_s3
        result = process_from_s3(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            document_date=document_date,
            doc_type="lab_report",
        )
        final_status = result.get("status", "unknown")
        entity_count = len(result.get("entities", []))
        observation_count = len(result.get("observations", []))
        agent_counts = result.get("agent_counts", {})
        message = (
            f"Lab report processed - {observation_count} observations, "
            f"{entity_count} entities, {agent_counts.get('flags', 0)} flags."
            if final_status == "processed"
            else "Lab report received but processing did not complete cleanly."
        )
        mark_completed(job_id, {
            "document_id": document_id,
            "status": final_status,
            "doc_type": "lab_report",
            "observation_count": observation_count,
            "entity_count": entity_count,
            "agent_counts": agent_counts,
            "message": message,
        })
    except Exception as e:
        log.exception("Background lab processing failed for %s", document_id)
        mark_failed(job_id, f"Worker pipeline failed: {e}")'''

if old_labs_worker not in labs_src:
    print("[FAIL] labs worker-block anchor not found")
    raise SystemExit(1)
labs_src = labs_src.replace(old_labs_worker, new_labs_worker)

labs_path.write_text(labs_src, encoding="utf-8", newline="\n")
print("OK labs.py refactored")


# ============================================================================
# api/routes/notes.py - only the run_agents block goes to background
# ============================================================================
notes_path = Path("api/routes/notes.py")
notes_src = notes_path.read_text(encoding="utf-8")

if "BackgroundTasks" not in notes_src:
    notes_src = notes_src.replace(
        "from fastapi import APIRouter, Form, HTTPException, status",
        "from fastapi import APIRouter, Form, HTTPException, status, BackgroundTasks",
    )
if "from api.jobs import" not in notes_src:
    notes_src = notes_src.replace(
        "from nlp.date_normaliser import normalise_dates",
        "from nlp.date_normaliser import normalise_dates\n"
        "from api.jobs import create_job, mark_running, mark_completed, mark_failed",
    )

old_notes_sig = '''async def add_clinician_note(
    patient_id: str,
    note: ClinicianNote,
) -> dict:'''
new_notes_sig = '''async def add_clinician_note(
    patient_id: str,
    note: ClinicianNote,
    background_tasks: BackgroundTasks = None,
) -> dict:'''
if old_notes_sig not in notes_src:
    print("[FAIL] notes signature anchor not found")
    raise SystemExit(1)
notes_src = notes_src.replace(old_notes_sig, new_notes_sig)

old_notes_agents = '''    # 6. Run agent orchestrator
    agent_counts = {}
    try:
        from agents.orchestrator import run_agents
        agent_state = run_agents(
            patient_id=patient_id,
            document_id=document_id,
        )
        agent_counts = {
            "timeline_events": len(agent_state.get("timeline_events", [])),
            "flags": len(agent_state.get("flags", [])),
            "contradictions": len(agent_state.get("contradictions", [])),
            "briefing": agent_state.get("briefing") is not None,
            "errors": len(agent_state.get("errors", [])),
        }
    except Exception as e:
        log.exception("Agent orchestrator crashed for note %s", document_id)
        agent_counts = {"error": str(e)}

    return {
        "document_id": document_id,
        "status": "processed",
        "doc_type": "clinician_note",
        "entity_count": len(entities),
        "agent_counts": agent_counts,
        "message": (
            f"Note recorded - {len(entities)} entities extracted, "
            f"{agent_counts.get('flags', 0)} flags."
        ),
    }'''

new_notes_agents = '''    # 6. Run agents in background; respond now with what we know already
    job_id = create_job(
        kind="note_agents",
        context={"document_id": document_id, "patient_id": patient_id},
    )
    if background_tasks is not None:
        background_tasks.add_task(
            _run_note_agents_in_background,
            job_id=job_id,
            patient_id=patient_id,
            document_id=document_id,
        )
    else:
        # Fallback for callers that didn't pass BackgroundTasks - run inline
        _run_note_agents_in_background(job_id, patient_id, document_id)

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "saved",
        "doc_type": "clinician_note",
        "entity_count": len(entities),
        "message": (
            f"Note saved - {len(entities)} entities extracted. "
            "Agents running in background. Poll /api/jobs/{job_id}."
        ),
    }


def _run_note_agents_in_background(
    job_id: str,
    patient_id: str,
    document_id: str,
) -> None:
    mark_running(job_id)
    try:
        from agents.orchestrator import run_agents
        agent_state = run_agents(patient_id=patient_id, document_id=document_id)
        agent_counts = {
            "timeline_events": len(agent_state.get("timeline_events", [])),
            "flags": len(agent_state.get("flags", [])),
            "contradictions": len(agent_state.get("contradictions", [])),
            "briefing": agent_state.get("briefing") is not None,
            "errors": len(agent_state.get("errors", [])),
        }
        mark_completed(job_id, {
            "document_id": document_id,
            "agent_counts": agent_counts,
            "message": (
                f"Note agents complete - {agent_counts['flags']} flags, "
                f"{agent_counts['contradictions']} contradictions."
            ),
        })
    except Exception as e:
        log.exception("Agent orchestrator crashed for note %s", document_id)
        mark_failed(job_id, f"Agent orchestrator failed: {e}")'''

if old_notes_agents not in notes_src:
    print("[FAIL] notes agents-block anchor not found")
    raise SystemExit(1)
notes_src = notes_src.replace(old_notes_agents, new_notes_agents)

notes_path.write_text(notes_src, encoding="utf-8", newline="\n")
print("OK notes.py refactored")


# ============================================================================
# api/routes/documents.py - DELETE only: move agent re-run to background
# ============================================================================
docs_path = Path("api/routes/documents.py")
docs_src = docs_path.read_text(encoding="utf-8")

# Need to see the DELETE function's agent re-run block to anchor on.
# Show the section to the user; this script writes the import + helper but
# leaves the actual DELETE refactor to a follow-up since I don't have full
# visibility on the function's tail.

# 1. Update delete_document signature to take BackgroundTasks
old_del_sig = "def delete_document(document_id: str) -> dict:"
new_del_sig = "def delete_document(document_id: str, background_tasks: BackgroundTasks) -> dict:"
if old_del_sig in docs_src and "background_tasks: BackgroundTasks" not in docs_src.split(old_del_sig)[1][:200]:
    docs_src = docs_src.replace(old_del_sig, new_del_sig, 1)

# 2. Add the background helper at module bottom (the run_agents-on-remaining)
helper_block = '''


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
'''

if "_rerun_agents_in_background" not in docs_src:
    docs_src = docs_src.rstrip() + helper_block

docs_path.write_text(docs_src, encoding="utf-8", newline="\n")
print("OK documents.py: DELETE signature + helper added (manual step needed for the agent-call replacement)")
print()
print("NEXT: I need to see the tail of delete_document where run_agents is called.")
print("Run: Get-Content api/routes/documents.py | Select-Object -Skip 420 -First 60")