"""Patch cleanup_pat_test_01_entities.py to delete observations
alongside entities before re-processing each doc.

Today's cleanup loop calls delete_entities_for_document(doc_id) but
NOT delete_observations. process_from_s3 then runs lab_parser which
re-extracts observations - appending to whatever's already in
CORE.observation. Result: duplicates compound on every cleanup run.

Fix: delete observations for the doc before re-processing. Same
pattern as entity delete: scoped to one doc via source_document_id.

Atomic anchored replacement adds delete_observations_for_document
helper + a call in the main loop.
"""
from pathlib import Path

p = Path("cleanup_pat_test_01_entities.py")
src = p.read_text(encoding="utf-8")

if "def delete_observations_for_document" in src:
    print("[SKIP] observation-dedup already patched")
    raise SystemExit(0)

# 1. Add the helper after delete_entities_for_document
old_helper = '''def delete_entities_for_document(document_id: str) -> int:
    """DELETE entity rows for one document. Returns rows deleted."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.entity WHERE document_id = %s",
            (document_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()'''

new_helper = '''def delete_entities_for_document(document_id: str) -> int:
    """DELETE entity rows for one document. Returns rows deleted."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.entity WHERE document_id = %s",
            (document_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def delete_observations_for_document(document_id: str) -> int:
    """DELETE observation rows for one document. Returns rows deleted.

    Needed because process_from_s3 re-extracts observations via lab_parser
    and appends without dedup; without explicit delete, duplicates compound
    on every cleanup run.
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.observation WHERE source_document_id = %s",
            (document_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()'''

if old_helper not in src:
    print("[FAIL] delete_entities_for_document anchor not found")
    raise SystemExit(1)
src = src.replace(old_helper, new_helper)

# 2. Call delete_observations_for_document in the loop, alongside the
#    existing delete_entities_for_document call
old_loop_call = '''        # 1. DELETE existing rows
        deleted = delete_entities_for_document(doc_id)
        print(f"  Deleted: {deleted} rows")'''

new_loop_call = '''        # 1. DELETE existing entity + observation rows for this doc
        deleted_e = delete_entities_for_document(doc_id)
        deleted_o = delete_observations_for_document(doc_id)
        print(f"  Deleted: {deleted_e} entity rows, {deleted_o} observation rows")'''

if old_loop_call not in src:
    print("[FAIL] loop-call anchor not found")
    raise SystemExit(1)
src = src.replace(old_loop_call, new_loop_call)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK cleanup script patched: observations deleted alongside entities")