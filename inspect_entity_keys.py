"""Find the correct field names on extracted entity dicts."""
from worker.document_processor import process_document
from datetime import date
from pathlib import Path

result = process_document(
    file_path=Path("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf"),
    document_id="test",
    patient_id="patient_001",
    document_date=date(2024, 1, 12),
    doc_type="gp_referral",
)

print("=== First condition entity keys + values ===")
if result["conditions"]:
    print(result["conditions"][0])

print("\n=== First medication entity keys + values ===")
if result["medications"]:
    print(result["medications"][0])

print("\n=== First observation keys + values ===")
if result["observations"]:
    print(result["observations"][0])

print("\n=== First conflict entity keys + values ===")
entities = result.get("entities", [])
conflicts = [e for e in entities if e.get("entity_type") == "Conflict"]
if conflicts:
    print(conflicts[0])