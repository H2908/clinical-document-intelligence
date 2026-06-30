"""Fix extracted_text check in ingest_synthetic_patients.py.
The field lives at result['document']['extracted_text'], not result['extracted_text'].
"""
from pathlib import Path

p = Path("ingest_synthetic_patients.py")
src = p.read_text(encoding="utf-8")

old = 'has_text = bool(result.get("extracted_text", "").strip())'
new = 'has_text = bool((result.get("document") or {}).get("extracted_text", "").strip())'

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("[OK] extracted_text check fixed")