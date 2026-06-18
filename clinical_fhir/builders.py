"""FHIR R4 resource builders.

Pure functions. Each takes a domain dict (CORE.patient row, Entity from
nlp/medical_ner, CORE.observation row) and returns a FHIR R4 resource
dict, JSON-serialisable, no I/O, no external lookups.

Coverage:
    build_patient(patient_row)               -> Patient resource
    build_condition(entity, patient_id)      -> Condition resource
    build_medication_statement(entity, ...)  -> MedicationStatement resource
    build_observation(obs_row, patient_id)   -> Observation resource

Code system URLs:
    ICD-10:  http://hl7.org/fhir/sid/icd-10
    BNF UK:  https://fhir.hl7.org.uk/CodeSystem/UKCore-BNFLegacy
    NHS#:    https://fhir.nhs.uk/Id/nhs-number
    Local:   urn:cdi:patient-id

Out of scope: AllergyIntolerance, Encounter, FHIR R5.
"""
from __future__ import annotations
from typing import Any, Optional


# ---- Code system constants ----

CODE_SYSTEM_ICD10 = "http://hl7.org/fhir/sid/icd-10"
CODE_SYSTEM_BNF_UK = "https://fhir.hl7.org.uk/CodeSystem/UKCore-BNFLegacy"
ID_SYSTEM_NHS_NUMBER = "https://fhir.nhs.uk/Id/nhs-number"
ID_SYSTEM_LOCAL_PATIENT = "urn:cdi:patient-id"


# ---- ID sanitiser for FHIR R4B compliance ----

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


# ---- Sex/gender mapping ----

# Internal sex codes -> FHIR R4 gender values
# Reference: https://www.hl7.org/fhir/valueset-administrative-gender.html
_GENDER_MAP = {
    "M": "male",
    "F": "female",
    "Other": "other",
    "O": "other",
    "U": "unknown",
}


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

def build_patient(patient_row: dict) -> dict:
    """Build a FHIR R4 Patient resource from a CORE.patient row.

    Expected input fields: patient_id, name, dob, nhs_number, sex.
    Other fields ignored. Missing optional fields produce omitted elements
    (not present-as-null).
    """
    patient_id = patient_row["patient_id"]

    # Identifiers: NHS Number (official system) + internal id
    identifiers: list[dict] = []
    nhs_number = patient_row.get("nhs_number")
    if nhs_number:
        identifiers.append({
            "system": ID_SYSTEM_NHS_NUMBER,
            "value": str(nhs_number),
        })
    identifiers.append({
        "system": ID_SYSTEM_LOCAL_PATIENT,
        "value": patient_id,
    })

    # Name as a single text element (R4 also supports family + given,
    # but we don't store split names internally).
    name_text = patient_row.get("name") or ""

    # Gender mapping
    sex = patient_row.get("sex")
    gender = _GENDER_MAP.get(sex, "unknown")

    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": _to_fhir_id(patient_id),
        "identifier": identifiers,
        "name": [{"text": name_text}],
        "gender": gender,
    }

    # birthDate: FHIR expects YYYY-MM-DD string. Tolerate datetime/date objects.
    dob = patient_row.get("dob")
    if dob is not None:
        if hasattr(dob, "isoformat"):
            resource["birthDate"] = dob.isoformat()[:10]
        else:
            resource["birthDate"] = str(dob)[:10]

    return resource


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

def build_condition(entity: dict, patient_id: str) -> dict:
    """Build a FHIR R4 Condition resource from a Diagnosis Entity.

    Expected entity fields: text (required), icd10_code (optional),
    document_id (optional), document_date (optional).
    """
    text = entity.get("text", "")
    icd10 = entity.get("icd10_code")

    code: dict[str, Any] = {"text": text}
    if icd10:
        code["coding"] = [{
            "system": CODE_SYSTEM_ICD10,
            "code": icd10,
            "display": text,
        }]

    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "subject": {"reference": _fhir_ref(patient_id, "Patient")},
        "code": code,
    }

    # Provenance: link back to the source document if known
    document_id = entity.get("document_id")
    if document_id:
        resource["evidence"] = [{
            "detail": [{"reference": _fhir_ref(document_id, "DocumentReference")}],
        }]

    # Onset / recorded date
    doc_date = entity.get("document_date")
    if doc_date is not None:
        if hasattr(doc_date, "isoformat"):
            resource["recordedDate"] = doc_date.isoformat()[:10]
        else:
            resource["recordedDate"] = str(doc_date)[:10]

    return resource


