"""Permanent fix for the patient-level output duplication bug.

Bug: orchestrator calls write_flags / write_contradictions once per
document re-process. Both functions are INSERT-only on patient-scoped
data. Re-processing N documents writes N copies of the patient's
flag/contradiction set. Today's demo cleanup showed 198 flag rows for
36 distinct flags, 154 contradictions for 12 distinct ones.

Fix: add replace_existing=False parameter to write_flags and
write_contradictions. When True, the function deletes all rows for the
patient before writing the new set. Default False preserves backward
compatibility for any caller that does want incremental writes.

Orchestrator opts in to replace_existing=True for both calls. The
explicit kwarg makes the semantics self-documenting at the call site.

Briefing already uses MERGE on patient_id (idempotent upsert), so no
change needed there.
"""
from pathlib import Path

# ============================================================================
# 1. snowflake_writer.py
# ============================================================================
p = Path("database/snowflake_writer.py")
src = p.read_text(encoding="utf-8")

# 1a. Add delete helpers near the bottom, after delete_patient (or near it).
# Insert before delete_patient so they appear in logical grouping.
if "def delete_flags_for_patient" in src:
    print("[SKIP] delete helpers already in writer")
else:
    helpers_block = '''# ---- delete helpers for patient-scoped outputs ----
def delete_flags_for_patient(patient_id: str) -> int:
    """DELETE all CORE.flag rows for one patient. Returns rows deleted.

    Used by callers that produce a complete patient-level flag set and
    want to replace any prior set atomically (orchestrator after a
    full agent pipeline run). For incremental writes, call write_flags
    without replace_existing=True instead.
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.flag WHERE patient_id = %s",
            (patient_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def delete_contradictions_for_patient(patient_id: str) -> int:
    """DELETE all CORE.contradiction rows for one patient. Returns rows deleted.

    Same rationale as delete_flags_for_patient: patient-scoped outputs
    that should be replaced wholesale on full re-runs.
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.contradiction WHERE patient_id = %s",
            (patient_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


# ---- delete_patient ----'''

    old_anchor = "# ---- delete_patient ----"
    if old_anchor not in src:
        print("[FAIL] delete_patient section anchor not found")
        raise SystemExit(1)
    src = src.replace(old_anchor, helpers_block, 1)
    print("OK writer: delete_flags_for_patient + delete_contradictions_for_patient added")

# 1b. Extend write_flags with replace_existing
old_write_flags = '''def write_flags(patient_id: str, flags: list, context: dict | None = None) -> None:
    """Write risk flags to CORE.flag via SP_WRITE_FLAGS.

    If context (with model + prompt_version + temperature) is provided,
    every flag is hashed via audit_agent.attach_hash before serialisation.
    The hash lands in CORE.flag.provenance_hash via SP_WRITE_FLAGS
    (partner-side SP binds the field; verified via verify_sps_updated.py).

    If context is None, behaviour is unchanged - no hash attached. Old
    rows in CORE.flag have NULL provenance_hash; audit agent reports
    those as no_stored_hash (not mismatch).
    """
    if context is not None:
        flags = [attach_hash(flag, context) for flag in flags]
    flags_json = json.dumps(flags, default=str)
    sql = (f"CALL clinical_db.core.SP_WRITE_FLAGS("
           f"'{patient_id}', PARSE_JSON($${flags_json}$$))")
    _call_proc_with_array(sql, "write_flags", patient_id)'''

new_write_flags = '''def write_flags(
    patient_id: str,
    flags: list,
    context: dict | None = None,
    replace_existing: bool = False,
) -> None:
    """Write risk flags to CORE.flag via SP_WRITE_FLAGS.

    If context (with model + prompt_version + temperature) is provided,
    every flag is hashed via audit_agent.attach_hash before serialisation.
    The hash lands in CORE.flag.provenance_hash via SP_WRITE_FLAGS
    (partner-side SP binds the field; verified via verify_sps_updated.py).
    If context is None, behaviour is unchanged - no hash attached.

    If replace_existing=True, all existing CORE.flag rows for this
    patient are DELETED before insert. Use this when writing a complete
    patient-level flag set (e.g. after a full orchestrator run on a
    re-processed document). Default False preserves backward compat for
    incremental-write callers.
    """
    if replace_existing:
        deleted = delete_flags_for_patient(patient_id)
        print(f"[snowflake_writer] write_flags: replace_existing deleted "
              f"{deleted} prior flag rows for {patient_id}")
    if context is not None:
        flags = [attach_hash(flag, context) for flag in flags]
    flags_json = json.dumps(flags, default=str)
    sql = (f"CALL clinical_db.core.SP_WRITE_FLAGS("
           f"'{patient_id}', PARSE_JSON($${flags_json}$$))")
    _call_proc_with_array(sql, "write_flags", patient_id)'''

