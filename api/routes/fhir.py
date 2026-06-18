"""FHIR R4 endpoints.

Exposes the patient-level FHIR Bundle stored in mart.fhir_patient_bundle.
The bundle is built by fhir.fhir_builder.write_fhir_bundle (call POST
/rebuild) and persisted in Snowflake. This module provides:

  GET  /patients/{patient_id}/fhir          - read cached bundle (200/404)
  POST /patients/{patient_id}/fhir/rebuild  - build + write fresh bundle (200)

Storage table: clinical_db.mart.fhir_patient_bundle (designed by partner
in database/schemas/05_fhir.sql).
"""
from __future__ import annotations
import json
import logging
import os

import snowflake.connector
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from clinical_fhir.fhir_builder import (
    build_patient_bundle,
    write_fhir_bundle,
    PatientNotFound,
)

load_dotenv()
log = logging.getLogger(__name__)
router = APIRouter()


def _conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


# ----------------------------------------------------------------------
# GET /patients/{patient_id}/fhir
# ----------------------------------------------------------------------
@router.get("/patients/{patient_id}/fhir")
def get_fhir_bundle(patient_id: str):
    """Return the cached FHIR Bundle for a patient.

    Reads mart.fhir_patient_bundle. If no row exists, returns 404 with a
    pointer to the rebuild endpoint. The bundle is returned with
    Content-Type: application/fhir+json (FHIR R4 convention).
    """
    try:
        conn = _conn()
    except Exception:
        log.exception("Snowflake connect failed for GET fhir")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT bundle, fhir_version, resource_count, generated_at, is_stale "
            "FROM clinical_db.mart.fhir_patient_bundle WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "no_bundle",
                              "message": (
                                  f"No FHIR bundle yet for {patient_id}. "
                                  f"POST /api/patients/{patient_id}/fhir/rebuild "
                                  "to build one.")}},
        )

    bundle_raw, fhir_version, resource_count, generated_at, is_stale = row

    # Snowflake VARIANT returns either str or already-parsed dict
    if isinstance(bundle_raw, str):
        try:
            bundle = json.loads(bundle_raw)
        except json.JSONDecodeError:
            log.exception("Stored bundle JSON is malformed for %s", patient_id)
            raise HTTPException(
                status_code=500,
                detail={"error": {"code": "internal_error",
                                  "message": "Stored bundle JSON is malformed"}},
            )
    else:
        bundle = bundle_raw

    # Sanity: returned object must be a Bundle
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        log.error("Stored object is not a FHIR Bundle for %s: type=%s",
                  patient_id, type(bundle).__name__)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": "Stored object is not a Bundle"}},
        )

    # FHIR convention: application/fhir+json
    return JSONResponse(
        content=bundle,
        headers={"Content-Type": "application/fhir+json"},
    )


# ----------------------------------------------------------------------
# POST /patients/{patient_id}/fhir/rebuild
# ----------------------------------------------------------------------
@router.post("/patients/{patient_id}/fhir/rebuild")
def rebuild_fhir_bundle(patient_id: str):
    """Build a fresh FHIR Bundle from CORE and write it to
    mart.fhir_patient_bundle (MERGE - inserts or updates).

    Returns metadata about the write, not the bundle itself. Call GET
    afterwards to retrieve the new bundle.
    """
    try:
        bundle = build_patient_bundle(patient_id)
    except PatientNotFound:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "patient_not_found",
                              "message": f"Patient {patient_id} not in CORE.patient"}},
        )
    except Exception as e:
        log.exception("build_patient_bundle failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Bundle build failed: {e}"}},
        )

    try:
        result = write_fhir_bundle(patient_id, bundle)
    except Exception as e:
        log.exception("write_fhir_bundle failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Bundle write failed: {e}"}},
        )

    return {
        "patient_id": patient_id,
        "resource_count": result["resource_count"],
        "rows_affected": result["rows_affected"],
        "message": (
            f"FHIR bundle rebuilt for {patient_id}: "
            f"{result['resource_count']} resources. "
            f"GET /api/patients/{patient_id}/fhir to retrieve."
        ),
    }
