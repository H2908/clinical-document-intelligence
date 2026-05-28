from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import date
from typing import Optional

router = APIRouter()


class LabResult(BaseModel):
    test: str
    value: str
    unit: str
    date: date


class NewLabs(BaseModel):
    document_date: date
    source: Optional[str] = None
    results: list[LabResult]


@router.post("/patients/{patient_id}/labs",
             status_code=status.HTTP_202_ACCEPTED)
def add_labs(patient_id: str, body: NewLabs) -> dict:
    # Phase 2: store as a lab_report document, write observations
    return {
        "document_id": "doc_lab1",
        "status": "pending",
        "message": "Added to record - processing entities.",
    }