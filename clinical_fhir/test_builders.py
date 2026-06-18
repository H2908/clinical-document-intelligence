"""Tests for fhir.builders.

Eight cases, two per builder. Happy path verifies required FHIR fields
present and shaped correctly. Edge cases verify graceful handling of
missing optional fields (no ICD-10, no BNF, no observation unit).

Tests assert structure, not full FHIR validity. Block 2 adds fhir.resources
parser validation on top of these tests.

Run: python -m fhir.test_builders
Expected: 8/8 pass.
"""
from clinical_fhir.builders import (
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
    return False, f"R4B validator rejected: {err.get('errors', [])}"


# ---- Test fixtures ----

PATIENT_ROW = {
    "patient_id": "pat_test_01",
    "name": "Margaret Thompson",
    "dob": "1954-08-15",
    "nhs_number": "9991000001",
    "sex": "F",
}

CONDITION_ENTITY = {
    "entity_type": "Diagnosis",
    "text": "Chronic heart failure",
    "icd10_code": "I50.22",
    "document_id": "doc_3a3edf90",
    "document_date": "2024-01-12",
    "normalised_value": "explicit",
}

CONDITION_ENTITY_NO_CODE = {
    "entity_type": "Diagnosis",
    "text": "exertional dyspnoea",
    "icd10_code": None,
    "document_id": "doc_3a3edf90",
    "document_date": "2024-01-12",
    "normalised_value": None,
}

DRUG_ENTITY = {
    "entity_type": "Drug",
    "text": "Ramipril 5 mg",
    "bnf_code": "0205051F0",
    "document_id": "doc_3a3edf90",
    "document_date": "2024-01-12",
    "normalised_value": "ramipril",
}

DRUG_ENTITY_NO_BNF = {
    "entity_type": "Drug",
    "text": "unknown_drug 10 mg",
    "bnf_code": None,
    "document_id": "doc_3a3edf90",
    "document_date": "2024-01-12",
    "normalised_value": "unknown_drug",
}

OBSERVATION_ROW = {
    "observation_id": "obs_001",
    "test": "HbA1c",
    "value": "8.4",
    "unit": "%",
    "observation_date": "2023-05-22",
    "source_document_id": "doc_375bbc8a",
}

OBSERVATION_ROW_NO_UNIT = {
    "observation_id": "obs_002",
    "test": "Penicillin reaction",
    "value": "rash",
    "unit": None,
    "observation_date": "2018-03-10",
    "source_document_id": "doc_375bbc8a",
}


# ---- Patient builder ----

def case_1_patient_happy_path():
    """Patient with all fields produces a valid R4 Patient resource."""
    r = build_patient(PATIENT_ROW)
    return (
        r is not None
        and r["resourceType"] == "Patient"
        and r["id"] == "pat-test-01"
        and any(i.get("value") == "9991000001" for i in r.get("identifier", []))
        and any(i.get("value") == "pat_test_01" for i in r.get("identifier", []))
        and r["gender"] == "female"
        and r["birthDate"] == "1954-08-15"
        and r["name"][0]["text"] == "Margaret Thompson"
    ), r


def case_2_patient_male_sex_mapping():
    """Sex 'M' maps to FHIR gender 'male', 'Other' maps to 'other'."""
    p_male = build_patient({**PATIENT_ROW, "sex": "M"})
    p_other = build_patient({**PATIENT_ROW, "sex": "Other"})
    return (
        p_male["gender"] == "male"
        and p_other["gender"] == "other"
    ), (p_male["gender"], p_other["gender"])


# ---- Condition builder ----

def case_3_condition_with_icd10():
    """Diagnosis with ICD-10 code produces Condition with code.coding."""
    r = build_condition(CONDITION_ENTITY, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "Condition"
        and r["subject"]["reference"] == "Patient/pat-test-01"
        and r["code"]["text"] == "Chronic heart failure"
        and any(
            c.get("code") == "I50.22"
            and c.get("system") == "http://hl7.org/fhir/sid/icd-10"
            for c in r["code"].get("coding", [])
        )
    ), r


def case_4_condition_no_icd10_code():
    """Diagnosis without ICD-10 code omits the coding array (still valid)."""
    r = build_condition(CONDITION_ENTITY_NO_CODE, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "Condition"
        and r["code"]["text"] == "exertional dyspnoea"
        and ("coding" not in r["code"] or r["code"]["coding"] == [])
    ), r


# ---- MedicationStatement builder ----

def case_5_medication_with_bnf():
    """Drug with BNF code produces MedicationStatement with coded medication."""
    r = build_medication_statement(DRUG_ENTITY, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "MedicationStatement"
        and r["subject"]["reference"] == "Patient/pat-test-01"
        and r["status"] == "active"
        and r["medicationCodeableConcept"]["text"] in ("Ramipril 5 mg", "ramipril")
        and any(
            c.get("code") == "0205051F0"
            and "bnf" in c.get("system", "").lower()
            for c in r["medicationCodeableConcept"].get("coding", [])
        )
    ), r


def case_6_medication_no_bnf():
    """Drug without BNF code omits coding, keeps text."""
    r = build_medication_statement(DRUG_ENTITY_NO_BNF, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "MedicationStatement"
        and r["medicationCodeableConcept"]["text"]
        and ("coding" not in r["medicationCodeableConcept"]
             or r["medicationCodeableConcept"]["coding"] == [])
    ), r


# ---- Observation builder ----

def case_7_observation_with_unit():
    """Lab observation with unit produces Observation with valueQuantity."""
    r = build_observation(OBSERVATION_ROW, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "Observation"
        and r["status"] == "final"
        and r["subject"]["reference"] == "Patient/pat-test-01"
        and r["code"]["text"] == "HbA1c"
        and r["effectiveDateTime"] == "2023-05-22"
        and r["valueQuantity"]["value"] == 8.4
        and r["valueQuantity"]["unit"] == "%"
    ), r


def case_8_observation_no_unit_uses_valueString():
    """Observation with non-numeric value falls back to valueString."""
    r = build_observation(OBSERVATION_ROW_NO_UNIT, "pat_test_01")
    return (
        r is not None
        and r["resourceType"] == "Observation"
        and r["code"]["text"] == "Penicillin reaction"
        and "valueQuantity" not in r
        and r.get("valueString") == "rash"
    ), r


CASES = [
    ("01_patient_happy_path", case_1_patient_happy_path),
    ("02_patient_sex_mapping", case_2_patient_male_sex_mapping),
    ("03_condition_with_icd10", case_3_condition_with_icd10),
    ("04_condition_no_icd10", case_4_condition_no_icd10_code),
    ("05_medication_with_bnf", case_5_medication_with_bnf),
    ("06_medication_no_bnf", case_6_medication_no_bnf),
    ("07_observation_with_unit", case_7_observation_with_unit),
    ("08_observation_no_unit", case_8_observation_no_unit_uses_valueString),
]


def main() -> int:
    print("Running 8-case FHIR builder test set + R4B validator gate\n")
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
    print(f"\n{passes}/{len(CASES)} passed")
    if fails:
        print(f"FAILED: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())