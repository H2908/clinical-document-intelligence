"""Fix the scope leak: process_document's local override of document_date
isn't propagating to process_from_s3 where insert_core_document is called.

Two surgical edits:

  1. In process_document, after the override, stash the resolved date
     in payload["document"]["document_date_resolved"] as an ISO string.
     (We already stash document_date_extracted=True/False.)

  2. In process_from_s3, before calling insert_core_document, read the
     resolved date back from the result payload and pass that instead
     of process_from_s3's own document_date parameter.

Effect: extracted date now flows all the way to CORE.document.
RAW.raw_documents still has the user-supplied date (audit preserved).
"""
from pathlib import Path

p = Path("worker/document_processor.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# Edit 1: stash resolved date in payload
# ============================================================================
old_override = '''            document_date = extracted_date
            payload["document"]["document_date_extracted"] = True
        else:
            payload["document"]["document_date_extracted"] = False'''

new_override = '''            document_date = extracted_date
            payload["document"]["document_date_extracted"] = True
        else:
            payload["document"]["document_date_extracted"] = False
        # Always stash the resolved date (extracted or original) so
        # process_from_s3 can use it when writing to CORE.document.
        payload["document"]["document_date_resolved"] = (
            document_date.isoformat() if hasattr(document_date, "isoformat") else str(document_date)
        )'''

if "document_date_resolved" in src:
    print("[SKIP] payload already carries document_date_resolved")
elif old_override not in src:
    print("[FAIL] override-anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_override, new_override, 1)
    print("[OK] process_document now stashes resolved date in payload")


# ============================================================================
# Edit 2: read resolved date in process_from_s3 before insert_core_document
# ============================================================================
old_insert = '''        if payload["status"] == "processed":
            from database.snowflake_writer import insert_core_document
            insert_core_document(
                document_id=document_id,
                patient_id=patient_id,
                file_name=Path(s3_key).name,
                doc_type=doc_type,
                s3_key=s3_key,
                document_date=document_date,
                source=None,
                extracted_text=payload.get("document", {}).get("extracted_text"),
                status="processed",
            )'''

new_insert = '''        if payload["status"] == "processed":
            from database.snowflake_writer import insert_core_document
            from datetime import date as _date_cls
            # Prefer the date resolved by process_document (which may have
            # extracted it from the PDF text) over the user-supplied one.
            resolved_iso = payload.get("document", {}).get("document_date_resolved")
            try:
                resolved_date = (
                    _date_cls.fromisoformat(resolved_iso) if resolved_iso else document_date
                )
            except (TypeError, ValueError):
                resolved_date = document_date
            log.info(
                "CORE.document write: document_id=%s document_date=%s (user supplied %s)",
                document_id, resolved_date, document_date,
            )
            insert_core_document(
                document_id=document_id,
                patient_id=patient_id,
                file_name=Path(s3_key).name,
                doc_type=doc_type,
                s3_key=s3_key,
                document_date=resolved_date,
                source=None,
                extracted_text=payload.get("document", {}).get("extracted_text"),
                status="processed",
            )'''

if "resolved_date = " in src:
    print("[SKIP] process_from_s3 already uses resolved_date")
elif old_insert not in src:
    print("[FAIL] insert_core_document anchor not matching")
    raise SystemExit(1)
else:
    src = src.replace(old_insert, new_insert, 1)
    print("[OK] process_from_s3 now writes resolved date to CORE.document")


p.write_text(src, encoding="utf-8", newline="\n")
print()
print("=== Summary ===")
print("process_document stashes resolved date in payload['document']")
print("process_from_s3 reads it back and uses it for the CORE write")
print()
print("Next: re-run cleanup, watch for the new log lines:")
print("  - 'document_date extracted from text: ...'")
print("  - 'CORE.document write: document_id=... document_date=2024-XX-XX'")