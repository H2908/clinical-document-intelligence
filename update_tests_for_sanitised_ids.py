"""Update FHIR test assertions for sanitised IDs.

The builders now emit hyphenated FHIR IDs (pat-test-01) instead of the
internal underscored form (pat_test_01). Tests need to assert the new
contract. Six assertions to flip across two files.

Atomic anchored replacements. Internal data fixtures (PATIENT_ROW,
PATIENT, entity dicts) keep underscored patient_id - they represent
internal data. Only the assertions about FHIR-resource output flip.
"""
from pathlib import Path


# ============================================================================
# clinical_fhir/test_builders.py - 4 assertions to flip
# ============================================================================
p = Path("clinical_fhir/test_builders.py")
src = p.read_text(encoding="utf-8")

replacements = [
    # case_1_patient_happy_path: assert id is pat-test-01 (FHIR-sanitised),
    # not pat_test_01 (internal). The identifier.value can stay pat_test_01
    # since FHIR doesn't constrain identifier.value charset.
    (
        'and r["id"] == "pat_test_01"',
        'and r["id"] == "pat-test-01"',
    ),

    # case_3_condition_with_icd10: subject.reference uses FHIR-sanitised
    (
        'and r["subject"]["reference"] == "Patient/pat_test_01"\n        and r["code"]["text"] == "Chronic heart failure"',
        'and r["subject"]["reference"] == "Patient/pat-test-01"\n        and r["code"]["text"] == "Chronic heart failure"',
    ),

    # case_5_medication_with_bnf: subject.reference
    (
        'and r["subject"]["reference"] == "Patient/pat_test_01"\n        and r["status"] == "active"',
        'and r["subject"]["reference"] == "Patient/pat-test-01"\n        and r["status"] == "active"',
    ),

    # case_7_observation_with_unit: subject.reference
    (
        'and r["subject"]["reference"] == "Patient/pat_test_01"\n        and r["code"]["text"] == "HbA1c"',
        'and r["subject"]["reference"] == "Patient/pat-test-01"\n        and r["code"]["text"] == "HbA1c"',
    ),
]

for old, new in replacements:
    if old not in src:
        print(f"[FAIL] anchor not found: {old[:60]!r}...")
        raise SystemExit(1)
    src = src.replace(old, new)

p.write_text(src, encoding="utf-8", newline="\n")
print(f"OK clinical_fhir/test_builders.py: {len(replacements)} assertions updated")


# ============================================================================
# clinical_fhir/test_fhir_builder.py - 2 assertions to flip
# ============================================================================
p2 = Path("clinical_fhir/test_fhir_builder.py")
src2 = p2.read_text(encoding="utf-8")

replacements2 = [
    # case_3: dedup merges evidence refs. Refs are now hyphenated.
    (
        'return refs == {"DocumentReference/doc_01", "DocumentReference/doc_02"}, refs',
        'return refs == {"DocumentReference/doc-01", "DocumentReference/doc-02"}, refs',
    ),

    # case_4: medication dedup. informationSource is the first doc;
    # derivedFrom has the second.
    (
        '''return (
        info == "DocumentReference/doc_01"
        and derived_refs == {"DocumentReference/doc_02"}
    ), (info, derived_refs)''',
        '''return (
        info == "DocumentReference/doc-01"
        and derived_refs == {"DocumentReference/doc-02"}
    ), (info, derived_refs)''',
    ),
]

for old, new in replacements2:
    if old not in src2:
        print(f"[FAIL] anchor not found in test_fhir_builder.py")
        print(f"  looking for: {old[:80]!r}...")
        raise SystemExit(1)
    src2 = src2.replace(old, new)

p2.write_text(src2, encoding="utf-8", newline="\n")
print(f"OK clinical_fhir/test_fhir_builder.py: {len(replacements2)} assertions updated")

print("\n=== Summary ===")
print("6 assertions flipped from internal underscored IDs to FHIR-sanitised IDs.")
print("Internal data fixtures unchanged.")