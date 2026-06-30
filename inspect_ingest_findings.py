"""Inspect what the pipeline actually extracted from the 15 synthetic docs.
Shows entities by type, conditions, medications, and observations per patient.
"""
from worker.document_processor import process_document
from datetime import date
from pathlib import Path
from collections import defaultdict

PATIENTS = {
    "patient_001": [
        ("01_GP_Referral_Thompson_12Jan2024.pdf",     date(2024, 1, 12), "gp_referral"),
        ("02_Cardiology_Thompson_28Feb2024.pdf",      date(2024, 2, 28), "clinic_letter"),
        ("03_AE_Discharge_Thompson_04Apr2024.pdf",    date(2024, 4,  4), "discharge_summary"),
    ],
    "patient_006": [
        ("01_GP_Diabetes_Review_Patel_14Nov2023.pdf",     date(2023, 11, 14), "gp_referral"),
        ("02_Diabetes_Clinic_Patel_09Feb2024.pdf",        date(2024,  2,  9), "clinic_letter"),
        ("03_GP_Hypertension_Review_Patel_18Jun2024.pdf", date(2024,  6, 18), "gp_referral"),
    ],
    "patient_009": [
        ("01_GP_Asthma_Review_Bennett_11Mar2024.pdf",     date(2024,  3, 11), "gp_referral"),
        ("02_Respiratory_Clinic_Bennett_22Aug2024.pdf",   date(2024,  8, 22), "clinic_letter"),
        ("03_AE_Discharge_Bennett_09Nov2024.pdf",         date(2024, 11,  9), "discharge_summary"),
    ],
    "patient_013": [
        ("01_GP_CKD_Review_Walsh_16Jan2024.pdf",          date(2024,  1, 16), "gp_referral"),
        ("02_Renal_Clinic_Walsh_14May2024.pdf",           date(2024,  5, 14), "clinic_letter"),
        ("03_GP_Locum_Walsh_22Oct2024.pdf",               date(2024, 10, 22), "gp_referral"),
    ],
}

BASE = Path("data/synthetic/documents")

for patient_id, docs in PATIENTS.items():
    print(f"\n{'='*60}")
    print(f"PATIENT: {patient_id}")
    print(f"{'='*60}")

    all_conditions = defaultdict(set)
    all_medications = defaultdict(set)
    all_conflicts = []

    for filename, doc_date, doc_type in docs:
        result = process_document(
            file_path=BASE / patient_id / filename,
            document_id=f"{patient_id}_{Path(filename).stem}",
            patient_id=patient_id,
            document_date=doc_date,
            doc_type=doc_type,
        )

        print(f"\n  Doc: {filename}")
        print(f"  Date: {doc_date}  Type: {doc_type}")

        # Conditions
        conds = result.get("conditions", [])
        if conds:
            for c in conds:
                text = c.get("text") or c.get("normalised_value") or ""
                all_conditions[text].add(filename[:6])
            print(f"  Conditions ({len(conds)}): {[c.get('text','?')[:40] for c in conds]}")

        # Medications
        meds = result.get("medications", [])
        if meds:
            for m in meds:
                text = m.get("text") or m.get("normalised_value") or ""
                all_medications[text].add(filename[:6])
            print(f"  Medications ({len(meds)}): {[m.get('text','?')[:30] for m in meds]}")

        # Observations (labs)
        obs = result.get("observations", [])
        if obs:
            print(f"  Observations ({len(obs)}): {[o.get('text','?')[:30] for o in obs]}")

        # Conflicts (allergy entities)
        entities = result.get("entities", [])
        conflicts = [e for e in entities if e.get("entity_type") == "Conflict"]
        if conflicts:
            all_conflicts.extend(conflicts)
            print(f"  Conflicts ({len(conflicts)}): {[c.get('text','?')[:40] for c in conflicts]}")

    # Cross-doc summary
    print(f"\n  --- Cross-doc summary for {patient_id} ---")
    print(f"  Unique conditions seen: {sorted(all_conditions.keys())}")
    print(f"  Unique medications seen: {sorted(all_medications.keys())}")
    if all_conflicts:
        print(f"  Conflict entities: {[c.get('text','?') for c in all_conflicts]}")
    else:
        print(f"  Conflict entities: none detected")