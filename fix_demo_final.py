from pathlib import Path

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# Fix 1: Diagnosis timeline - remove dedup, add document_date
old = '''    # Condition/Diagnosis events - one per unique condition
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
            })'''

new = '''    # Condition/Diagnosis events - one per condition per document (with date)
    for c in f.get("conditions", []):
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

if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Diagnosis timeline: document_date attached, dedup removed")
else:
    print("[FAIL] Diagnosis anchor not found")
    raise SystemExit(1)

# Fix 2: medications in get_patient - add last_prescribed
old_meds = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),'''

new_meds = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),
                "last_prescribed": m.get("document_date"),'''

count = src.count(old_meds)
if count >= 1:
    src = src.replace(old_meds, new_meds)
    print(f"[OK] medications: last_prescribed added ({count} locations)")
else:
    print("[FAIL] medications anchor not found")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("[OK] demo/api/main.py saved")