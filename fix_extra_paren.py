"""One-char fix: remove the trailing extra ')' on the patient block
in snowflake_writer.write_briefing.

The regex-based fix in fix_ner_substring_and_patient_block.py left an
unmatched ')' because the original pattern captured an opening { but
the closing } of that dict slipped into the replacement.
"""
from pathlib import Path

p = Path("database/snowflake_writer.py")
src = p.read_text(encoding="utf-8")

old = '"patient": briefing.get("patient") or _fetch_patient_block(patient_id)),'
new = '"patient": briefing.get("patient") or _fetch_patient_block(patient_id),'

if old not in src:
    if new in src:
        print("[SKIP] already fixed")
        raise SystemExit(0)
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] extra ')' removed from patient block")