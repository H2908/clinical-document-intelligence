"""Fix Bug 1 (NER substring leak) and Bug 2 (patient block placeholder).

Bug 1: nlp/medical_ner._looks_like_condition does substring matches
against CONDITION_TERMS / SYMPTOM_TERMS / CONDITION_ROOTS. Short terms
like 'uti' (in CONDITION_TERMS) and 'pe' (in CONDITION_TERMS) leak as
substrings into common words ('routine' contains 'uti'; 'specialist'
contains 'pe'). Fix: regex word-boundary matching for all three lists.

Bug 2: database/snowflake_writer.write_briefing has a hardcoded
placeholder fallback when briefing dict doesn't carry a 'patient' key
('Test Patient', 1980-01-01, 000 000 0001, Other). The briefing agent
never produces a 'patient' key, so the fallback always fires. Every
patient's MART row stores wrong demographics. Fix: read from
CORE.patient when no 'patient' block is present.

Two anchored edits across two files.
"""
from pathlib import Path
import re

# ============================================================================
# 1. nlp/medical_ner.py - word-boundary regex in _looks_like_condition
# ============================================================================
p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

old_func = '''def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Accepts if ANY of:
      - Direct match on a known condition term (CONDITION_TERMS)
      - Contains a known condition term as a substring
      - Contains a known condition root suffix (CONDITION_ROOTS)
      - Direct match on a known symptom term (SYMPTOM_TERMS)
      - Contains a known symptom term as a substring

    Symptoms are absorbed as "Diagnosis" because the 4-type entity schema
    does not model them separately. Signal preserved at the cost of
    schematic looseness.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Contains a known condition term as a substring
    for term in CONDITION_TERMS:
        if term in lower:
            return True
    # Direct match on a symptom term
    if lower in SYMPTOM_TERMS:
        return True
    # Contains a symptom term as a substring
    for term in SYMPTOM_TERMS:
        if term in lower:
            return True
    # Contains a known condition root suffix
    for root in CONDITION_ROOTS:
        if root in lower:
            return True
    return False'''

new_func = '''def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Accepts if ANY of:
      - Direct match on a known condition term (CONDITION_TERMS)
      - Contains a known condition term as a WORD-BOUNDARY match
      - Contains a known condition root suffix as a WORD-BOUNDARY match
      - Direct match on a known symptom term (SYMPTOM_TERMS)
      - Contains a known symptom term as a WORD-BOUNDARY match

    Word boundaries (regex \\\\b) prevent short medical abbreviations from
    leaking into unrelated common words. Before this fix, 'uti' (urinary
    tract infection) leaked into 'routine' and 'pe' (pulmonary embolism)
    leaked into 'specialist', producing false-positive Diagnosis entities.

    Symptoms are absorbed as "Diagnosis" because the 4-type entity schema
    does not model them separately. Signal preserved at the cost of
    schematic looseness.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Word-boundary match on any condition term
    for term in CONDITION_TERMS:
        if re.search(rf"\\b{re.escape(term)}\\b", lower):
            return True
    # Direct match on a symptom term
    if lower in SYMPTOM_TERMS:
        return True
    # Word-boundary match on any symptom term
    for term in SYMPTOM_TERMS:
        if re.search(rf"\\b{re.escape(term)}\\b", lower):
            return True
    # Word-boundary match on any condition root suffix.
    # Roots like 'itis', 'osis', 'pathy' are intentional suffixes - they
    # match at word END not as separate words. We use a different pattern:
    # the root must appear at the end of any word in the span.
    for root in CONDITION_ROOTS:
        if re.search(rf"{re.escape(root)}\\b", lower):
            return True
    return False'''

if "Word-boundary match on any condition term" in src:
    print("[SKIP] _looks_like_condition already uses word boundaries")
elif old_func not in src:
    print("[FAIL] _looks_like_condition anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_func, new_func)
    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] medical_ner: substring checks replaced with word-boundary regex")


# ============================================================================
# 2. database/snowflake_writer.py - real CORE.patient read in write_briefing
# ============================================================================
p2 = Path("database/snowflake_writer.py")
src2 = p2.read_text(encoding="utf-8")

old_block = '''      "patient": briefing.get("patient", {
          "id":         patient_id,
          "name":       "Test Patient",
          "dob":        "1980-01-01",
          "nhs_number": "000 000 0001",
          "sex":        "Other",'''

# Look for the same block but with leading spaces variability
import re as _re
pattern = _re.compile(
    r'("patient":\s*briefing\.get\("patient",\s*\{)\s*'
    r'"id":\s*[^,]*,\s*'
    r'"name":\s*"Test Patient",\s*'
    r'"dob":\s*"1980-01-01",\s*'
    r'"nhs_number":\s*"000 000 0001",\s*'
    r'"sex":\s*"Other",?\s*\}',
    _re.DOTALL,
)
match = pattern.search(src2)

if "_fetch_patient_block" in src2:
    print("[SKIP] write_briefing already has real patient read")
elif match is None:
    print("[FAIL] patient placeholder anchor not found")
    print("       Showing first 400 chars of search target:")
    idx = src2.find('"patient": briefing.get')
    if idx >= 0:
        print(f"       {src2[idx:idx+400]!r}")
    raise SystemExit(1)
else:
    # Replace the placeholder block with a call to a helper that reads CORE.patient
    new_get = '"patient": briefing.get("patient") or _fetch_patient_block(patient_id)'
    src2 = src2[:match.start()] + new_get + src2[match.end():]

    # Add the helper function above write_briefing
    helper = '''def _fetch_patient_block(patient_id: str) -> dict:
    """Read patient demographics from CORE.patient. Returns the shape
    the briefing JSON expects. Falls back to id-only if the row is
    missing (shouldn't happen but defensive)."""
    try:
        conn = _get_connection()
    except Exception:
        return {"id": patient_id, "name": "", "dob": None, "nhs_number": "", "sex": ""}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, dob, nhs_number, sex FROM clinical_db.core.patient "
            "WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"id": patient_id, "name": "", "dob": None, "nhs_number": "", "sex": ""}
        name, dob, nhs, sex = row
        return {
            "id": patient_id,
            "name": name or "",
            "dob": str(dob) if dob else None,
            "nhs_number": nhs or "",
            "sex": sex or "",
        }
    finally:
        conn.close()


'''
    # Insert helper just before def write_briefing
    anchor = "def write_briefing(patient_id: str, briefing: dict) -> None:"
    if anchor not in src2:
        print("[FAIL] write_briefing anchor not found for helper insert")
        raise SystemExit(1)
    src2 = src2.replace(anchor, helper + anchor, 1)
    p2.write_text(src2, encoding="utf-8", newline="\n")
    print("[OK] snowflake_writer: write_briefing now reads real patient demographics from CORE")

print()
print("=== Summary ===")
print("Bug 1: word-boundary regex prevents uti/pe substring leaks into routine/specialist")
print("Bug 2: write_briefing reads CORE.patient instead of hardcoded Test Patient placeholder")
print()
print("Next:")
print("  1. Re-process pat_fa9fb06f's 3 docs to refresh NER + MART")
print("  2. Refresh browser - briefing shows Margaret Thompson, no Routine/nurse specialist noise")