"""Batch ingest synthetic patients 001, 002, 006, 009, 013 through the
worker pipeline. Calls process_document() directly with correct patient_id
and document_date extracted from the filename. Logs entity count per doc.
"""
import logging
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

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
    "patient_006": [
        ("01_GP_Diabetes_Review_Patel_14Nov2023.pdf",        date(2023, 11, 14), "gp_referral"),
        ("02_Diabetes_Clinic_Patel_09Feb2024.pdf",           date(2024,  2,  9), "clinic_letter"),
        ("03_GP_Hypertension_Review_Patel_18Jun2024.pdf",    date(2024,  6, 18), "gp_referral"),
    ],
    "patient_009": [
        ("01_GP_Asthma_Review_Bennett_11Mar2024.pdf",        date(2024,  3, 11), "gp_referral"),
        ("02_Respiratory_Clinic_Bennett_22Aug2024.pdf",      date(2024,  8, 22), "clinic_letter"),
        ("03_AE_Discharge_Bennett_09Nov2024.pdf",            date(2024, 11,  9), "discharge_summary"),
    ],
    "patient_013": [
        ("01_GP_CKD_Review_Walsh_16Jan2024.pdf",             date(2024,  1, 16), "gp_referral"),
        ("02_Renal_Clinic_Walsh_14May2024.pdf",              date(2024,  5, 14), "clinic_letter"),
        ("03_GP_Locum_Walsh_22Oct2024.pdf",                  date(2024, 10, 22), "gp_referral"),
    ],
}

BASE = Path("data/synthetic/documents")
results = []
errors = []

for patient_id, docs in PATIENTS.items():
    print(f"\n{'='*60}")
    print(f"Patient: {patient_id}")
    print(f"{'='*60}")
    for filename, doc_date, doc_type in docs:
        pdf_path = BASE / patient_id / filename
        doc_id = f"{patient_id}_{Path(filename).stem}"
        try:
            result = process_document(
                file_path=pdf_path,
                document_id=doc_id,
                patient_id=patient_id,
                document_date=doc_date,
                doc_type=doc_type,
            )
            n_entities = len(result.get("entities", []))
            n_obs = len(result.get("observations", []))
            has_text = bool((result.get("document") or {}).get("extracted_text", "").strip())
            status = result.get("status", "unknown")
            results.append((patient_id, filename, status, n_entities, n_obs, has_text))
            marker = "[OK]" if status == "success" and has_text else "[WARN]"
            print(f"  {marker} {filename}")
            print(f"       status={status}  entities={n_entities}  obs={n_obs}  text={'yes' if has_text else 'NO'}")
        except Exception as e:
            errors.append((patient_id, filename, str(e)))
            print(f"  [FAIL] {filename}")
            print(f"         {e}")

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"{'patient':<15} {'file':<50} {'status':<10} {'ents':>5} {'obs':>5} {'text':>5}")
print("-" * 95)
for patient_id, filename, status, n_ents, n_obs, has_text in results:
    short = filename[:48]
    print(f"{patient_id:<15} {short:<50} {status:<10} {n_ents:>5} {n_obs:>5} {'yes' if has_text else 'NO':>5}")

if errors:
    print(f"\n[ERRORS] {len(errors)} documents failed:")
    for patient_id, filename, err in errors:
        print(f"  {patient_id} / {filename}: {err}")
else:
    print(f"\n[OK] All {len(results)} documents processed without exception.")

text_missing = [(p, f) for p, f, s, e, o, t in results if not t]
if text_missing:
    print(f"\n[WARN] extracted_text empty for {len(text_missing)} documents:")
    for p, f in text_missing:
        print(f"  {p} / {f}")
else:
    print(f"[OK] extracted_text populated for all {len(results)} documents.")
