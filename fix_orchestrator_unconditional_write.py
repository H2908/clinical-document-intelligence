"""Fix the orchestrator's post-delete regen bug.

Two related bugs in agents/orchestrator.py:_write_outputs:

  1. `return state` is indented inside the `if state["briefing"]:` block.
     When briefing is None, the function falls off the end returning
     None - which LangGraph interprets as state corruption.

  2. write_flags and write_contradictions are only called if the new
     output is non-empty. This means replace_existing=True never fires
     when the new output is empty - leaving stale flags/contradictions
     from before the regen.

Bug surfaced when delete-document path triggered a regen that produced
fewer flags than before. Demo showed 12 flag rows referencing 6
documents when only 3 documents remained.

Fix: call write_flags and write_contradictions unconditionally with
replace_existing=True. Empty list is a valid input that results in
"delete all, insert nothing". SP_WRITE_FLAGS / SP_WRITE_CONTRADICTIONS
both return OK for empty arrays (verified by code inspection).
"""
from pathlib import Path

p = Path("agents/orchestrator.py")
src = p.read_text(encoding="utf-8")

# Anchor on the entire _write_outputs function body, replace wholesale
# because there are several related changes (unconditional writes + fixed
# return indent + behaviour preserved). One coherent edit.
old_block = '''def _write_outputs(state: OrchestrationState) -> OrchestrationState:
    """Write timeline, flags, contradictions, briefing to Snowflake."""
    patient_id = state["patient_id"]
    log.info("Writing outputs for %s", patient_id)

    # Imports are local to defer dependency on the writer module.
    # These names match docs/DB_SCHEMA.md \u00a76.
    from database.snowflake_writer import (
        write_timeline,
        write_flags,
        write_contradictions,
        refresh_summary,
    )

    if state["timeline_events"]:
        try:
            write_timeline(patient_id, state["timeline_events"])
        except Exception as e:
            log.exception("write_timeline failed")
            state["errors"].append(f"write_timeline: {e}")

    if state["flags"]:
        try:
            # SP_WRITE_FLAGS expects source_document_id; v1.3 AI flags
            # emit cited_document_id. Map so both rule and AI flags persist.
            # TODO partner: update SP_WRITE_FLAGS to handle both field names.
            flags_to_write = []
            for f in state["flags"]:
                fcopy = dict(f)
                if "source_document_id" not in fcopy and "cited_document_id" in fcopy:
                    fcopy["source_document_id"] = fcopy["cited_document_id"]
                flags_to_write.append(fcopy)
                        # Hash flags for tamper-evidence. Context tracks the locked
            # production state of the v1.3 grounding instrument; if model,
            # prompt_version, or temperature change in prompts.py, update
            # this dict too so the hash reflects the real generation context.
            audit_context = {
                "model": "claude-sonnet-4-6",
                "prompt_version": "v1.3",
                "temperature": 0.7,
            }
            write_flags(patient_id, flags_to_write, context=audit_context, replace_existing=True)
        except Exception as e:
            log.exception("write_flags failed")
            state["errors"].append(f"write_flags: {e}")

    if state["contradictions"]:
        try:
            write_contradictions(patient_id, state["contradictions"], replace_existing=True)
        except Exception as e:
            log.exception("write_contradictions failed")
            state["errors"].append(f"write_contradictions: {e}")

    # Persist briefing directly to MART (bypasses SP_REFRESH_SUMMARY which
    # builds from CORE.condition / CORE.medication - tables not currently
    # populated). The briefing agent's dict is the source of truth.
    if state["briefing"]:
        try:
            from database.snowflake_writer import write_briefing
            write_briefing(patient_id, state["briefing"])
        except Exception as e:
            log.exception("write_briefing failed")
            state["errors"].append(f"write_briefing: {e}")

        return state'''

new_block = '''def _write_outputs(state: OrchestrationState) -> OrchestrationState:
    """Write timeline, flags, contradictions, briefing to Snowflake.

    Patient-level outputs (flags, contradictions) are written UNCONDITIONALLY
    with replace_existing=True - even when the new list is empty. That
    ensures stale rows from prior runs get deleted, which is essential
    after a document delete reduces the patient's content footprint.

    Timeline and briefing are append-or-merge oriented so they stay
    conditional on having content to write.
    """
    patient_id = state["patient_id"]
    log.info("Writing outputs for %s", patient_id)

    # Imports are local to defer dependency on the writer module.
    # These names match docs/DB_SCHEMA.md \u00a76.
    from database.snowflake_writer import (
        write_timeline,
        write_flags,
        write_contradictions,
        refresh_summary,
        write_briefing,
    )

    if state["timeline_events"]:
        try:
            write_timeline(patient_id, state["timeline_events"])
        except Exception as e:
            log.exception("write_timeline failed")
            state["errors"].append(f"write_timeline: {e}")

    # write_flags is called UNCONDITIONALLY with replace_existing=True so
    # that stale rows are cleared even when state["flags"] is empty (e.g.
    # after a delete reduces the doc set to zero meaningful flags).
    try:
        # SP_WRITE_FLAGS expects source_document_id; v1.3 AI flags emit
        # cited_document_id. Map so both rule and AI flags persist.
        flags_to_write = []
        for f in state["flags"]:
            fcopy = dict(f)
            if "source_document_id" not in fcopy and "cited_document_id" in fcopy:
                fcopy["source_document_id"] = fcopy["cited_document_id"]
            flags_to_write.append(fcopy)
        # Hash flags for tamper-evidence. Context tracks the locked
        # production state of the v1.3 grounding instrument; if model,
        # prompt_version, or temperature change in prompts.py, update
        # this dict too so the hash reflects the real generation context.
        audit_context = {
            "model": "claude-sonnet-4-6",
            "prompt_version": "v1.3",
            "temperature": 0.7,
        }
        write_flags(patient_id, flags_to_write, context=audit_context, replace_existing=True)
        log.info("write_flags: %d flags written (replace_existing=True)", len(flags_to_write))
    except Exception as e:
        log.exception("write_flags failed")
        state["errors"].append(f"write_flags: {e}")

    # write_contradictions UNCONDITIONALLY for same reason as flags.
    try:
        write_contradictions(patient_id, state["contradictions"], replace_existing=True)
        log.info("write_contradictions: %d written (replace_existing=True)",
                 len(state["contradictions"]))
    except Exception as e:
        log.exception("write_contradictions failed")
        state["errors"].append(f"write_contradictions: {e}")

    # Briefing is a MERGE-on-patient_id - idempotent upsert. Still
    # conditional because nothing to merge if briefing is None.
    if state["briefing"]:
        try:
            write_briefing(patient_id, state["briefing"])
        except Exception as e:
            log.exception("write_briefing failed")
            state["errors"].append(f"write_briefing: {e}")

    return state'''

if "write_flags is called UNCONDITIONALLY" in src:
    print("[SKIP] orchestrator already has unconditional writes")
elif old_block not in src:
    print("[FAIL] _write_outputs anchor not matching - check formatting")
    raise SystemExit(1)
else:
    src = src.replace(old_block, new_block)
    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] orchestrator._write_outputs: unconditional flag/contradiction writes + return state fixed")