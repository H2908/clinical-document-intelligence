"""Tests for fhir.fhir_builder.build_patient_bundle.

Pure-injection tests: data is passed via the optional patient_row /
entities / observations parameters so the tests don't hit Snowflake.

Five cases:
  1. Happy path: full input -> well-formed Bundle with one resource of
     each type
  2. Empty entities + empty observations -> Bundle with only Patient
  3. Condition dedup: two Diagnosis entities for the same condition in
     different documents -> one Condition resource with merged evidence
  4. Medication dedup: two Drug entities for the same drug -> one
     MedicationStatement with merged derivedFrom
  5. Bundle structure: type == 'collection', entries are wrapped in
     {"resource": ...}, timestamp is set, resourceType is Bundle

Run: python -m fhir.test_fhir_builder
Expected: 5/5 pass.
"""
from fhir.fhir_builder import build_patient_bundle


PATIENT = {
    "patient_id": "pat_test_01",
    "name": "Margaret Thompson",
    "dob": "1954-08-15",
    "nhs_number": "9991000001",
    "sex": "F",
}

DX_HEART_FAILURE_DOC1 = {
    "entity_type": "Diagnosis",
    "text": "Chronic heart failure",
    "icd10_code": "I50.22",
    "document_id": "doc_01",
    "document_date": "2024-01-12",
}

DX_HEART_FAILURE_DOC2 = {
    "entity_type": "Diagnosis",
    "text": "chronic heart failure",   # case differs - same canonical
    "icd10_code": "I50.22",
    "document_id": "doc_02",
    "document_date": "2024-02-28",
}

DX_DIABETES = {
    "entity_type": "Diagnosis",
    "text": "Type 2 diabetes mellitus",
    "icd10_code": "E11.9",
    "document_id": "doc_01",
    "document_date": "2024-01-12",
}

DRUG_RAMIPRIL_DOC1 = {
    "entity_type": "Drug",
    "text": "Ramipril 5 mg",
    "bnf_code": "0205051F0",
    "normalised_value": "ramipril",
    "document_id": "doc_01",
    "document_date": "2024-01-12",
}

DRUG_RAMIPRIL_DOC2 = {
    "entity_type": "Drug",
    "text": "ramipril",
    "bnf_code": "0205051F0",
    "normalised_value": "ramipril",
    "document_id": "doc_02",
    "document_date": "2024-02-28",
}

DRUG_METFORMIN = {
    "entity_type": "Drug",
    "text": "Metformin",
    "bnf_code": "0601022B0",
    "normalised_value": "metformin",
    "document_id": "doc_01",
    "document_date": "2024-01-12",
}

OBS_HBA1C = {
    "observation_id": "obs_001",
    "test": "HbA1c",
    "value": "8.4",
    "unit": "%",
    "observation_date": "2023-05-22",
    "source_document_id": "doc_03",
}


def case_1_happy_path_full_bundle():
    """Bundle has Patient + 2 Conditions + 2 Medications + 1 Observation."""
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[DX_HEART_FAILURE_DOC1, DX_DIABETES, DRUG_RAMIPRIL_DOC1, DRUG_METFORMIN],
        observations=[OBS_HBA1C],
    )
    by_type: dict[str, int] = {}
    for entry in bundle["entry"]:
        rt = entry["resource"]["resourceType"]
        by_type[rt] = by_type.get(rt, 0) + 1
    return (
        bundle["resourceType"] == "Bundle"
        and bundle["type"] == "collection"
        and by_type.get("Patient") == 1
        and by_type.get("Condition") == 2
        and by_type.get("MedicationStatement") == 2
        and by_type.get("Observation") == 1
    ), by_type


def case_2_empty_data_yields_patient_only():
    """Patient with no entities, no observations -> Bundle with only Patient."""
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[],
        observations=[],
    )
    return (
        len(bundle["entry"]) == 1
        and bundle["entry"][0]["resource"]["resourceType"] == "Patient"
    ), bundle["entry"]


def case_3_condition_dedup_merges_evidence():
    """Same condition in two docs -> one Condition with both docs in evidence."""
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[DX_HEART_FAILURE_DOC1, DX_HEART_FAILURE_DOC2],
        observations=[],
    )
    conditions = [e["resource"] for e in bundle["entry"]
                  if e["resource"]["resourceType"] == "Condition"]
    if len(conditions) != 1:
        return False, f"expected 1 condition, got {len(conditions)}"
    cond = conditions[0]
    evidence_details = cond.get("evidence", [{}])[0].get("detail", [])
    refs = {d.get("reference") for d in evidence_details}
    return refs == {"DocumentReference/doc_01", "DocumentReference/doc_02"}, refs


def case_4_medication_dedup_merges_derivedFrom():
    """Same drug in two docs -> one MedicationStatement, second doc in derivedFrom."""
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[DRUG_RAMIPRIL_DOC1, DRUG_RAMIPRIL_DOC2],
        observations=[],
    )
    meds = [e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "MedicationStatement"]
    if len(meds) != 1:
        return False, f"expected 1 medication, got {len(meds)}"
    med = meds[0]
    info = med.get("informationSource", {}).get("reference")
    derived_refs = {d.get("reference") for d in med.get("derivedFrom", [])}
    return (
        info == "DocumentReference/doc_01"
        and derived_refs == {"DocumentReference/doc_02"}
    ), (info, derived_refs)


def case_5_bundle_shape_is_r4_collection():
    """Bundle has resourceType, type=collection, timestamp, entries wrapped."""
    bundle = build_patient_bundle(
        "pat_test_01",
        patient_row=PATIENT,
        entities=[DX_DIABETES],
        observations=[],
    )
    return (
        bundle["resourceType"] == "Bundle"
        and bundle["type"] == "collection"
        and "timestamp" in bundle
        and "entry" in bundle
        and all("resource" in e for e in bundle["entry"])
        and bundle["entry"][0]["resource"]["resourceType"] == "Patient"
    ), {
        "keys": sorted(bundle.keys()),
        "first_entry_keys": sorted(bundle["entry"][0].keys()),
    }


CASES = [
    ("01_happy_path_full_bundle", case_1_happy_path_full_bundle),
    ("02_empty_data_patient_only", case_2_empty_data_yields_patient_only),
    ("03_condition_dedup_merges_evidence", case_3_condition_dedup_merges_evidence),
    ("04_medication_dedup_merges_derivedFrom", case_4_medication_dedup_merges_derivedFrom),
    ("05_bundle_shape_is_r4_collection", case_5_bundle_shape_is_r4_collection),
]


def main() -> int:
    print("Running 5-case FHIR bundle assembly test set\n")
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
    print(f"\n{passes}/{len(CASES)} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())