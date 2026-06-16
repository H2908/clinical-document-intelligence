"""DELETE refactor v2 - search for anchor with whitespace tolerance.

Same intent as v1: move the synchronous run_agents call after the DB
commit into a background task. v1 failed because my anchor string had
a different blank-line layout than the file on disk. v2 uses regex
with \\s* between blocks so leading/trailing whitespace doesn't matter.
"""
import re
from pathlib import Path

p = Path("api/routes/documents.py")
src = p.read_text(encoding="utf-8")

# Build a regex that matches the synchronous regen block flexibly.
# Anchors: the "# 4. Re-run" comment through the "regenerated": regen close-brace
pattern = re.compile(
    r"    # 4\. Re-run agents on remaining docs \(best-effort\)\s*\n"
    r"    regen: dict = \{\}\s*\n"
    r"    try:\s*\n"
    r'        state = run_agents\(patient_id=patient_id, document_id=f"<deleted-\{document_id\}>"\)\s*\n'
    r"        regen = \{\s*\n"
    r'            "timeline_events": len\(state\.get\("timeline_events", \[\]\)\),\s*\n'
    r'            "flags":           len\(state\.get\("flags",           \[\]\)\),\s*\n'
    r'            "contradictions":  len\(state\.get\("contradictions",  \[\]\)\),\s*\n'
    r'            "briefing":        state\.get\("briefing"\) is not None,\s*\n'
    r'            "errors":          len\(state\.get\("errors",          \[\]\)\),\s*\n'
    r"        \}\s*\n"
    r"    except Exception as e:\s*\n"
    r'        log\.exception\("Agent regen failed after delete of %s", document_id\)\s*\n'
    r'        regen = \{"error": f"\{type\(e\)\.__name__\}: \{e\}"\}\s*\n'
    r"\s*\n"
    r"    # 5\. Summary\s*\n"
    r"    return \{\s*\n"
    r'        "deleted":           True,\s*\n'
    r'        "document_id":       document_id,\s*\n'
    r'        "patient_id":        patient_id,\s*\n'
    r'        "s3_deleted":        s3_deleted,\s*\n'
    r'        "rows_deleted":      \{table: count for table, count in deletes\},\s*\n'
    r'        "regenerated":       regen,\s*\n'
    r"    \}"
)

matches = pattern.findall(src)
print(f"Pattern matches: {len(matches)}")

# But the actual file may have different whitespace inside the dict literal
# (e.g. fewer spaces between key and value than I assumed). Try a looser pattern.
loose = re.compile(
    r"    # 4\. Re-run agents on remaining docs.*?"
    r'        "regenerated":\s+regen,\s*\n'
    r"    \}",
    re.DOTALL,
)
loose_matches = loose.findall(src)
print(f"Loose pattern matches: {len(loose_matches)}")

if len(loose_matches) != 1:
    print("[FAIL] loose pattern did not match exactly once - inspecting:")
    print()
    # Print 80 chars around the # 4. comment to see what's actually there
    idx = src.find("# 4. Re-run agents on remaining docs")
    if idx == -1:
        print("'# 4. Re-run agents on remaining docs' not found in file at all")
    else:
        snippet = src[idx:idx + 1500]
        print(f"--- 1500 chars from line containing # 4 ---")
        print(snippet)
    raise SystemExit(1)

# Confirmed: exactly one match. Do the replacement.
new_block = '''    # 4. Re-run agents in background. The DB cascade above is already
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

# Also make sure create_job is imported in documents.py
if "from api.jobs import" not in src:
    src = src.replace(
        "from ingestion.s3_uploader import upload",
        "from ingestion.s3_uploader import upload\n"
        "from api.jobs import create_job, mark_running, mark_completed, mark_failed",
        1,
    )
elif "create_job" not in src.split("from api.jobs import")[1].split("\n")[0]:
    # The import line exists but doesn't include create_job - rewrite it
    src = re.sub(
        r"from api\.jobs import [^\n]+",
        "from api.jobs import create_job, mark_running, mark_completed, mark_failed",
        src,
        count=1,
    )

src = loose.sub(new_block, src, count=1)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK DELETE refactored")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")