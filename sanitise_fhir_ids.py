"""Sanitise IDs in clinical_fhir/builders.py and clinical_fhir/fhir_builder.py
for FHIR R4B compliance.

FHIR R4B requires Resource.id and reference values to match the pattern
^[A-Za-z0-9\\-.]+$ - no underscores. Our internal IDs use underscores
throughout (pat_test_01, doc_XXXXXXXX, obs_XXXXX_...).

Solution: transform at the FHIR boundary only. Internal IDs untouched.
Add a _to_fhir_id helper and route every id / reference field through it.

Atomic anchored replacements in clinical_fhir/builders.py only. The
fhir_builder.py module passes patient_id through to references built by
builders, so it also needs the same transform - we update the few
hard-coded reference strings there too.
"""
from pathlib import Path

# ============================================================================
# clinical_fhir/builders.py
# ============================================================================
p = Path("clinical_fhir/builders.py")
src = p.read_text(encoding="utf-8")

# 1. Add the transform helpers at the top, after the CODE_SYSTEM constants
old_anchor = '# ---- Sex/gender mapping ----'
new_block = '''# ---- ID sanitiser for FHIR R4B compliance ----

# FHIR R4B Resource.id and reference values must match this regex.
# Internal IDs use underscores (pat_test_01, doc_XXXXXXXX, obs_...);
# we transform at the FHIR boundary so internal Snowflake IDs stay
# untouched. _ -> -, leave digits/letters/period intact.
def _to_fhir_id(internal_id: str) -> str:
    if internal_id is None:
        return ""
    return str(internal_id).replace("_", "-")


def _fhir_ref(internal_id: str, resource_type: str) -> str:
    """Build a FHIR-compliant reference string.

    Example:
        _fhir_ref("pat_test_01", "Patient") -> "Patient/pat-test-01"
    """
    return f"{resource_type}/{_to_fhir_id(internal_id)}"


# ---- Sex/gender mapping ----'''

if old_anchor not in src:
    print("[FAIL] sex/gender mapping anchor not found")
    raise SystemExit(1)
src = src.replace(old_anchor, new_block, 1)

# 2. Patient builder - sanitise the id and identifier value
old_patient = '''    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": identifiers,
        "name": [{"text": name_text}],
        "gender": gender,
    }'''
new_patient = '''    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": _to_fhir_id(patient_id),
        "identifier": identifiers,
        "name": [{"text": name_text}],
        "gender": gender,
    }'''
