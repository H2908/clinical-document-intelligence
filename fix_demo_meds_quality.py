"""Fix two medication display issues:
1. Dose column empty - parse dose from drug name text
2. 'furosemide dose' artefact - filter out NER noise entries
"""
from pathlib import Path
import re

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# Helper to extract dose from drug name text
# Will be injected as a local function in the module

# Fix: update both medication list comprehensions to parse dose
# and filter out noise entries like "furosemide dose"

NOISE_SUFFIXES = {"dose", "therapy", "treatment", "use", "review", "clinic"}

old = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),
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

new = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": (lambda t: (re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)", t, re.I) or type("o",(),({"group":lambda s,*a:""})())()).group(0))(m.get("drug","")),
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
            and m.get("drug","").strip().lower().split()[-1] not in {"dose","therapy","treatment","use","review","clinic"}
            and len(m.get("drug","").strip().split()) < 6
        }.values()),'''

if old in src:
    src = src.replace(old, new, 1)
    print("[OK] get_patient medications: dose parsed, noise filtered")
else:
    # Try without the sorted() block (earlier version)
    old2 = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),
                "last_prescribed": m.get("document_date"),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in f.get("medications", [])
            if m.get("drug","").strip()
        }.values()),'''
    new2 = '''"medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": (lambda t: (re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)", t, re.I) or type("o",(),({"group":lambda s,*a:""})())()).group(0))(m.get("drug","")),
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
            and m.get("drug","").strip().lower().split()[-1] not in {"dose","therapy","treatment","use","review","clinic"}
            and len(m.get("drug","").strip().split()) < 6
        }.values()),'''
    if old2 in src:
        src = src.replace(old2, new2, 1)
        print("[OK] get_patient medications (v2): dose parsed, noise filtered")
    else:
        print("[FAIL] medications anchor not found in either form")
        # Show context for debugging
        idx = src.find('"medications": list({')
        print(f"Context at first 'medications list': {src[idx:idx+300]}")
        raise SystemExit(1)

# Also fix briefing medications
old_b = '''            "medications": list({
                m.get("drug","").strip().lower().split()[0]: {
                    "drug": m.get("drug", ""),
                    "dose": m.get("dose", ""),'''

new_b = '''            "medications": list({
                m.get("drug","").strip().lower().split()[0]: {
                    "drug": m.get("drug", "").strip(),
                    "dose": (lambda t: (re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)", t, re.I) or type("o",(),({"group":lambda s,*a:""})())()).group(0))(m.get("drug","")),'''

if old_b in src:
    src = src.replace(old_b, new_b, 1)
    print("[OK] get_briefing medications: dose parsed")
else:
    print("[SKIP] briefing medications anchor not found")

p.write_text(src, encoding="utf-8")
print("[OK] demo/api/main.py saved")