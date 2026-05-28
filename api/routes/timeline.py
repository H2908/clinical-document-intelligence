from fastapi import APIRouter
from typing import Optional

router = APIRouter()


@router.get("/patients/{patient_id}/timeline")
def get_timeline(patient_id: str, type: Optional[str] = None) -> dict:
    events = [
        {"id": "evt_03", "date": "2024-04-10", "type": "Observation",
         "title": "eGFR 42 mL/min/1.73m2", "icd10_code": None,
         "source_document_id": "doc_91",
         "source_document_name": "DM_Review_10Apr2024.pdf"},
        {"id": "evt_02", "date": "2024-02-28", "type": "Diagnosis",
         "title": "Dilated cardiomyopathy diagnosed", "icd10_code": "I42.0",
         "source_document_id": "doc_77ab",
         "source_document_name": "Cardiology_28Feb2024.pdf"},
        {"id": "evt_01", "date": "2024-01-14", "type": "Referral",
         "title": "Cardiology referral sent", "icd10_code": None,
         "source_document_id": "doc_11",
         "source_document_name": "GP_Referral_14Jan2024.pdf"},
    ]
    if type:
        events = [e for e in events if e["type"] == type]
    return {"events": events}