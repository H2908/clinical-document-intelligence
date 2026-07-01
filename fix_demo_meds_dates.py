"""Fix medications to show document_date as last_prescribed,
and timeline to use document_date on Diagnosis/Medication events."""
from pathlib import Path
import re

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# Fix medications in get_patient - show all per-doc entries with last_prescribed
old = '''        "medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": (re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)(?:\\s+\\w+)?", m.get("drug",""), re.I) or type("", (), {"group": lambda self, *a: ""}())()).group(0),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in f.get("medications", [])
            if m.get("drug","").strip()
        }.values()),'''

new = '''        "medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": m.get("dose") or "",
                "last_prescribed": m.get("document_date"),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in sorted(
                f.get("medications", []),
                key=lambda x: x.get("document_date") or "",
                reverse=True,
            )
            if m.get("drug","").strip()
        }.values()),'''

if old in src:
    src = src.replace(old, new, 1)
    print("[OK] get_patient medications: last_prescribed from document_date")
else:
    print("[SKIP] get_patient meds anchor not found - may already be updated")

# Fix timeline Diagnosis events to use document_date
old_diag = '''        seen_conds = set()
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
            })'''

new_diag = '''    for c in f.get("conditions", []):
        name = c.get("name", "").strip()
        if name:
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": c.get("document_date"),
                "event_type": "Diagnosis",
                "title": name,
                "icd10_code": c.get("icd10_code"),
                "source_document_id": c.get("document_id", ""),
                "created_at": datetime.utcnow().isoformat() + "Z",
            })'''

if old_diag in src:
    src = src.replace(old_diag, new_diag, 1)
    print("[OK] timeline Diagnosis: document_date attached")
else:
    print("[SKIP] Diagnosis anchor not found")

# Fix timeline Medication events to use document_date
old_med = '''    seen_meds = set()
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
            })'''

new_med = '''    for m in f.get("medications", []):
        drug = m.get("drug", "").strip()
        if drug:
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_date": m.get("document_date"),
                "event_type": "Medication",
                "title": drug,
                "icd10_code": None,
                "source_document_id": m.get("document_id", ""),
                "created_at": datetime.utcnow().isoformat() + "Z",
            })'''

if old_med in src:
    src = src.replace(old_med, new_med, 1)
    print("[OK] timeline Medication: document_date attached")
else:
    print("[SKIP] Medication anchor not found")

p.write_text(src, encoding="utf-8")
print("[OK] demo/api/main.py saved")