"""Fix the broken _connect() calls in the two new delete helpers.

The patch script used _connect() but the actual helper in this file is
_get_connection(). The two new functions would NameError on first call.

Two anchored replacements. The rest of the patch (replace_existing
parameters, orchestrator updates) is correct - this only touches the
inside of the two new delete helpers.
"""
from pathlib import Path

p = Path("database/snowflake_writer.py")
src = p.read_text(encoding="utf-8")

# Inside delete_flags_for_patient
old_1 = '''def delete_flags_for_patient(patient_id: str) -> int:
    """DELETE all CORE.flag rows for one patient. Returns rows deleted.

    Used by callers that produce a complete patient-level flag set and
    want to replace any prior set atomically (orchestrator after a
    full agent pipeline run). For incremental writes, call write_flags
    without replace_existing=True instead.
    """
    conn = _connect()'''
new_1 = '''def delete_flags_for_patient(patient_id: str) -> int:
    """DELETE all CORE.flag rows for one patient. Returns rows deleted.

    Used by callers that produce a complete patient-level flag set and
    want to replace any prior set atomically (orchestrator after a
    full agent pipeline run). For incremental writes, call write_flags
    without replace_existing=True instead.
    """
    conn = _get_connection()'''

if old_1 not in src:
    print("[FAIL] delete_flags_for_patient anchor not found")
    raise SystemExit(1)
src = src.replace(old_1, new_1)
print("OK delete_flags_for_patient: _get_connection")

# Inside delete_contradictions_for_patient
old_2 = '''def delete_contradictions_for_patient(patient_id: str) -> int:
    """DELETE all CORE.contradiction rows for one patient. Returns rows deleted.

    Same rationale as delete_flags_for_patient: patient-scoped outputs
    that should be replaced wholesale on full re-runs.
    """
    conn = _connect()'''
new_2 = '''def delete_contradictions_for_patient(patient_id: str) -> int:
    """DELETE all CORE.contradiction rows for one patient. Returns rows deleted.

    Same rationale as delete_flags_for_patient: patient-scoped outputs
    that should be replaced wholesale on full re-runs.
    """
    conn = _get_connection()'''

if old_2 not in src:
    print("[FAIL] delete_contradictions_for_patient anchor not found")
    raise SystemExit(1)
src = src.replace(old_2, new_2)
print("OK delete_contradictions_for_patient: _get_connection")

p.write_text(src, encoding="utf-8", newline="\n")
print("\n=== Summary ===")
print("Two delete helpers now use the correct _get_connection() helper.")