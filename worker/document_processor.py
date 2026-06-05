"""
Worker — chains the pipeline for one document.

Pipeline:
  PDF -> parse -> clean -> NER -> negation -> dates
       -> assemble NLP_OUTPUT.md JSON
       -> write JSON to disk (Phase 2)
       -> (Phase 3: call snowflake_writer instead)

This is the single function your worker thread will call per job.
"""

from __future__ import annotations 
import json
import logging
from datetime import datetime,date
from pathlib import Path
from typing import Optional,Any

from parsers.pdf_parser import parse_pdf
from parsers.text_cleaner import clean_text
from nlp.medical_ner import extract_entities, Entity
from nlp.negation_detector import detect_negation
from nlp.date_normaliser import normalise_dates

log = logging.getLogger(__name__)
NLP_VERSION="1.0.0"

# ---------------------------------------------------------------------------
# Derivations — entities -> conditions / medications / observations
# ---------------------------------------------------------------------------


def _derive_conditions(entities: list[Entity]) -> list[dict[str, Any]]:
    """
    From non-negated Diagnosis entities, build the conditions[] list.
    Deduplicated by lowercase text.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for e in entities:
        if e["entity_type"] != "Diagnosis":
            continue
        if e.get("negated"):
            continue
        key = e["text"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": e["text"],
            "icd10_code": e.get("icd10_code"),
        })
    return out

def _derive_medications(entities: list[Entity]) -> list[dict[str, Any]]:
    """
    From non-negated Drug entities, build the medications[] list.
    Deduplicated by normalised_value (lowercase base drug name).
    Phase 2 leaves dose/started/flag blank; Phase 3's briefing agent fills them.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for e in entities:
        if e["entity_type"] != "Drug":
            continue
        if e.get("negated"):
            continue
        key = (e.get("normalised_value") or e["text"]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "drug": e["text"],
            "dose": "",          # Phase 3 — pair drug with following dose token
            "started": None,
            "flag_text": None,
        })
    return out

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_document(
    file_path: str | Path,
    document_id: str,
    patient_id: str,
    document_date: Optional[date] = None,
    doc_type: str = "clinic_letter",
) -> dict[str, Any]:
    """
    Process one document end-to-end.

    Args:
        file_path: path to the PDF on disk.
        document_id: ID assigned by the API when the upload landed (doc_<uuid>).
        patient_id: which patient this document belongs to (pat_<uuid>).
        document_date: clinical date of the document (used for relative-date
                       resolution like "2 weeks ago").
        doc_type: one of referral / clinic_letter / gp_note / discharge_summary
                  / lab_report / imaging / clinician_note.

    Returns:
        One dict matching NLP_OUTPUT.md §2.
    """
    log.info("Processing %s for %s", file_path, patient_id)
    processed_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    # Skeleton matching NLP_OUTPUT.md §2 — populated below.
    payload: dict[str, Any] = {
        "nlp_version": NLP_VERSION,
        "document_id": document_id,
        "patient_id": patient_id,
        "processed_at": processed_at,
        "status": "processed",
        "error_message": None,
        "document": {
            "doc_type": doc_type,
            "extracted_text": "",
            "image_url": None,
        },
        "entities": [],
        "conditions": [],
        "medications": [],
        "observations": [],     # Phase 3 — extracted from lab parsers
        "flags": [],            # Phase 3 — risk_flag_agent
        "contradictions": [],   # Phase 3 — contradiction_agent
        "timeline_events": [],  # Phase 3 — timeline_agent
    }

    # --- Pipeline ---------------------------------------------------------
    try:
        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        entities = extract_entities(cleaned)
        detect_negation(cleaned, entities)
        normalise_dates(entities, document_date)

        payload["entities"] = entities
        payload["conditions"] = _derive_conditions(entities)
        payload["medications"] = _derive_medications(entities)

    except (FileNotFoundError, ValueError) as e:
        # Known parser failures (missing file, not a PDF, encrypted, no text).
        # NLP_OUTPUT.md §5 says: status=failed, all arrays remain [], log it.
        log.warning("Document %s failed: %s", document_id, e)
        payload["status"] = "failed"
        payload["error_message"] = str(e)

    except Exception as e:
        # Unknown failure — still emit a valid payload so the document
        # doesn't silently vanish from the worker queue.
        log.exception("Document %s unexpected error", document_id)
        payload["status"] = "failed"
        payload["error_message"] = f"Unexpected error: {e}"

    return payload    
# ---------------------------------------------------------------------------
# Disk sink (Phase 2). Phase 3 replaces this with snowflake_writer calls.
# ---------------------------------------------------------------------------

def write_to_disk(payload: dict[str, Any], output_dir: str | Path) -> Path:
    """
    Phase 2 sink: write the payload JSON to disk so the rest of the
    pipeline (frontend, future agents) can be developed against real
    output before the storage layer is ready.

    Returns the path written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{payload['document_id']}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %s", out_path)
    return out_path

def process_from_s3(
    document_id: str,
    patient_id: str,
    s3_key: str,
    document_date: date,
    doc_type: str,
) -> dict[str, Any]:
    """
    Phase 2 Together Task 3 entrypoint.
    Downloads file from S3, runs the NLP pipeline, writes entities to CORE.
    """
    import os
    import tempfile
    import boto3
    from database.snowflake_writer import write_entities

    log.info("Processing %s from S3 (%s)", document_id, s3_key)

    s3 = boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    ext = Path(s3_key).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.close()

    try:
        s3.download_file(os.environ["AWS_S3_BUCKET"], s3_key, tmp.name)

        payload = process_document(
            file_path=tmp.name,
            document_id=document_id,
            patient_id=patient_id,
            document_date=document_date,
            doc_type=doc_type,
        )

        if payload["status"] == "processed" and payload["entities"]:
            # Promote the document to CORE first (so FK from entities is valid)
            from database.snowflake_writer import insert_core_document
            insert_core_document(
            document_id=document_id,
            patient_id=patient_id,
            file_name=Path(s3_key).name,
            doc_type=doc_type,
            s3_key=s3_key,
            document_date=document_date,
            source=None,  # could thread through from the API if needed
            extracted_text=payload.get("extracted_text"),
            status="processed",
        )
        if payload["entities"]:
            write_entities(document_id, patient_id, payload["entities"])

        return payload
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# CLI for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Usage:
        python -m worker.document_processor <pdf_path> [output_dir]
    """
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m worker.document_processor <pdf_path> [output_dir]")
        sys.exit(1)

    pdf = Path(sys.argv[1])
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "data/synthetic/processed")

    result = process_document(
        file_path=pdf,
        document_id=f"doc_{pdf.stem}",
        patient_id="pat_demo",
        document_date=date.today(),
        doc_type="clinic_letter",
    )
    out_path = write_to_disk(result, out_dir)
    print(f"Status: {result['status']}")
    print(f"Entities: {len(result['entities'])}")
    print(f"Conditions: {len(result['conditions'])}")
    print(f"Medications: {len(result['medications'])}")
    print(f"Wrote: {out_path}")