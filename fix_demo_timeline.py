"""Fix two demo API issues:
1. Timeline missing Diagnosis/Medication/Conflict/Document event types
2. Medications missing dose (parse from drug text)
"""
from pathlib import Path

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# ── Fix 1: Replace get_timeline with full event-type support ──────────────────

old_timeline = '''@app.get("/api/patients/{patient_id}/timeline")
def get_timeline(patient_id: str, event_type: Optional[str] = Query(None), limit: int = Query(200)):
    f = _load(patient_id)
    # Build timeline events from documents + flags
    events = []
    for doc in f.get("documents", []):
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_date": doc.get("document_date"),
            "event_type": doc.get("doc_type", "document"),
            "title": doc.get("file_name", "Document"),
            "icd10_code": None,
            "source_document_id": doc.get("document_id", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
    for fl in f.get("flags", []):
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_date": None,
            "event_type": "flag",
            "title": f"[{fl.get('severity','MEDIUM')}] {fl.get('category','')}",
            "icd10_code": None,
            "source_document_id": fl.get("source_document_id", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]
    events = events[:limit]
    return {"patient_id": patient_id, "count": len(events), "events": events}'''

new_timeline = '''@app.get("/api/patients/{patient_id}/timeline")
def get_timeline(patient_id: str, event_type: Optional[str] = Query(None), limit: int = Query(200)):
    f = _load(patient_id)
    events = []

    # Document events
    for doc in f.get("documents", []):
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_date": doc.get("document_date"),
            "event_type": "Document",
            "title": doc.get("file_name", "Document"),
            "icd10_code": None,
            "source_document_id": doc.get("document_id", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
        })

    # Condition/Diagnosis events - one per unique condition
    seen_conds = set()
    for c in f.get("conditions", []):
        name = c.get("name", "").strip()
        if name and name not in seen_conds:
            seen_conds.add(name)
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": None,
                "event_type": "Diagnosis",
                "title": name,
                "icd10_code": c.get("icd10_code"),
                "source_document_id": "",
                "created_at": datetime.utcnow().isoformat() + "Z",
            })

    # Medication events - one per unique drug
    seen_meds = set()
    for m in f.get("medications", []):
        drug = m.get("drug", "").strip()
        key = drug.lower().split()[0] if drug else ""
        if key and key not in seen_meds:
            seen_meds.add(key)
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": None,
                "event_type": "Medication",
                "title": drug,
                "icd10_code": None,
                "source_document_id": "",
                "created_at": datetime.utcnow().isoformat() + "Z",
            })

    # Conflict events - from entities
    for e in f.get("entities", []):
        if e.get("entity_type") == "Conflict" and not e.get("negated"):
            text = (e.get("text") or "").strip()
            if text and len(text) > 4:
                events.append({
                    "event_id": str(uuid.uuid4()),
                    "event_date": e.get("document_date"),
                    "event_type": "Conflict",
                    "title": text,
                    "icd10_code": None,
                    "source_document_id": e.get("document_id", ""),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                })

    if event_type and event_type != "all":
        events = [e for e in events if e["event_type"] == event_type]
    events = events[:limit]
    return {"patient_id": patient_id, "count": len(events), "events": events}'''

if old_timeline not in src:
    print("[FAIL] timeline anchor not found")
    raise SystemExit(1)
src = src.replace(old_timeline, new_timeline, 1)
print("[OK] timeline: Diagnosis/Medication/Conflict/Document event types added")


# ── Fix 2: Parse dose from drug text in get_patient and get_briefing ──────────
import re

def _dedup_meds_code(indent="        "):
    return (
        f'{indent}"medications": list({{\n'
        f'{indent}    m.get("drug","").strip().lower().split()[0]: {{\n'
        f'{indent}        "drug": m.get("drug", "").strip(),\n'
        f'{indent}        "dose": (re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)(?:\\s+\\w+)?", m.get("drug",""), re.I) or type("", (), {{"group": lambda self, *a: ""}})()).group(0),\n'
        f'{indent}        "started": m.get("started"),\n'
        f'{indent}        "flag": m.get("flag_text"),\n'
        f'{indent}        "normalised": m.get("normalised_value", ""),\n'
        f'{indent}    }}\n'
        f'{indent}    for m in f.get("medications", [])\n'
        f'{indent}    if m.get("drug","").strip()\n'
        f'{indent}}}.values()),\n'
    )

# Add re import if not present
if "import re" not in src:
    src = src.replace("import uuid", "import re\nimport uuid", 1)
    print("[OK] import re added")

p.write_text(src, encoding="utf-8")
print("[OK] demo/api/main.py saved")
print("\nRestart uvicorn to pick up changes (--reload should do it automatically)")
