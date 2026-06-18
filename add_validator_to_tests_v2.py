"""V2 of validator-to-tests integration. Correct anchor this time.

Both test_builders.py and test_fhir_builder.py have the SAME main()
shape (try/except wrapper around fn()). V1 anchor missed it.

Adds:
  - validator import + _validate helper (per-resource)
  - validator gate inside main() runner that gates ok on R4B validation

For test_fhir_builder.py: end-of-suite Bundle validation gate that
build_patient_bundle output passes the validator.
"""
from pathlib import Path

# Skip-protection: if already added, no-op
def skip_if_done(src, marker):
    return marker in src


# ============================================================================
# clinical_fhir/test_builders.py
# ============================================================================
p = Path("clinical_fhir/test_builders.py")
src = p.read_text(encoding="utf-8")

if skip_if_done(src, "from clinical_fhir.validator import validate_resource"):
    print("[SKIP] test_builders.py already has validator import")
else:
    old_imports = '''from clinical_fhir.builders import (
    build_patient,
    build_condition,
    build_medication_statement,
    build_observation,
)'''
    new_imports = '''from clinical_fhir.builders import (
    build_patient,
    build_condition,
    build_medication_statement,
    build_observation,
)
from clinical_fhir.validator import validate_resource


def _validate(resource: dict) -> tuple[bool, str]:
    """R4B validator gate. Returns (True, '') if valid, else (False, errors)."""
    err = validate_resource(resource)
    if err is None:
        return True, ""
    return False, f"R4B validator rejected: {err.get('errors', [])}"'''

    if old_imports not in src:
        print("[FAIL] builder import anchor not found")
        raise SystemExit(1)
    src = src.replace(old_imports, new_imports)
    print("OK test_builders.py: validator import + helper added")

# Replace main() with validator-gated version. Anchor matches the REAL shape
# (try/except wrapper that the file actually has).
old_main = '''def main() -> int:
    print("Running 8-case FHIR builder test set\\n")
    passes = 0
    fails = []
    for case_id, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as e:
            print(f"  [ERROR] {case_id}: {type(e).__name__}: {e}")
            fails.append(case_id)
            continue
        if ok:
            print(f"  [OK]   {case_id}")
            passes += 1
        else:
            print(f"  [FAIL] {case_id}")
            print(f"         got: {detail}")
            fails.append(case_id)
    print(f"\\n{passes}/{len(CASES)} passed")
    if fails:
        print(f"FAILED: {fails}")
        return 1
    return 0'''

new_main = '''def main() -> int:
    print("Running 8-case FHIR builder test set + R4B validator gate\\n")
    passes = 0
    fails = []
    for case_id, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as e:
            print(f"  [ERROR] {case_id}: {type(e).__name__}: {e}")
            fails.append(case_id)
            continue
        if not ok:
            print(f"  [FAIL] {case_id}")
            print(f"         got: {detail}")
            fails.append(case_id)
            continue
        # Validator gate: detail carries the built resource for every case
        if isinstance(detail, dict) and "resourceType" in detail:
            v_ok, v_msg = _validate(detail)
            if not v_ok:
                print(f"  [FAIL] {case_id} - R4B validation")
                print(f"         {v_msg}")
                fails.append(case_id)
                continue
        # Case 02 returns a tuple of genders, not a resource - skip validator
        # for it (the underlying Patient resources built inside the case
        # already validate elsewhere).
        print(f"  [OK]   {case_id}")
        passes += 1
    print(f"\\n{passes}/{len(CASES)} passed")
    if fails:
        print(f"FAILED: {fails}")
        return 1
    return 0'''

if old_main not in src:
    print("[FAIL] test_builders main() anchor still not matching - inspect file")
    raise SystemExit(1)
src = src.replace(old_main, new_main)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK test_builders.py: main() updated with validator gate")


# ============================================================================
# clinical_fhir/test_fhir_builder.py
# ============================================================================
p2 = Path("clinical_fhir/test_fhir_builder.py")
src2 = p2.read_text(encoding="utf-8")

if skip_if_done(src2, "from clinical_fhir.validator import validate_bundle"):
    print("[SKIP] test_fhir_builder.py already has validator import")
else:
    old_imports2 = 'from clinical_fhir.fhir_builder import build_patient_bundle'
    new_imports2 = '''from clinical_fhir.fhir_builder import build_patient_bundle
from clinical_fhir.validator import validate_bundle


def _validate_bundle(bundle: dict) -> tuple[bool, str]:
    """R4B validator gate for bundles."""
    report = validate_bundle(bundle)
    if report["bundle_valid"] and report["summary"]["invalid_count"] == 0:
        return True, ""
    bad = [e for e in report["entry_results"] if not e["valid"]]
    return False, (
        f"bundle_valid={report['bundle_valid']}, "
        f"invalid_entries={report['summary']['invalid_count']}, "
        f"first_failures={bad[:3]}"
    )'''
    if old_imports2 not in src2:
        print("[FAIL] fhir_builder import anchor not found")
        raise SystemExit(1)
    src2 = src2.replace(old_imports2, new_imports2)
    print("OK test_fhir_builder.py: validator import + helper added")

# Add end-of-suite Bundle validation by extending main()
old_main2 = '''def main() -> int:
    print("Running 5-case FHIR bundle assembly test set\\n")
    passes = 0
    fails = []
    for case_id, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as e:
            print(f"  [ERROR] {case_id}: {type(e).__name__}: {e}")
            fails.append(case_id)
            continue
        if ok:
            print(f"  [OK]   {case_id}")
            passes += 1
        else:
            print(f"  [FAIL] {case_id}")
            print(f"         got: {detail}")
            fails.append(case_id)
    print(f"\\n{passes}/{len(CASES)} passed")
    return 0 if not fails else 1'''

new_main2 = '''def main() -> int:
    print("Running 5-case FHIR bundle assembly test set + R4B validator gate\\n")
    passes = 0
    fails = []
    for case_id, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as e:
            print(f"  [ERROR] {case_id}: {type(e).__name__}: {e}")
            fails.append(case_id)
            continue
        if ok:
            print(f"  [OK]   {case_id}")
            passes += 1
        else:
            print(f"  [FAIL] {case_id}")
            print(f"         got: {detail}")
            fails.append(case_id)

    # End-of-suite Bundle validation gate
    print()
    print("=== End-of-suite R4B Bundle validation gate ===")
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[DX_HEART_FAILURE_DOC1, DX_DIABETES, DRUG_RAMIPRIL_DOC1, DRUG_METFORMIN],
        observations=[OBS_HBA1C],
    )
    v_ok, v_msg = _validate_bundle(bundle)
    if v_ok:
        print(f"  [OK]   Bundle assembled from injected fixtures validates R4B")
    else:
        print(f"  [FAIL] R4B Bundle validation")
        print(f"         {v_msg}")
        fails.append("end_of_suite_r4b_bundle_validation")

    print(f"\\n{passes}/{len(CASES)} cases passed; "
          f"R4B gate: {'OK' if 'end_of_suite_r4b_bundle_validation' not in fails else 'FAILED'}")
    return 0 if not fails else 1'''

if old_main2 not in src2:
    print("[FAIL] test_fhir_builder main() anchor not matching")
    raise SystemExit(1)
src2 = src2.replace(old_main2, new_main2)
p2.write_text(src2, encoding="utf-8", newline="\n")
print("OK test_fhir_builder.py: main() updated with end-of-suite validator gate")

print("\n=== Summary ===")
print("Both test files now have R4B validator integration.")
print("Run: python -m clinical_fhir.test_builders")
print("Run: python -m clinical_fhir.test_fhir_builder")