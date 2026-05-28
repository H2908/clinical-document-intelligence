from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

router = APIRouter()


class ContradictionPatch(BaseModel):
    status: Literal["open", "resolved"]


@router.get("/patients/{patient_id}/contradictions")
def list_contradictions(patient_id: str) -> dict:
    return {
        "contradictions": [
            {
                "id": "con_22",
                "severity": "HIGH",
                "category": "ALLERGY",
                "status": "open",
                "document_a": {
                    "document_id": "doc_11",
                    "document_name": "GP_Referral_14Jan2024.pdf",
                    "date": "2024-01-14",
                    "statement": "NKDA - no known drug allergies recorded.",
                },
                "document_b": {
                    "document_id": "doc_77ab",
                    "document_name": "Cardiology_28Feb2024.pdf",
                    "date": "2024-02-28",
                    "statement": ("Penicillin allergy - patient reports rash on "
                                  "exposure in 2019. Avoid beta-lactams."),
                },
                "explanation": ("Two recent documents disagree about drug allergy "
                                "status. The cardiology record is more recent and "
                                "patient-reported. Recommend confirming directly "
                                "with the patient."),
            }
        ]
    }


@router.patch("/contradictions/{contradiction_id}")
def update_contradiction(contradiction_id: str, body: ContradictionPatch) -> dict:
    return {"id": contradiction_id, "status": body.status}