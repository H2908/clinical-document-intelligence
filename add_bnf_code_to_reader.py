"""Add bnf_code to read_entities_for_patient SELECT.

CORE.entity has bnf_code populated (verified: 27/27 Drug entities for
pat_test_01 carry codes). But snowflake_reader's SELECT predates that
column. FHIR bundle builder reads via this function and gets None for
bnf_code on every entity. Bundle Medications show bnf=- as a result.

One-line addition to the SELECT.
"""
from pathlib import Path

p = Path("database/snowflake_reader.py")
src = p.read_text(encoding="utf-8")

if "e.bnf_code" in src:
    print("[SKIP] bnf_code already in SELECT")
    raise SystemExit(0)

old_select = '''            SELECT
                e.entity_type,
                e.text,
                e.start_offset,
                e.end_offset,
                e.negated,
                e.icd10_code,
                e.normalised_value,
                e.document_id,
                d.document_date,
                d.doc_type
            FROM clinical_db.core.entity e'''

new_select = '''            SELECT
                e.entity_type,
                e.text,
                e.start_offset,
                e.end_offset,
                e.negated,
                e.icd10_code,
                e.bnf_code,
                e.normalised_value,
                e.document_id,
                d.document_date,
                d.doc_type
            FROM clinical_db.core.entity e'''

if old_select not in src:
    print("[FAIL] SELECT anchor not found - check formatting")
    raise SystemExit(1)
src = src.replace(old_select, new_select)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK bnf_code added to read_entities_for_patient SELECT")