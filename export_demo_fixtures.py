"""Export pre-computed pipeline results for EMNLP demo fixtures.
Runs the full pipeline (NER + flag agent + contradiction agent) on
patient_001 and patient_002 locally and writes results to demo/fixtures/.
Zero Snowflake, zero S3. Pure local execution against synthetic PDFs.
Does NOT modify any existing code — standalone export script only.
"""
import json
import time
from datetime import date
from pathlib import Path

# ---- Config ----
PATIENTS = {
    "patient_001": {
        "name": "Margaret Thompson",
        "dob": "1954-08-15",
        "nhs": "999 100 0001",
        "sex": "F",
        "domain": "Cardiology + CKD",
        "docs": [
            ("01_GP_Referral_Thompson_12Jan2024.pdf",     date(2024, 1, 12), "gp_referral"),
            ("02_Cardiology_Thompson_28Feb2024.pdf",      date(2024, 2, 28), "clinic_letter"),
            ("03_AE_Discharge_Thompson_04Apr2024.pdf",    date(2024, 4,  4), "discharge_summary"),
        ],
    },
    "patient_002": {
        "name": "Daniel Ofori",
        "dob": "1968-03-22",
        "nhs": "999 200 0002",
        "sex": "M",
        "domain": "Type 2 Diabetes",
        "docs": [
            ("01_GP_Annual_Diabetes_Review_Ofori_22May2023.pdf", date(2023, 5, 22), "gp_referral"),
            ("02_Diabetes_Clinic_Ofori_18Sep2023.pdf",           date(2023, 9, 18), "clinic_letter"),
            ("03_Lab_Report_Ofori_14Feb2024.pdf",                date(2024, 2, 14), "lab_report"),
        ],
    },
}

BASE = Path("data/synthetic/documents")
OUT_DIR = Path("demo/fixtures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

from worker.document_processor import process_document
from agents.flag_agent import detect_flags
from agents.contradiction_agent import find_contradictions

for patient_id, meta in PATIENTS.items():
    print(f"\n{'='*60}")
    print(f"Processing {patient_id} — {meta['name']}")
    print(f"{'='*60}")

    all_entities = []
    all_observations = []
    all_conditions = []
    all_medications = []
    documents = []
    t_total = 0.0

    for filename, doc_date, doc_type in meta["docs"]:
        doc_id = f"{patient_id}_{Path(filename).stem}"
        pdf_path = BASE / patient_id / filename
        print(f"  Processing {filename}...")
        t0 = time.time()
        result = process_document(
            file_path=pdf_path,
            document_id=doc_id,
            patient_id=patient_id,
            document_date=doc_date,
            doc_type=doc_type,
        )
        wall = time.time() - t0
        t_total += wall

        doc_record = {
            "document_id": doc_id,
            "patient_id": patient_id,
            "file_name": filename,
            "doc_type": doc_type,
            "document_date": doc_date.isoformat(),
            "extracted_text": result["document"].get("extracted_text", ""),
            "wall_clock_seconds": round(wall, 2),
        }
        documents.append(doc_record)

        for e in result.get("entities", []):
            e["document_id"] = doc_id
            e["document_date"] = doc_date.isoformat()
        all_entities.extend(result.get("entities", []))

        for o in result.get("observations", []):
            o["document_id"] = doc_id
            if hasattr(o.get("observation_date"), "isoformat"):
                o["observation_date"] = o["observation_date"].isoformat()
        all_observations.extend(result.get("observations", []))
        all_conditions.extend(result.get("conditions", []))
        all_medications.extend(result.get("medications", []))

        print(f"    entities={len(result.get('entities',[]))}  "
              f"obs={len(result.get('observations',[]))}  "
              f"wall={wall:.2f}s")

    print(f"  Running flag agent (rules_only mode)...")
    t0 = time.time()
    flags, flag_meta = detect_flags(
        patient_id=patient_id,
        entities=all_entities,
        documents=documents,
        mode="rules_only",
    )
    flag_wall = time.time() - t0
    print(f"    flags={len(flags)}  wall={flag_wall:.2f}s")

    print(f"  Running contradiction agent...")
    t0 = time.time()
    try:
        contra_tuple = find_contradictions(
            patient_id=patient_id,
            entities=all_entities,
            documents=documents,
        )
        # find_contradictions returns (rule_list, llm_list)
        contradictions = [
            c for sub in contra_tuple
            for c in (sub if isinstance(sub, list) else [sub])
            if isinstance(c, dict)
        ]
    except Exception as e:
        print(f"    [WARN] contradiction agent error: {e}")
        contradictions = []
    contra_wall = time.time() - t0
    print(f"    contradictions={len(contradictions)}  wall={contra_wall:.2f}s")

    # Serialise dates in flags
    for f in flags:
        for k, v in f.items():
            if hasattr(v, "isoformat"):
                f[k] = v.isoformat()

    for c in contradictions:
        for k, v in c.items():
            if hasattr(v, "isoformat"):
                c[k] = v.isoformat()

    fixture = {
        "patient_id": patient_id,
        "patient_name": meta["name"],
        "patient_dob": meta["dob"],
        "patient_nhs": meta["nhs"],
        "patient_sex": meta["sex"],
        "domain": meta["domain"],
        "generated_at": date.today().isoformat(),
        "performance": {
            "total_documents": len(documents),
            "total_entities": len(all_entities),
            "total_wall_seconds": round(t_total + flag_wall + contra_wall, 2),
            "per_doc_avg_seconds": round(t_total / len(documents), 2),
        },
        "documents": documents,
        "entities": all_entities,
        "observations": all_observations,
        "conditions": all_conditions,
        "medications": all_medications,
        "flags": flags,
        "contradictions": contradictions,
    }

    out_path = OUT_DIR / f"{patient_id}.json"
    out_path.write_text(
        json.dumps(fixture, indent=2, default=str),
        encoding="utf-8"
    )
    print(f"\n  [OK] {out_path} written ({out_path.stat().st_size} bytes)")
    print(f"       {len(flags)} flags, {len(contradictions)} contradictions")
    print(f"       total wall clock: {round(t_total + flag_wall + contra_wall, 2)}s")

print(f"\n{'='*60}")
print("Demo fixtures ready in demo/fixtures/")
print(f"{'='*60}")
