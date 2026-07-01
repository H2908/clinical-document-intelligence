from agents.contradiction_agent import find_contradictions
from worker.document_processor import process_document
from datetime import date
from pathlib import Path

BASE = Path("data/synthetic/documents/patient_001")
docs_meta = [
    ("01_GP_Referral_Thompson_12Jan2024.pdf",  date(2024,1,12), "gp_referral"),
    ("02_Cardiology_Thompson_28Feb2024.pdf",   date(2024,2,28), "clinic_letter"),
    ("03_AE_Discharge_Thompson_04Apr2024.pdf", date(2024,4,4),  "discharge_summary"),
]
all_entities = []
documents = []
for filename, doc_date, doc_type in docs_meta:
    doc_id = f"patient_001_{Path(filename).stem}"
    r = process_document(
        file_path=BASE / filename,
        document_id=doc_id,
        patient_id="patient_001",
        document_date=doc_date,
        doc_type=doc_type,
    )
    for e in r.get("entities", []):
        e["document_id"] = doc_id
        e["document_date"] = doc_date.isoformat()
    all_entities.extend(r.get("entities", []))
    documents.append({
        "document_id": doc_id,
        "patient_id": "patient_001",
        "file_name": filename,
        "doc_type": doc_type,
        "document_date": doc_date.isoformat(),
        "extracted_text": r["document"].get("extracted_text", ""),
    })

result = find_contradictions(
    patient_id="patient_001",
    entities=all_entities,
    documents=documents,
)
print(f"Type: {type(result)}")
print(f"Length: {len(result)}")
if result:
    print(f"First element type: {type(result[0])}")
    print(f"First element: {result[0]}")