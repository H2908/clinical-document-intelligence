"""Rebuild fixture medications and conditions with document dates attached."""
import json
from pathlib import Path
from datetime import date
from worker.document_processor import process_document

PATIENTS = {
    "patient_001": [
        ("01_GP_Referral_Thompson_12Jan2024.pdf",     date(2024, 1, 12), "gp_referral"),
        ("02_Cardiology_Thompson_28Feb2024.pdf",      date(2024, 2, 28), "clinic_letter"),
        ("03_AE_Discharge_Thompson_04Apr2024.pdf",    date(2024, 4,  4), "discharge_summary"),
    ],
    "patient_002": [
        ("01_GP_Annual_Diabetes_Review_Ofori_22May2023.pdf", date(2023, 5, 22), "gp_referral"),
        ("02_Diabetes_Clinic_Ofori_18Sep2023.pdf",           date(2023, 9, 18), "clinic_letter"),
        ("03_Lab_Report_Ofori_14Feb2024.pdf",                date(2024, 2, 14), "lab_report"),
    ],
}

BASE = Path("data/synthetic/documents")
FIXTURES_DIR = Path("demo/fixtures")

for patient_id, docs_meta in PATIENTS.items():
    f = json.loads((FIXTURES_DIR / f"{patient_id}.json").read_text(encoding="utf-8"))

    # Rebuild conditions and medications WITH document date
    all_conditions = []
    all_medications = []

    for filename, doc_date, doc_type in docs_meta:
        doc_id = f"{patient_id}_{Path(filename).stem}"
        r = process_document(
            file_path=BASE / patient_id / filename,
            document_id=doc_id,
            patient_id=patient_id,
            document_date=doc_date,
            doc_type=doc_type,
        )
        for c in r.get("conditions", []):
            c["document_date"] = doc_date.isoformat()
            c["document_id"] = doc_id
            all_conditions.append(c)
        for m in r.get("medications", []):
            m["document_date"] = doc_date.isoformat()
            m["document_id"] = doc_id
            all_medications.append(m)

    f["conditions"] = all_conditions
    f["medications"] = all_medications

    (FIXTURES_DIR / f"{patient_id}.json").write_text(
        json.dumps(f, indent=2, default=str), encoding="utf-8"
    )
    print(f"[OK] {patient_id}: {len(all_conditions)} conditions, {len(all_medications)} medications with dates")