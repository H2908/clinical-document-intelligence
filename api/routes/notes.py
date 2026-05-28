from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import date
from typing import Optional

router = APIRouter()


class NewNote(BaseModel):
    text: str
    document_date: date
    source: Optional[str] = None


@router.post("/patients/{patient_id}/notes",
             status_code=status.HTTP_202_ACCEPTED)
def add_note(patient_id: str, body: NewNote) -> dict:
    # Phase 2: store as a clinician_note document and enqueue NLP job
    return {
        "document_id": "doc_note1",
        "status": "pending",
        "message": "Added to record - processing entities.",
    }