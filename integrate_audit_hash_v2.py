"""V2: integrate audit_agent.attach_hash into write_flags chain.

Two anchored edits:
  1. database/snowflake_writer.py - extend write_flags signature with
     optional context param; if context given, hash every flag first.
  2. agents/orchestrator.py - pass context to write_flags call so the
     v1.3 instrument's flags carry provenance hashes from now on.

V1 aborted because my dotenv anchor was wrong. V2 anchors on the actual
file shape.

Idempotent: re-running after partial success no-ops.
"""
from pathlib import Path

# ============================================================================
# 1. snowflake_writer.py - add import + extend write_flags signature
# ============================================================================
p = Path("database/snowflake_writer.py")
src = p.read_text(encoding="utf-8")

# 1a. Add audit_agent import after snowflake import
old_imports = '''import os
import json
import snowflake.connector
from dotenv import load_dotenv'''
new_imports = '''import os
import json
import snowflake.connector
from dotenv import load_dotenv
from agents.audit_agent import attach_hash'''

if "from agents.audit_agent import attach_hash" in src:
    print("[SKIP] writer: audit_agent already imported")
else:
    if old_imports not in src:
        print("[FAIL] writer imports anchor not found")
        raise SystemExit(1)
    src = src.replace(old_imports, new_imports)
    print("OK writer: audit_agent import added")

# 1b. Extend write_flags signature
old_write_flags = '''def write_flags(patient_id: str, flags: list) -> None:
    """Write risk flags to CORE.flag via SP_WRITE_FLAGS."""
    flags_json = json.dumps(flags, default=str)
    sql = (f"CALL clinical_db.core.SP_WRITE_FLAGS("
           f"'{patient_id}', PARSE_JSON($${flags_json}$$))")
    _call_proc_with_array(sql, "write_flags", patient_id)'''

new_write_flags = '''def write_flags(patient_id: str, flags: list, context: dict | None = None) -> None:
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

if "context: dict | None = None" in src:
    print("[SKIP] writer: write_flags already extended")
else:
    if old_write_flags not in src:
        print("[FAIL] writer write_flags anchor not found")
        raise SystemExit(1)
    src = src.replace(old_write_flags, new_write_flags)
    print("OK writer: write_flags signature extended")

p.write_text(src, encoding="utf-8", newline="\n")

# ============================================================================
# 2. orchestrator.py - pass context to write_flags
# ============================================================================
p2 = Path("agents/orchestrator.py")
src2 = p2.read_text(encoding="utf-8")

# Constants for the audit context: locked production state.
# These should track FLAG_SECOND_PASS_VERSION in prompts.py and the
# Anthropic model + temperature in flag_agent.py. If those drift, the
# hash will reflect stale context - keep them coordinated.
new_context_block = '''            # Hash flags for tamper-evidence. Context tracks the locked
            # production state of the v1.3 grounding instrument; if model,
            # prompt_version, or temperature change in prompts.py, update
            # this dict too so the hash reflects the real generation context.
            audit_context = {
                "model": "claude-sonnet-4-6",
                "prompt_version": "v1.3",
                "temperature": 0.7,
            }
            write_flags(patient_id, flags_to_write, context=audit_context)'''

old_call = "write_flags(patient_id, flags_to_write)"

if "audit_context" in src2:
    print("[SKIP] orchestrator: audit_context already wired")
else:
    if old_call not in src2:
        print("[FAIL] orchestrator write_flags call anchor not found")
        raise SystemExit(1)
    # Verify exactly one occurrence so we don't change two places
    count = src2.count(old_call)
    if count != 1:
        print(f"[FAIL] expected 1 write_flags call, found {count}")
        raise SystemExit(1)
    src2 = src2.replace(old_call, new_context_block)
    print("OK orchestrator: write_flags call now passes audit_context")

p2.write_text(src2, encoding="utf-8", newline="\n")

print()
print("=== Summary ===")
print("snowflake_writer.write_flags: optional context param, hashes when given")
print("orchestrator: passes audit_context (v1.3 production state)")
print()
print("Next: smoke test")
print("  1. Upload one doc via API or run cleanup script on one doc")
print("  2. Query: SELECT category, provenance_hash FROM CORE.flag "
      "WHERE patient_id='pat_test_01' LIMIT 5")
print("  3. Expect: provenance_hash populated (64-char hex) on new flags")