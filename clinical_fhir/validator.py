"""FHIR R4B validation wrapper using the fhir.resources library.

Phase 4 L2. Round-trips every builder output through the official R4B
schema parser. Catches:
  - Required fields missing
  - Wrong types (string where Reference expected, etc.)
  - Bad cardinality (informationSource is 0..1, derivedFrom is 0..*)
  - Malformed nested resources

Tolerates:
  - Unknown extension fields
  - System URLs the library doesn't recognise as canonical (warning, not error)

Why R4B not R4: R4B is FHIR R4's corrected revision (technical errata
patch from 2023). Most production servers and EHRs target R4B. Same
resource shapes for our purposes; minor cardinality bug fixes.

Usage:
    from clinical_fhir.validator import validate_resource, validate_bundle

    err = validate_resource(patient_dict)  # None if valid, dict if not
    err = validate_bundle(bundle_dict)
"""
from __future__ import annotations
import logging
from typing import Any, Optional

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.medicationstatement import MedicationStatement
from fhir.resources.R4B.observation import Observation

log = logging.getLogger(__name__)


# Map resourceType string to the fhir.resources model class
_RESOURCE_MODELS = {
    "Patient": Patient,
    "Condition": Condition,
    "MedicationStatement": MedicationStatement,
    "Observation": Observation,
    "Bundle": Bundle,
}


def validate_resource(resource: dict) -> Optional[dict]:
    """Validate a single FHIR resource dict against its R4B schema.

    Args:
        resource: dict with 'resourceType' and resource fields.

    Returns:
        None if valid. A dict with {resourceType, errors} if invalid.
    """
    rt = resource.get("resourceType")
    if rt is None:
        return {"resourceType": None, "errors": ["resourceType field is missing"]}

    model = _RESOURCE_MODELS.get(rt)
    if model is None:
        return {"resourceType": rt, "errors": [f"unknown resourceType: {rt!r}"]}

    try:
        # fhir.resources 8.x uses pydantic v2 model_validate
        model.model_validate(resource)
        return None
    except Exception as e:
        return {
            "resourceType": rt,
            "errors": _extract_errors(e),
        }


def validate_bundle(bundle: dict) -> dict:
    """Validate a FHIR Bundle and every resource inside it.

    Returns:
        {
            "bundle_valid": bool,
            "bundle_errors": list[str],
            "entry_count": int,
            "entry_results": list[{index, resourceType, valid, errors}],
            "summary": {valid_count, invalid_count},
        }

    Bundle validation runs FIRST. If the Bundle envelope is invalid, we
    still walk entries (to surface every issue at once rather than fail-
    fast).
    """
    bundle_err = validate_resource(bundle)
    bundle_valid = bundle_err is None
    bundle_errors: list[str] = [] if bundle_valid else bundle_err["errors"]

    entries = bundle.get("entry", []) or []
    entry_results = []
    valid_count = 0
    invalid_count = 0

    for i, entry in enumerate(entries):
        resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
        err = validate_resource(resource)
        rt = resource.get("resourceType", "?")
        if err is None:
            entry_results.append({
                "index": i,
                "resourceType": rt,
                "valid": True,
                "errors": [],
            })
            valid_count += 1
        else:
            entry_results.append({
                "index": i,
                "resourceType": rt,
                "valid": False,
                "errors": err["errors"],
            })
            invalid_count += 1

    return {
        "bundle_valid": bundle_valid,
        "bundle_errors": bundle_errors,
        "entry_count": len(entries),
        "entry_results": entry_results,
        "summary": {
            "valid_count": valid_count,
            "invalid_count": invalid_count,
        },
    }


def _extract_errors(exc: Exception) -> list[str]:
    """Pull human-readable error strings out of a pydantic ValidationError
    (or any other exception). Returns a list of short messages."""
    # pydantic v2 ValidationError has .errors() returning list of dicts
    if hasattr(exc, "errors") and callable(exc.errors):
        try:
            errs = exc.errors()
            messages = []
            for e in errs:
                loc = ".".join(str(part) for part in e.get("loc", []))
                msg = e.get("msg", "")
                typ = e.get("type", "")
                messages.append(f"{loc}: {msg} (type={typ})" if loc else f"{msg} (type={typ})")
            return messages
        except Exception:
            pass
    return [f"{type(exc).__name__}: {exc}"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI: validate a FHIR Bundle from a JSON file or from Snowflake.

    Usage:
        python -m clinical_fhir.validator --file path/to/bundle.json
        python -m clinical_fhir.validator --patient pat_test_01  (reads
                                                                  from CORE
                                                                  via the
                                                                  builder)
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Validate FHIR R4B Bundle or resource."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Path to JSON file containing a Bundle.")
    src.add_argument("--patient", help="Patient ID; build bundle from CORE then validate.")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            bundle = json.load(f)
    else:
        from clinical_fhir.fhir_builder import build_patient_bundle
        bundle = build_patient_bundle(args.patient)

    report = validate_bundle(bundle)
    print(f"Bundle envelope valid: {report['bundle_valid']}")
    if not report["bundle_valid"]:
        print("Bundle errors:")
        for err in report["bundle_errors"]:
            print(f"  - {err}")

    print(f"Entries: {report['entry_count']}")
    print(f"Valid:   {report['summary']['valid_count']}")
    print(f"Invalid: {report['summary']['invalid_count']}")

    if report["summary"]["invalid_count"] > 0:
        print("\nInvalid entries:")
        for entry in report["entry_results"]:
            if not entry["valid"]:
                print(f"  [{entry['index']}] {entry['resourceType']}:")
                for err in entry["errors"]:
                    print(f"      - {err}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())