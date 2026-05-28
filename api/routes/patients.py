from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

router = APIRouter()

MOCK_PATIENTS = [
    {
        "id": "pat_8f3a", "name": "Mohammed Al-Rashidi", "dob": "1970-03-12",
        "nhs_number": "485 621 3847", "sex": "M",
        "document_count": 3, "open_flag_count": 3,
        "last_updated": "2024-04-10T09:00:00Z",
    },
    {
        "id": "pat_2c7b", "name": "Eleanor Whitfield", "dob": "1948-09-28",
        "nhs_number": "602 114 7785", "sex": "F",
        "document_count": 3, "open_flag_count": 2,
        "last_updated": "2024-05-02T10:30:00Z",
    },
    {
        "id": "pat_4d1e", "name": "Daniel Osei", "dob": "1991-07-05",
        "nhs_number": "733 908 2210", "sex": "M",
        "document_count": 2, "open_flag_count": 1,
        "last_updated": "2024-02-22T14:15:00Z",
    },
]


class NewPatient(BaseModel):
    name: str
    dob: date
    nhs_number: str
    sex: Literal["M", "F", "Other"]


@router.get("/patients")
def list_patients(search: Optional[str] = None) -> dict:
    items = MOCK_PATIENTS
    if search:
        s = search.lower()
        items = [p for p in items if s in p["name"].lower() or s in p["nhs_number"]]
    return {"patients": items}


@router.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(body: NewPatient) -> dict:
    # Phase 2: write to Snowflake. For now, echo a created card shape.
    return {
        "id": "pat_new1",
        "name": body.name,
        "dob": body.dob.isoformat(),
        "nhs_number": body.nhs_number,
        "sex": body.sex,
        "document_count": 0,
        "open_flag_count": 0,
        "last_updated": "2026-05-27T09:00:00Z",
    }


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str) -> dict:
    for p in MOCK_PATIENTS:
        if p["id"] == patient_id:
            return {
                **p,
                "age": 54,
                "stats": {
                    "document_count": p["document_count"],
                    "open_flag_count": p["open_flag_count"],
                    "contradiction_count": 1,
                },
                "conditions": [
                    {"name": "Dilated cardiomyopathy", "icd10_code": "I42.0"},
                    {"name": "Type 2 diabetes mellitus", "icd10_code": "E11"},
                ],
                "medications": [
                    {"drug": "Bisoprolol", "dose": "2.5 mg OD",
                     "started": "2024-02-28", "flag": None},
                    {"drug": "Metformin", "dose": "1 g BD",
                     "started": "2019-04-10",
                     "flag": "eGFR below recommended threshold"},
                ],
                "top_flags": [],
            }
    raise HTTPException(status_code=404,
        detail={"error": {"code": "not_found",
                          "message": f"Patient {patient_id} does not exist."}})


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: str) -> dict:
    return {"deleted": True, "patient_id": patient_id}