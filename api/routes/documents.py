from cmath import log
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from datetime import date
from database.snowflake_writer import insert_raw_document
from ingestion.s3_uploader import upload

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
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    original_ext = Path(file.filename or "").suffix or ".pdf"
    s3_key = f"uploads/{patient_id}/{document_id}{original_ext}"
    file_name = file.filename or f"{document_id}{original_ext}"

    try:
        upload(file.file, s3_key)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 upload failed: {e}"}},
        )

    try:
        insert_raw_document(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            file_name=file_name,
            doc_type=type,
            document_date=document_date,
            source=source,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "internal_error",
                              "message": f"S3 ok but DB insert failed: {e}"}},
        )
    # 3. Run NLP pipeline synchronously (Phase 2 milestone — Phase 3 will move
    # this to a background worker polling raw_documents).
    from worker.document_processor import process_from_s3
    try:
        result = process_from_s3(
            document_id=document_id,
            patient_id=patient_id,
            s3_key=s3_key,
            document_date=document_date,
            doc_type=type,
        )
        final_status = result["status"]
        entity_count = len(result["entities"])
    except Exception as e:
        log.exception("Worker pipeline failed for %s", document_id)
        final_status = "failed"
        entity_count = 0

    return {
        "document_id": document_id,
        "status": final_status,
        "entity_count": entity_count,
        "message": (
            f"Document processed — {entity_count} entities extracted."
            if final_status == "processed"
            else "Document received but processing failed - check logs."
        ),
    }