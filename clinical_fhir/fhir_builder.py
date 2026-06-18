"""FHIR Bundle assembly + Snowflake persistence.

Public-facing module matching the partner's documented name in
database/schemas/05_fhir.sql:
    "ML partner owns the builder (fhir/fhir_builder.py)"

Exports:
    build_patient_bundle(patient_id) -> dict   - Pure assembly, no I/O
    write_fhir_bundle(patient_id, bundle)      - MERGE into mart.fhir_patient_bundle

build_patient_bundle reads from CORE via snowflake_reader (entities,
documents, observations), calls the four resource builders in
fhir.builders, deduplicates Conditions and MedicationStatements while
merging their evidence/source references, and wraps everything in a
FHIR R4 Bundle of type 'collection'.

Bundle structure:
  {
    "resourceType": "Bundle",
    "type": "collection",
    "timestamp": ISO 8601 UTC,
    "entry": [
      {"resource": {...Patient...}},
      {"resource": {...Condition...}},
      {"resource": {...MedicationStatement...}},
      ...
      {"resource": {...Observation...}},
    ]
  }

Dedup rule (Option C, locked):
  - Condition identity: (canonical_text, icd10_code)
    where canonical_text = text.lower().strip()
  - MedicationStatement identity: (normalised_value or canonical_text, bnf_code)
  - On collision, keep the FIRST resource encountered, but merge the
    evidence/informationSource references from later duplicates into
    the survivor's reference list.

Empty-data handling: if the patient has zero entities/observations, the
Bundle still contains the Patient resource (and that alone). Empty
Bundles without a Patient indicate the patient_id wasn't found in
CORE.patient - we raise PatientNotFound in that case.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from clinical_fhir.builders import (
    _fhir_ref,
    build_patient,
    build_condition,
    build_medication_statement,
    build_observation,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class PatientNotFound(Exception):
    """The patient_id wasn't found in CORE.patient. Raised by
    build_patient_bundle so the endpoint can return 404 cleanly."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canon(s: str) -> str:
    """Lowercase + strip. Used for dedup identity (matches the
    canonical() rule used everywhere else identity matters)."""
    return (s or "").strip().lower()


def _merge_evidence(existing: dict, new_entity: dict) -> None:
    """Append a DocumentReference to the existing Condition's evidence
    list when a duplicate Diagnosis appears in another document.

    Idempotent on the existing references - won't add the same doc id
    twice.
    """
    doc_id = new_entity.get("document_id")
    if not doc_id:
        return
    new_ref = {"reference": _fhir_ref(doc_id, "DocumentReference")}
    evidence = existing.setdefault("evidence", [{"detail": []}])
    if not evidence:
        evidence.append({"detail": []})
    detail = evidence[0].setdefault("detail", [])
    if not any(d.get("reference") == new_ref["reference"] for d in detail):
        detail.append(new_ref)


def _merge_information_source(existing: dict, new_entity: dict) -> None:
    """For MedicationStatement, FHIR R4 informationSource is a single
    Reference, not an array. To carry multi-document provenance without
    breaking R4 cardinality, we collect them in a contained extension.
    Pragmatic compromise: keep informationSource as-is (first doc),
    append additional docs to derivedFrom (an R4 0..* Reference array).
    """
    doc_id = new_entity.get("document_id")
    if not doc_id:
        return
    new_ref = {"reference": _fhir_ref(doc_id, "DocumentReference")}
    derived = existing.setdefault("derivedFrom", [])
    if not any(d.get("reference") == new_ref["reference"] for d in derived):
        derived.append(new_ref)


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------