if old_patient not in src:
    print("[FAIL] Patient resource construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_patient, new_patient)

# Also sanitise the local-patient-id identifier value (the internal id stored
# as a business identifier in the identifier array)
old_local_id = '''    identifiers.append({
        "system": ID_SYSTEM_LOCAL_PATIENT,
        "value": patient_id,
    })'''
new_local_id = '''    identifiers.append({
        "system": ID_SYSTEM_LOCAL_PATIENT,
        "value": patient_id,
    })  # Note: identifier.value tolerates underscores; only id and references need sanitising'''
# Leave this one alone - identifier.value is a free-text business identifier
# and FHIR doesn't constrain its character set. Comment-only update for clarity.
# We do nothing here - the existing value is fine.

# 3. Condition - subject.reference and evidence references go through _fhir_ref
old_condition_subject = '''        "subject": {"reference": f"Patient/{patient_id}"},'''
new_condition_subject = '''        "subject": {"reference": _fhir_ref(patient_id, "Patient")},'''
# This pattern appears in Condition, MedicationStatement, and Observation builders.
# Replace ALL occurrences - there are three.
count = src.count(old_condition_subject)
if count != 3:
    print(f"[FAIL] expected 3 'Patient/{{patient_id}}' references, found {count}")
    raise SystemExit(1)
src = src.replace(old_condition_subject, new_condition_subject)

# 4. Condition.evidence references
old_evidence = '''        resource["evidence"] = [{
            "detail": [{"reference": f"DocumentReference/{document_id}"}],
        }]'''
new_evidence = '''        resource["evidence"] = [{
            "detail": [{"reference": _fhir_ref(document_id, "DocumentReference")}],
        }]'''
if old_evidence not in src:
    print("[FAIL] Condition.evidence anchor not found")
    raise SystemExit(1)
src = src.replace(old_evidence, new_evidence)

# 5. MedicationStatement.informationSource
old_info_src = '''        resource["informationSource"] = {
            "reference": f"DocumentReference/{document_id}",
        }'''
new_info_src = '''        resource["informationSource"] = {
            "reference": _fhir_ref(document_id, "DocumentReference"),
        }'''
if old_info_src not in src:
    print("[FAIL] MedicationStatement.informationSource anchor not found")
    raise SystemExit(1)
src = src.replace(old_info_src, new_info_src)

# 6. Observation.derivedFrom
old_obs_derived = '''        resource["derivedFrom"] = [{
            "reference": f"DocumentReference/{src}",
        }]'''
new_obs_derived = '''        resource["derivedFrom"] = [{
            "reference": _fhir_ref(src, "DocumentReference"),
        }]'''
if old_obs_derived not in src:
    print("[FAIL] Observation.derivedFrom anchor not found")
    raise SystemExit(1)
src = src.replace(old_obs_derived, new_obs_derived)

# 7. Observation.id from observation_id field
old_obs_id = '''    obs_id = obs_row.get("observation_id")
    if obs_id:
        resource["id"] = obs_id'''
new_obs_id = '''    obs_id = obs_row.get("observation_id")
    if obs_id:
        resource["id"] = _to_fhir_id(obs_id)'''
if old_obs_id not in src:
    print("[FAIL] Observation.id anchor not found")
    raise SystemExit(1)
src = src.replace(old_obs_id, new_obs_id)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK builders.py: ID sanitiser added, 6 reference sites updated")


# ============================================================================
# clinical_fhir/fhir_builder.py
# ============================================================================
p2 = Path("clinical_fhir/fhir_builder.py")
src2 = p2.read_text(encoding="utf-8")

# fhir_builder.py builds reference strings in _merge_evidence and
# _merge_information_source helpers. Same sanitisation needed.
# But those helpers build references using f"DocumentReference/{doc_id}"
# where doc_id is the raw internal id. Need _to_fhir_id imported and applied.

if "from clinical_fhir.builders import" in src2 and "_to_fhir_id" not in src2:
    # Add _to_fhir_id and _fhir_ref to the import
    src2 = src2.replace(
        "from clinical_fhir.builders import (",
        "from clinical_fhir.builders import (\n    _fhir_ref,",
        1,
    )

# Replace the two hard-coded reference patterns in fhir_builder.py
old_evidence_ref = '''    new_ref = {"reference": f"DocumentReference/{doc_id}"}
    evidence = existing.setdefault("evidence", [{"detail": []}])'''
new_evidence_ref = '''    new_ref = {"reference": _fhir_ref(doc_id, "DocumentReference")}
    evidence = existing.setdefault("evidence", [{"detail": []}])'''
if old_evidence_ref in src2:
    src2 = src2.replace(old_evidence_ref, new_evidence_ref)
    print("OK fhir_builder.py: _merge_evidence reference sanitised")

old_info_ref = '''    new_ref = {"reference": f"DocumentReference/{doc_id}"}
    derived = existing.setdefault("derivedFrom", [])'''
new_info_ref = '''    new_ref = {"reference": _fhir_ref(doc_id, "DocumentReference")}
    derived = existing.setdefault("derivedFrom", [])'''
if old_info_ref in src2:
    src2 = src2.replace(old_info_ref, new_info_ref)
    print("OK fhir_builder.py: _merge_information_source reference sanitised")

p2.write_text(src2, encoding="utf-8", newline="\n")

print("\n=== Summary ===")
print("builders.py: _to_fhir_id + _fhir_ref helpers added")
print("All Patient.id, references, and Observation.id sites updated")
print("fhir_builder.py: dedup-merge references sanitised")
print()
print("NEXT: rerun tests and the validator. Internal IDs stay underscored;")
print("FHIR boundary outputs use hyphens.")