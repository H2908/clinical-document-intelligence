"""
Worker — chains the pipeline for one document.

Pipeline:
  PDF -> parse -> clean -> NER -> negation -> dates -> lab parsing
       -> assemble NLP_OUTPUT.md JSON
       -> write JSON to disk (Phase 2)
       -> write entities + observations to Snowflake (Phase 3)
       -> run agent orchestrator (Phase 3)

This is the single function your worker thread will call per job.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Any

from parsers.pdf_parser import parse_pdf
from parsers.text_cleaner import clean_text
from nlp.medical_ner import extract_entities, Entity
from nlp.lab_parser import parse_labs
from nlp.negation_detector import detect_negation
from nlp.date_normaliser import normalise_dates

log = logging.getLogger(__name__)
NLP_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Derivations - entities -> conditions / medications
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
            "dose": "",
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
        One dict matching NLP_OUTPUT.md section 2.
    """
    log.info("Processing %s for %s", file_path, patient_id)
    processed_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

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
        "observations": [],
        "flags": [],
        "contradictions": [],
        "timeline_events": [],
    }

    # --- Pipeline ---------------------------------------------------------
    try:
        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        entities = extract_entities(cleaned)
        detect_negation(cleaned, entities)
        normalise_dates(entities, document_date)

        observations = parse_labs(
            text=cleaned,
            document_id=document_id,
            document_date=document_date,
        )
        payload["observations"] = observations
        log.info("Extracted %d lab observations from %s", len(observations), document_id)

        payload["entities"] = entities
        payload["conditions"] = _derive_conditions(entities)
        payload["medications"] = _derive_medications(entities)

    except (FileNotFoundError, ValueError) as e:
        # Known parser failures (missing file, not a PDF, encrypted, no text).
        log.warning("Document %s failed: %s", document_id, e)
        payload["status"] = "failed"
        payload["error_message"] = str(e)

    except Exception as e:
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
    pipeline can be developed against real output.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{payload['document_id']}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("Wrote %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# S3 + Snowflake entrypoint (Phase 3)
# ---------------------------------------------------------------------------

def process_from_s3(
    document_id: str,
    patient_id: str,
    s3_key: str,
    document_date: date,
    doc_type: str,
) -> dict[str, Any]:
    """
    Phase 3 entrypoint: downloads from S3, runs NLP pipeline, writes entities
    AND observations to CORE, runs agent orchestrator.
    """
    import os
    import tempfile
    import boto3
    from database.snowflake_writer import write_entities, write_observations

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

        # Promote to CORE + write entities and observations, only if processing succeeded
        if payload["status"] == "processed":
            from database.snowflake_writer import insert_core_document
            insert_core_document(
                document_id=document_id,
                patient_id=patient_id,
                file_name=Path(s3_key).name,
                doc_type=doc_type,
                s3_key=s3_key,
                document_date=document_date,
                source=None,
                extracted_text=payload.get("document", {}).get("extracted_text"),
                status="processed",
            )

            if payload["entities"]:
                try:
                    write_entities(document_id, patient_id, payload["entities"])
                except Exception:
                    log.exception("write_entities failed for %s", document_id)

            if payload.get("observations"):
                try:
                    write_observations(document_id, patient_id, payload["observations"])
                except Exception:
                    log.exception("write_observations failed for %s", document_id)

        # --- Run the agent orchestrator -------------------------------
        try:
            from agents.orchestrator import run_agents
            agent_state = run_agents(
                patient_id=patient_id,
                document_id=document_id,
            )
            agent_errors = agent_state.get("errors", [])
            if agent_errors:
                log.warning(
                    "Agent orchestrator finished with %d errors: %s",
                    len(agent_errors), agent_errors,
                )
            else:
                log.info(
                    "Agent orchestrator finished: %d timeline, %d flags, "
                    "%d contradictions, briefing %s",
                    len(agent_state.get("timeline_events", [])),
                    len(agent_state.get("flags", [])),
                    len(agent_state.get("contradictions", [])),
                    "present" if agent_state.get("briefing") else "missing",
                )
            payload["agent_counts"] = {
                "timeline_events": len(agent_state.get("timeline_events", [])),
                "flags": len(agent_state.get("flags", [])),
                "contradictions": len(agent_state.get("contradictions", [])),
                "briefing": agent_state.get("briefing") is not None,
                "errors": len(agent_errors),
            }
        except Exception as e:
            log.exception("Agent orchestrator crashed for %s", document_id)
            payload["agent_counts"] = {"error": str(e)}

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
    print(f"Observations: {len(result['observations'])}")
    print(f"Conditions: {len(result['conditions'])}")
    print(f"Medications: {len(result['medications'])}")
    print(f"Wrote: {out_path}")