def build_patient_bundle(
    patient_id: str,
    patient_row: Optional[dict] = None,
    entities: Optional[list[dict]] = None,
    observations: Optional[list[dict]] = None,
) -> dict:
    """Assemble a FHIR R4 Bundle (type=collection) for a patient.

    Args:
        patient_id: the CORE patient_id.
        patient_row, entities, observations: optional injected data,
            used by tests. If omitted, fetched from Snowflake via
            snowflake_reader.

    Returns:
        FHIR R4 Bundle dict.

    Raises:
        PatientNotFound: if patient_id isn't in CORE.patient.
    """
    # ---- Fetch data ----
    if patient_row is None:
        patient_row = _fetch_patient_row(patient_id)
        if patient_row is None:
            raise PatientNotFound(
                f"Patient {patient_id!r} not found in CORE.patient"
            )

    if entities is None:
        from database.snowflake_reader import read_entities_for_patient
        entities = read_entities_for_patient(patient_id)

    if observations is None:
        from database.snowflake_reader import read_observations_for_patient
        observations = read_observations_for_patient(patient_id)

    # ---- Build resources ----
    entries: list[dict] = []

    # 1. Patient (always present, always first)
    patient_resource = build_patient(patient_row)
    entries.append({"resource": patient_resource})

    # 2. Conditions (from Diagnosis entities), deduplicated on
    #    (canon(text), icd10_code), merging evidence refs.
    condition_index: dict[tuple, dict] = {}
    for ent in entities:
        if ent.get("entity_type") != "Diagnosis":
            continue
        key = (_canon(ent.get("text", "")), ent.get("icd10_code") or "")
        if key in condition_index:
            _merge_evidence(condition_index[key], ent)
        else:
            condition_index[key] = build_condition(ent, patient_id)
    for cond in condition_index.values():
        entries.append({"resource": cond})

    # 3. MedicationStatements (from Drug entities), dedup on
    #    (normalised_value or canon(text), bnf_code), merging derivedFrom refs.
    med_index: dict[tuple, dict] = {}
    for ent in entities:
        if ent.get("entity_type") != "Drug":
            continue
        norm = ent.get("normalised_value") or _canon(ent.get("text", ""))
        key = (norm, ent.get("bnf_code") or "")
        if key in med_index:
            _merge_information_source(med_index[key], ent)
        else:
            med_index[key] = build_medication_statement(ent, patient_id)
    for med in med_index.values():
        entries.append({"resource": med})

    # 4. Observations (one resource per row, no dedup - each lab value
    #    is a separate datum even if same test repeats over time).
    for obs in observations:
        entries.append({"resource": build_observation(obs, patient_id)})

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": entries,
    }


# ---------------------------------------------------------------------------
# Snowflake patient fetch
# ---------------------------------------------------------------------------

def _fetch_patient_row(patient_id: str) -> Optional[dict]:
    """Read a single patient row from CORE.patient.

    Returns dict with patient_id/name/dob/nhs_number/sex, or None if not found.
    """
    import os
    import snowflake.connector
    from dotenv import load_dotenv
    load_dotenv()

    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT patient_id, name, dob, nhs_number, sex "
            "FROM clinical_db.core.patient WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [c[0].lower() for c in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Snowflake bundle write
# ---------------------------------------------------------------------------

def write_fhir_bundle(patient_id: str, bundle: dict) -> dict:
    """MERGE a FHIR Bundle into mart.fhir_patient_bundle.

    UPSERT on patient_id. resource_count is derived from len(entry).
    is_stale is reset to FALSE on write (the bundle is fresh).

    Returns: {patient_id, resource_count, generated_at, rows_affected}
    """
    import os
    import json
    import snowflake.connector
    from dotenv import load_dotenv
    load_dotenv()

    resource_count = len(bundle.get("entry", []))
    bundle_json = json.dumps(bundle, default=str)

    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )
    try:
        cur = conn.cursor()
        # MERGE: insert new bundle or update existing. PARSE_JSON converts
        # the string payload to the VARIANT column. resource_count and
        # generated_at land on both branches; is_stale is reset to FALSE
        # because we just rebuilt.
        cur.execute(
            """
            MERGE INTO clinical_db.mart.fhir_patient_bundle AS t
            USING (SELECT %s AS patient_id) AS s
              ON t.patient_id = s.patient_id
            WHEN MATCHED THEN UPDATE SET
                bundle         = PARSE_JSON(%s),
                resource_count = %s,
                generated_at   = CURRENT_TIMESTAMP(),
                is_stale       = FALSE
            WHEN NOT MATCHED THEN INSERT
                (patient_id, bundle, fhir_version, resource_count,
                 generated_at, is_stale)
              VALUES
                (%s, PARSE_JSON(%s), 'R4', %s,
                 CURRENT_TIMESTAMP(), FALSE)
            """,
            (
                patient_id,
                bundle_json, resource_count,
                patient_id, bundle_json, resource_count,
            ),
        )
        rows_affected = cur.rowcount
        conn.commit()
        log.info(
            "write_fhir_bundle: patient_id=%s resource_count=%d rows_affected=%d",
            patient_id, resource_count, rows_affected,
        )
        return {
            "patient_id": patient_id,
            "resource_count": resource_count,
            "rows_affected": rows_affected,
        }
    finally:
        conn.close()