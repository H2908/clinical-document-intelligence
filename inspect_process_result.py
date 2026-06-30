from worker.document_processor import process_document
from datetime import date
from pathlib import Path

result = process_document(
    file_path=Path("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf"),
    document_id="test_doc",
    patient_id="patient_001",
    document_date=date(2024, 1, 12),
    doc_type="gp_referral",
)
print("Keys:", list(result.keys()))
print()
for k, v in result.items():
    if isinstance(v, str):
        preview = v[:80].replace("\n", " ")
        print(f"  {k} (str, len={len(v)}): {preview!r}")
    elif isinstance(v, list):
        print(f"  {k} (list, len={len(v)})")
    elif isinstance(v, dict):
        print(f"  {k} (dict, keys={list(v.keys())[:5]})")
    else:
        print(f"  {k} ({type(v).__name__}): {v}")