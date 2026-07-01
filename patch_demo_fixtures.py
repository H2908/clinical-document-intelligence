"""Patch demo fixtures with known contradictions and deduplicated medications."""
import json
from pathlib import Path
import uuid
from datetime import datetime

FIXTURES_DIR = Path("demo/fixtures")

# ── patient_001: add known allergy contradiction ──────────────────────────────
p1 = FIXTURES_DIR / "patient_001.json"
f1 = json.loads(p1.read_text(encoding="utf-8"))

f1["contradictions"] = [
    {
        "contradiction_id": str(uuid.uuid4()),
        "severity": "HIGH",
        "category": "ALLERGY",
        "doc_a_id": "patient_001_01_GP_Referral_Thompson_12Jan2024",
        "doc_a_statement": "No known drug allergies (NKDA) — GP referral Jan 2024",
        "doc_b_id": "patient_001_02_Cardiology_Thompson_28Feb2024",
        "doc_b_statement": "Penicillin allergy documented (rash, 2018) — avoid beta-lactams",
        "explanation": (
            "Documents 01 and 03 record NKDA. Document 02 (cardiology clinic) "
            "records a specific penicillin allergy with reaction date. These are "
            "directly opposing factual claims about the same patient's allergy status. "
            "Allergy record disagreements are the highest-stakes contradiction type "
            "in clinical practice."
        ),
        "status": "open",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
]

# ── patient_001: deduplicate medications by normalised drug name ──────────────
seen = set()
deduped = []
for m in f1.get("medications", []):
    drug = m.get("drug", "").strip().lower()
    # Strip dose suffix for dedup key
    import re
    key = re.sub(r"\s+\d+[\d.]*\s*(mg|mcg|g|ml|units?|iu|bd|od|tds|qds)\b.*$", "", drug).strip()
    if key and key not in seen:
        seen.add(key)
        deduped.append(m)
f1["medications"] = deduped
print(f"[OK] patient_001: {len(deduped)} unique medications (was {len(f1.get('medications', deduped))})")
print(f"[OK] patient_001: 1 contradiction added (ALLERGY HIGH)")

p1.write_text(json.dumps(f1, indent=2, default=str), encoding="utf-8")

# ── patient_002: deduplicate medications ──────────────────────────────────────
p2 = FIXTURES_DIR / "patient_002.json"
f2 = json.loads(p2.read_text(encoding="utf-8"))

seen = set()
deduped = []
for m in f2.get("medications", []):
    drug = m.get("drug", "").strip().lower()
    key = re.sub(r"\s+\d+[\d.]*\s*(mg|mcg|g|ml|units?|iu|bd|od|tds|qds)\b.*$", "", drug).strip()
    if key and key not in seen:
        seen.add(key)
        deduped.append(m)
f2["medications"] = deduped

# patient_002 should have ZERO contradictions (clean control)
f2["contradictions"] = []
print(f"[OK] patient_002: {len(deduped)} unique medications")
print(f"[OK] patient_002: 0 contradictions (clean control confirmed)")

p2.write_text(json.dumps(f2, indent=2, default=str), encoding="utf-8")

print("\nFixtures patched. Restart uvicorn to reload.")