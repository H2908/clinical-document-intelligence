from fastapi import APIRouter

router = APIRouter()


@router.get("/patients/{patient_id}/briefing")
def get_briefing(patient_id: str) -> dict:
    return {
        "patient": {
            "id": patient_id, "name": "Mohammed Al-Rashidi",
            "dob": "1970-03-12", "nhs_number": "485 621 3847",
            "sex": "M", "age": 54,
        },
        "generated_at": "2026-05-27T09:00:00Z",
        "disclaimer": ("For administrative use only - this briefing is generated "
                       "from extracted document data and does not constitute "
                       "clinical advice."),
        "conditions": [
            {"name": "Dilated cardiomyopathy", "icd10_code": "I42.0"},
            {"name": "Type 2 diabetes mellitus", "icd10_code": "E11"},
            {"name": "Essential hypertension", "icd10_code": "I10"},
            {"name": "Chronic kidney disease, stage 3a", "icd10_code": "N18.3"},
        ],
        "medications": [
            {"drug": "Bisoprolol", "dose": "2.5 mg OD",
             "started": "2024-02-28", "flag": None},
            {"drug": "Metformin", "dose": "1 g BD", "started": "2019-04-10",
             "flag": "eGFR below recommended threshold"},
        ],
        "recent_results": [
            {"test": "eGFR", "value": "42", "unit": "mL/min/1.73m2",
             "date": "2024-04-10", "trend": ["58", "49", "42"]},
            {"test": "HbA1c", "value": "62", "unit": "mmol/mol",
             "date": "2024-04-10", "trend": ["55", "58", "62"]},
            {"test": "LVEF", "value": "32", "unit": "%",
             "date": "2024-02-28", "trend": []},
        ],
        "open_flags": [],
        "recent_imaging": [],
        "last_documents": [
            {"document_id": "doc_91", "name": "DM_Review_10Apr2024.pdf",
             "date": "2024-04-10"},
            {"document_id": "doc_77ab", "name": "Cardiology_28Feb2024.pdf",
             "date": "2024-02-28"},
            {"document_id": "doc_11", "name": "GP_Referral_14Jan2024.pdf",
             "date": "2024-01-14"},
        ],
    }