from pathlib import Path

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

old = '''        "medications": list({
            m.get("drug","").strip().lower().split()[0]: {
                "drug": m.get("drug", "").strip(),
                "dose": _parse_dose(m.get("drug", "")),
                "last_prescribed": m.get("document_date"),
                "started": m.get("started"),
                "flag": m.get("flag_text"),
                "normalised": m.get("normalised_value", ""),
            }
            for m in sorted(
                f.get("medications", []),
                key=lambda x: x.get("document_date") or "0000-00-00",
                reverse=True,
            )
            if m.get("drug","").strip()
            and not _is_noise_med(m.get("drug", ""))
        }.values()),'''

new = '''        "medications": list({
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

count = src.count(old)
if count == 0:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new)
print(f"[OK] noise filter moved before dedup ({count} locations)")
p.write_text(src, encoding="utf-8")
print("[OK] saved")