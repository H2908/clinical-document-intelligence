from pathlib import Path

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# Replace all occurrences of medications list comprehension with simple deduped lookup
old_pattern = '''        "medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": _parse_dose(m.get("drug", "")),
                "last_prescribed": m.get("document_date"),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in sorted(
                [x for x in f.get("medications", [])
                 if x.get("drug","").strip() and not _is_noise_med(x.get("drug",""))],
                key=lambda x: x.get("document_date") or "0000-00-00",
                reverse=True,
            )
        }.values()),'''

new_pattern = '''        "medications": [
            {
                "drug": m.get("drug", ""),
                "dose": m.get("dose", ""),
                "last_prescribed": m.get("document_date", ""),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in f.get("medications_deduped", f.get("medications", []))
        ],'''

old_briefing = '''                for m in sorted(
                    [x for x in f.get("medications", [])
                     if x.get("drug","").strip() and not _is_noise_med(x.get("drug",""))],
                    key=lambda x: x.get("document_date") or "0000-00-00",
                    reverse=True,
                )
            }.values()),'''

new_briefing = '''                for m in f.get("medications_deduped", f.get("medications", []))
            ],'''

old_briefing_start = '''            "medications": list({
                m.get("drug","").strip().lower().split()[0]: {
                    "drug": m.get("drug", "").strip(),
                    "dose": _parse_dose(m.get("drug", "")),
                    "last_prescribed": m.get("document_date"),
                    "started": m.get("started"),
                    "flag": m.get("flag_text"),
                    "normalised": m.get("normalised_value", ""),
                }'''

new_briefing_start = '''            "medications": [
                {
                    "drug": m.get("drug", ""),
                    "dose": m.get("dose", ""),
                    "last_prescribed": m.get("document_date", ""),
                    "started": m.get("started"),
                    "flag": m.get("flag_text"),
                    "normalised": m.get("normalised_value", ""),
                }'''

count1 = src.count(old_pattern)
if count1:
    src = src.replace(old_pattern, new_pattern)
    print(f"[OK] get_patient medications: now uses medications_deduped ({count1}x)")
else:
    print("[SKIP] get_patient pattern not found")

# Fix briefing in two parts
if old_briefing_start in src and old_briefing in src:
    src = src.replace(old_briefing_start, new_briefing_start)
    src = src.replace(old_briefing, new_briefing)
    print("[OK] get_briefing medications: now uses medications_deduped")
else:
    print("[SKIP] briefing pattern not found - checking counts:",
          src.count(old_briefing_start), src.count(old_briefing))

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("[OK] saved")