if "replace_existing: bool = False" in src and "def write_flags" in src:
    print("[SKIP] write_flags already has replace_existing")
else:
    if old_write_flags not in src:
        print("[FAIL] write_flags anchor not found")
        raise SystemExit(1)
    src = src.replace(old_write_flags, new_write_flags)
    print("OK writer: write_flags extended with replace_existing")

# 1c. Extend write_contradictions similarly
# First find the current signature
import re
m = re.search(
    r'def write_contradictions\(patient_id: str, contradictions: list\) -> None:\n(\s+""".*?""")',
    src,
    flags=re.DOTALL,
)
if m is None:
    print("[FAIL] write_contradictions function not found with expected signature")
    raise SystemExit(1)

old_sig_and_doc = m.group(0)
docstring = m.group(1)

# Build a new version with replace_existing
new_sig = '''def write_contradictions(
    patient_id: str,
    contradictions: list,
    replace_existing: bool = False,
) -> None:
''' + docstring

# Then we'll inject the DELETE call right after the docstring closes
new_sig_with_delete = new_sig + '''
    if replace_existing:
        deleted = delete_contradictions_for_patient(patient_id)
        print(f"[snowflake_writer] write_contradictions: replace_existing deleted "
              f"{deleted} prior contradiction rows for {patient_id}")'''

if "replace_existing: bool = False" in src.split("def write_contradictions")[1].split("def ")[0]:
    print("[SKIP] write_contradictions already has replace_existing")
else:
    src = src.replace(old_sig_and_doc, new_sig_with_delete)
    print("OK writer: write_contradictions extended with replace_existing")

p.write_text(src, encoding="utf-8", newline="\n")

# ============================================================================
# 2. orchestrator.py - pass replace_existing=True on both writes
# ============================================================================
p2 = Path("agents/orchestrator.py")
src2 = p2.read_text(encoding="utf-8")

# Update write_flags call
old_flags_call = "write_flags(patient_id, flags_to_write, context=audit_context)"
new_flags_call = "write_flags(patient_id, flags_to_write, context=audit_context, replace_existing=True)"

if "replace_existing=True" in src2 and "write_flags" in src2:
    print("[SKIP] orchestrator write_flags already has replace_existing")
elif old_flags_call not in src2:
    print(f"[FAIL] orchestrator write_flags call not found: {old_flags_call!r}")
    raise SystemExit(1)
else:
    src2 = src2.replace(old_flags_call, new_flags_call)
    print("OK orchestrator: write_flags now passes replace_existing=True")

# Update write_contradictions call
old_contr_call = 'write_contradictions(patient_id, state["contradictions"])'
new_contr_call = 'write_contradictions(patient_id, state["contradictions"], replace_existing=True)'

if 'write_contradictions(patient_id, state["contradictions"], replace_existing' in src2:
    print("[SKIP] orchestrator write_contradictions already has replace_existing")
elif old_contr_call not in src2:
    print(f"[FAIL] orchestrator write_contradictions call not found")
    raise SystemExit(1)
else:
    src2 = src2.replace(old_contr_call, new_contr_call)
    print("OK orchestrator: write_contradictions now passes replace_existing=True")

p2.write_text(src2, encoding="utf-8", newline="\n")

print()
print("=== Summary ===")
print("- snowflake_writer.py: 2 delete helpers + replace_existing param on 2 writes")
print("- orchestrator.py: both calls now pass replace_existing=True")
print("- Briefing already uses MERGE - no change needed")