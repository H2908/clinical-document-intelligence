import time
from pathlib import Path
from datetime import date
from worker.document_processor import process_document

t0 = time.time()
r = process_document(
    file_path=Path("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf"),
    document_id="perf_test",
    patient_id="patient_001",
    document_date=date(2024, 1, 12),
    doc_type="gp_referral",
)
wall = time.time() - t0
print(f"Wall clock: {wall:.2f}s")
print(f"Entities: {len(r['entities'])}")
print(f"Status: {r['status']}")