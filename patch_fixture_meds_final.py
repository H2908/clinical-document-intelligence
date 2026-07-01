"""Pre-compute correct deduplicated medications in fixture.
Each drug appears once with the LATEST document_date.
"""
import json, re
from pathlib import Path

NOISE = {"dose","therapy","treatment","use","review","clinic","started"}

def is_noise(drug):
    tokens = drug.strip().lower().split()
    return bool(tokens and tokens[-1] in NOISE) or len(tokens) > 5

def parse_dose(drug):
    m = re.search(r"\d+[\d.]*\s*(?:mg|mcg|g|ml|units?|iu)", drug, re.I)
    return m.group(0) if m else ""

def dedup_meds(meds):
    """Keep latest date per drug root."""
    best = {}
    for m in sorted(meds, key=lambda x: x.get("document_date") or "0000", reverse=True):
        drug = m.get("drug","").strip()
        if not drug or is_noise(drug):
            continue
        key = drug.lower().split()[0]
        if key not in best:
            best[key] = {
                "drug": drug,
                "dose": parse_dose(drug),
                "document_date": m.get("document_date",""),
                "started": m.get("started"),
                "flag_text": m.get("flag_text"),
                "normalised_value": m.get("normalised_value",""),
                "document_id": m.get("document_id",""),
            }
    return list(best.values())

for path in sorted(Path("demo/fixtures").glob("*.json")):
    f = json.loads(path.read_text(encoding="utf-8"))
    original = f.get("medications", [])
    f["medications_deduped"] = dedup_meds(original)
    path.write_text(json.dumps(f, indent=2, default=str), encoding="utf-8")
    print(f"[OK] {path.name}: {len(original)} raw -> {len(f['medications_deduped'])} deduped")
    for m in f["medications_deduped"]:
        print(f"     {m['drug']:<30} {m['dose']:<8} {m['document_date']}")