from fastapi import APIRouter, UploadFile, File, Form, status
from datetime import date

router = APIRouter()


@router.get("/patients/{patient_id}/documents")
def list_patient_documents(patient_id: str) -> dict:
    return {
        "documents": [
            {"id": "doc_11", "name": "GP_Referral_14Jan2024.pdf",
             "type": "referral", "source": "EMIS Web",
             "date": "2024-01-14", "status": "processed"},
            {"id": "doc_77ab", "name": "Cardiology_28Feb2024.pdf",
             "type": "clinic_letter", "source": "Trust EPR",
             "date": "2024-02-28", "status": "processed"},
            {"id": "doc_91", "name": "DM_Review_10Apr2024.pdf",
             "type": "clinic_letter", "source": "EMIS Web",
             "date": "2024-04-10", "status": "processed"},
        ]
    }


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    return {
        "id": document_id,
        "name": "Cardiology_28Feb2024.pdf",
        "type": "clinic_letter",
        "source": "Trust EPR",
        "date": "2024-02-28",
        "status": "processed",
        "extracted_text": (
            "Patient reports penicillin allergy - rash on exposure 2019. "
            "Avoid beta-lactams. Echocardiogram on 28 Feb 2024 confirms "
            "dilated cardiomyopathy with LVEF 32%. Commenced bisoprolol 2.5 mg."
        ),
        "entities": [
            {"text": "penicillin allergy", "type": "Conflict", "start": 16, "end": 34},
            {"text": "dilated cardiomyopathy", "type": "Diagnosis", "start": 108, "end": 130},
            {"text": "bisoprolol 2.5 mg", "type": "Drug", "start": 165, "end": 182},
            {"text": "28 Feb 2024", "type": "Date", "start": 80, "end": 91},
        ],
        "image_url": None,
        "lab_results": None,
    }


@router.post("/patients/{patient_id}/documents",
             status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    patient_id: str,
    file: UploadFile = File(...),
    document_date: date = Form(...),
    type: str = Form(...),
    source: str | None = Form(None),
) -> dict:
    # Phase 2: push to S3 + enqueue worker job here
    return {
        "document_id": "doc_new1",
        "status": "pending",
        "message": "Added to record - processing entities.",
    }