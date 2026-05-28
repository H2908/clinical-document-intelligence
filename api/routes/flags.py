from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter()

MOCK_FLAGS = [
    {
        "id": "flag_4c1d", "severity": "HIGH", "category": "ALLERGY CONFLICT",
        "description": ("Allergy status conflicts between GP letter (NKDA) and "
                        "cardiology letter (penicillin allergy). Verify before "
                        "prescribing antibiotics."),
        "source_document_id": "doc_77ab",
        "source_document_name": "Cardiology_28Feb2024.pdf",
        "status": "open", "created_at": "2024-02-28T00:00:00Z",
    },
    {
        "id": "flag_5e2a", "severity": "HIGH", "category": "OVERDUE REFERRAL",
        "description": ("Heart failure nurse follow-up was due 4 weeks ago. "
                        "No record of appointment or attendance."),
        "source_document_id": "doc_77ab",
        "source_document_name": "Cardiology_28Feb2024.pdf",
        "status": "open", "created_at": "2024-02-28T00:00:00Z",
    },
    {
        "id": "flag_8f33", "severity": "MEDIUM", "category": "DRUG SAFETY",
        "description": ("Metformin 1 g BD continues despite eGFR of "
                        "42 mL/min/1.73m2. Consider dose reduction per NICE."),
        "source_document_id": "doc_91",
        "source_document_name": "DM_Review_10Apr2024.pdf",
        "status": "open", "created_at": "2024-04-10T00:00:00Z",
    },
]


class FlagPatch(BaseModel):
    status: Literal["open", "resolved"]


@router.get("/patients/{patient_id}/flags")
def list_flags(patient_id: str, status: Optional[str] = None) -> dict:
    items = MOCK_FLAGS
    if status:
        items = [f for f in items if f["status"] == status]
    return {
        "open_count": sum(1 for f in MOCK_FLAGS if f["status"] == "open"),
        "resolved_count": sum(1 for f in MOCK_FLAGS if f["status"] == "resolved"),
        "flags": items,
    }


@router.patch("/flags/{flag_id}")
def update_flag(flag_id: str, body: FlagPatch) -> dict:
    return {**MOCK_FLAGS[0], "id": flag_id, "status": body.status}