# ---------------------------------------------------------------------------
# MedicationStatement
# ---------------------------------------------------------------------------

def build_medication_statement(entity: dict, patient_id: str) -> dict:
    """Build a FHIR R4 MedicationStatement resource from a Drug Entity.

    Expected entity fields: text (required), bnf_code (optional),
    normalised_value (optional - the canonical lowercase drug name),
    document_id (optional), document_date (optional).
    """
    raw_text = entity.get("text", "")
    bnf = entity.get("bnf_code")

    # Prefer the canonical normalised name when available; fall back to raw
    medication_text = entity.get("normalised_value") or raw_text

    medication_concept: dict[str, Any] = {"text": medication_text}
    if bnf:
        medication_concept["coding"] = [{
            "system": CODE_SYSTEM_BNF_UK,
            "code": bnf,
            "display": medication_text,
        }]

    resource: dict[str, Any] = {
        "resourceType": "MedicationStatement",
        "status": "active",  # default - we don't track stopped meds yet
        "subject": {"reference": _fhir_ref(patient_id, "Patient")},
        "medicationCodeableConcept": medication_concept,
    }

    # Provenance: link back to source document
    document_id = entity.get("document_id")
    if document_id:
        resource["informationSource"] = {
            "reference": _fhir_ref(document_id, "DocumentReference"),
        }

    # effectiveDateTime: when the medication was recorded
    doc_date = entity.get("document_date")
    if doc_date is not None:
        if hasattr(doc_date, "isoformat"):
            resource["effectiveDateTime"] = doc_date.isoformat()[:10]
        else:
            resource["effectiveDateTime"] = str(doc_date)[:10]

    return resource


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

def _try_parse_numeric(value: Any) -> Optional[float]:
    """Return value as float if it parses cleanly, else None.

    Used to decide between valueQuantity (numeric) and valueString (text)
    in Observation. Returns None for things like 'rash', 'positive', etc.
    """
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def build_observation(obs_row: dict, patient_id: str) -> dict:
    """Build a FHIR R4 Observation resource from a CORE.observation row.

    Expected fields: test, value, unit (optional), observation_date
    (optional), source_document_id (optional), observation_id (optional).

    Numeric values produce valueQuantity. Non-numeric values produce
    valueString. Missing unit on numeric values is tolerated.
    """
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "status": "final",
        "subject": {"reference": _fhir_ref(patient_id, "Patient")},
        "code": {"text": obs_row.get("test", "")},
    }

    obs_id = obs_row.get("observation_id")
    if obs_id:
        resource["id"] = _to_fhir_id(obs_id)

    obs_date = obs_row.get("observation_date")
    if obs_date is not None:
        if hasattr(obs_date, "isoformat"):
            resource["effectiveDateTime"] = obs_date.isoformat()[:10]
        else:
            resource["effectiveDateTime"] = str(obs_date)[:10]

    # Value: numeric -> valueQuantity, otherwise valueString
    value = obs_row.get("value")
    unit = obs_row.get("unit")
    numeric = _try_parse_numeric(value)
    if numeric is not None:
        quantity: dict[str, Any] = {"value": numeric}
        if unit:
            quantity["unit"] = unit
        resource["valueQuantity"] = quantity
    elif value is not None:
        resource["valueString"] = str(value)

    # Provenance
    src = obs_row.get("source_document_id")
    if src:
        resource["derivedFrom"] = [{
            "reference": _fhir_ref(src, "DocumentReference"),
        }]

    return resource