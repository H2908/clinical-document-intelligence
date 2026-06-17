"""Refactor DELETE /documents to move the agent re-run into a background task.

Steps 1-3 (lookup, S3 delete, DB cascade) stay synchronous - the user
needs the delete to be committed before the response returns. Step 4
(re-run agents on the patient's remaining docs, slow) moves to background.
The _rerun_agents_in_background helper was added in the previous refactor.

Atomic anchored replacement on the run_agents block.
"""
from pathlib import Path

p = Path("api/routes/documents.py")
src = p.read_text(encoding="utf-8")

old = '''    # 4. Re-run agents on remaining docs (best-effort)
    regen: dict = {}
    try:
        state = run_agents(patient_id=patient_id, document_id=f"<deleted-{document_id}>")
        regen = {
            "timeline_events": len(state.get("timeline_events", [])),
            "flags":           len(state.get("flags", [])),
            "contradictions":  len(state.get("contradictions", [])),
            "briefing":        state.get("briefing") is not None,
            "errors":          len(state.get("errors", [])),
        }
    except Exception as e:
        log.exception("Agent regen failed after delete of %s", document_id)
        regen = {"error": f"{type(e).__name__}: {e}"}
    # 5. Summary
    return {
        "deleted":           True,
        "document_id":       document_id,
        "patient_id":        patient_id,
        "s3_deleted":        s3_deleted,
        "rows_deleted":      {table: count for table, count in deletes},
        "regenerated":       regen,
    }'''

new = '''    # 4. Re-run agents in background. The DB cascade above is already
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
    }'''

if old not in src:
    print("[FAIL] DELETE run_agents block anchor not found")
    raise SystemExit(1)
if src.count(old) > 1:
    print(f"[FAIL] anchor matched {src.count(old)} times")
    raise SystemExit(1)

# The `from agents.orchestrator import run_agents` inline import is no longer
# needed in the synchronous block (the background helper imports it itself).
# Leave it in place - it's harmless and removing it adds a separate edit.

src = src.replace(old, new)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK DELETE refactored to background-task regeneration")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")