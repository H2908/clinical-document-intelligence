"""
Clinician notes endpoints.

POST /patients/{patient_id}/notes — accepts plain text (NOT a file). Saves
the note as a document with doc_type='clinician_note', runs NER directly on
the submitted text without going through PDF parsing or S3. Useful for
quick clinical observations the doctor types directly.

GET /patients/{patient_id}/notes — returns the patient's notes from
CORE.document, filtered to doc_type='clinician_note'.
"""

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from database.snowflake_writer import (
    insert_raw_document,
    insert_core_document,
    write_entities,
)
from parsers.text_cleaner import clean_text
from nlp.medical_ner import extract_entities
from nlp.negation_detector import detect_negation
from nlp.date_normaliser import normalise_dates
from api.jobs import create_job, mark_running, mark_completed, mark_failed

log = logging.getLogger(__name__)
router = APIRouter()


# ---- Request body model ----
class ClinicianNote(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000,
                      description="The note body. Plain text, not formatted.")
    document_date: date = Field(...,
                                description="Clinical date of the note.")
    source: str | None = Field(None,
                               description="Optional - free-text source label.")


# ---- POST /patients/{patient_id}/notes ----
@router.post(
    "/patients/{patient_id}/notes",
    status_code=status.HTTP_202_ACCEPTED,
)
async def add_clinician_note(
    patient_id: str,
    note: ClinicianNote,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Notes pipeline (different from documents - no PDF, no S3):
      1. Clean the submitted text
      2. Extract entities (medical_ner + negation + date_normaliser)
      3. Insert into RAW.raw_documents with doc_type='clinician_note',
         s3_key=None (no file in storage for typed notes)
      4. Promote to CORE.document with extracted_text populated
      5. Write entities to CORE.entity
      6. Run agent orchestrator
    """
    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    # 1. Clean
    cleaned = clean_text(note.text)
    if not cleaned.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "validation_error",
                              "message": "Note text is empty after cleaning."}},
        )

    # 2. Extract entities (in-process; no PDF, no S3, no worker subprocess)
    try:
        entities = extract_entities(cleaned)
        detect_negation(cleaned, entities)
        normalise_dates(entities, note.document_date)
    except Exception as e:
        log.exception("NER pipeline failed for note %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"NLP pipeline failed: {e}"}},
        )

    # 3. RAW row - no s3_key for notes
    try:
        insert_raw_document(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=f"notes://{patient_id}/{document_id}",
            file_name=f"{document_id}_note.txt",
            doc_type="clinician_note",
            document_date=note.document_date,
            source=note.source,
        )
    except Exception as e:
        log.exception("RAW insert failed for note %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"DB insert failed: {e}"}},
        )

    # 4. Promote to CORE
    try:
        insert_core_document(
            document_id=document_id,
            patient_id=patient_id,
            file_name=f"{document_id}_note.txt",
            doc_type="clinician_note",
            s3_key=f"notes://{patient_id}/{document_id}",
            document_date=note.document_date,
            source=note.source,
            extracted_text=cleaned,
            status="processed",
        )
    except Exception as e:
        log.exception("CORE promote failed for note %s", document_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"CORE insert failed: {e}"}},
        )

    # 5. Write entities
    if entities:
        try:
            write_entities(document_id, patient_id, entities)
        except Exception as e:
            log.exception("write_entities failed for note %s", document_id)
            # Non-fatal: the note is saved; entities can be re-extracted later

    # 6. Run agents in background; respond now with what we know already
    job_id = create_job(
        kind="note_agents",
        context={"document_id": document_id, "patient_id": patient_id},
    )
    if background_tasks is not None:
        background_tasks.add_task(
            _run_note_agents_in_background,
            job_id=job_id,
            patient_id=patient_id,
            document_id=document_id,
        )
    else:
        # Fallback for callers that didn't pass BackgroundTasks - run inline
        _run_note_agents_in_background(job_id, patient_id, document_id)

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "saved",
        "doc_type": "clinician_note",
        "entity_count": len(entities),
        "message": (
            f"Note saved - {len(entities)} entities extracted. "
            "Agents running in background. Poll /api/jobs/{job_id}."
        ),
    }


def _run_note_agents_in_background(
    job_id: str,
    patient_id: str,
    document_id: str,
) -> None:
    mark_running(job_id)
    try:
        from agents.orchestrator import run_agents
        agent_state = run_agents(patient_id=patient_id, document_id=document_id)
        agent_counts = {
            "timeline_events": len(agent_state.get("timeline_events", [])),
            "flags": len(agent_state.get("flags", [])),
            "contradictions": len(agent_state.get("contradictions", [])),
            "briefing": agent_state.get("briefing") is not None,
            "errors": len(agent_state.get("errors", [])),
        }
        mark_completed(job_id, {
            "document_id": document_id,
            "agent_counts": agent_counts,
            "message": (
                f"Note agents complete - {agent_counts['flags']} flags, "
                f"{agent_counts['contradictions']} contradictions."
            ),
        })
    except Exception as e:
        log.exception("Agent orchestrator crashed for note %s", document_id)
        mark_failed(job_id, f"Agent orchestrator failed: {e}")


# ---- GET /patients/{patient_id}/notes ----
@router.get("/patients/{patient_id}/notes")
def list_patient_notes(patient_id: str) -> dict:
    """
    Return all clinician notes for a patient from CORE.document.
    Filters to doc_type='clinician_note', newest first.
    """
    import os
    import snowflake.connector
    from dotenv import load_dotenv

    load_dotenv()

    try:
        conn = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            database="clinical_db",
            warehouse="clinical_wh",
            role=os.environ["SNOWFLAKE_ROLE"],
        )
    except Exception:
        log.exception("Snowflake connect failed for notes read")
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "database_unavailable",
                              "message": "Could not connect to data warehouse"}},
        )

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                document_id,
                doc_type,
                document_date,
                source,
                status,
                extracted_text,
                created_at
            FROM clinical_db.core.document
            WHERE patient_id = %s
              AND doc_type = 'clinician_note'
            ORDER BY document_date DESC NULLS LAST, created_at DESC
        """, (patient_id,))
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
        notes = [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        log.exception("CORE.document read failed for %s", patient_id)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"Query failed: {e}"}},
        )
    finally:
        conn.close()

    # Serialise dates and timestamps for JSON
    for n in notes:
        if n.get("document_date") is not None:
            n["document_date"] = n["document_date"].isoformat()
        if n.get("created_at") is not None:
            n["created_at"] = n["created_at"].isoformat()

    return {
        "patient_id": patient_id,
        "count": len(notes),
        "notes": notes,
    }