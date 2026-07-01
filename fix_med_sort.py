from pathlib import Path
import re

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# The issue: dict comprehension keeps FIRST seen key, so we need to
# pre-sort descending by date so latest appears first and wins the dedup

old = '''            for m in sorted(
                f.get("medications", []),
                key=lambda x: x.get("document_date") or "",
                reverse=True,
            )
            if m.get("drug","").strip()
            and not _is_noise_med(m.get("drug", ""))'''

new = '''            for m in sorted(
                f.get("medications", []),
                key=lambda x: x.get("document_date") or "0000-00-00",
                reverse=True,
            )
            if m.get("drug","").strip()
            and not _is_noise_med(m.get("drug", ""))'''

# Also need to replace the non-sorted version if it exists
old2 = '''            for m in f.get("medications", [])
            if m.get("drug","").strip()
            and not _is_noise_med(m.get("drug", ""))'''

new2 = '''            for m in sorted(
                f.get("medications", []),
                key=lambda x: x.get("document_date") or "0000-00-00",
                reverse=True,
            )
            if m.get("drug","").strip()
            and not _is_noise_med(m.get("drug", ""))'''

changed = False
if old in src:
    src = src.replace(old, new)
    changed = True
    print("[OK] sorted() already present - fixed sort key")
if old2 in src:
    src = src.replace(old2, new2)
    changed = True
    print("[OK] added sorted() descending by document_date")

if not changed:
    print("[FAIL] neither anchor found")
    # Show context
    idx = src.find("_is_noise_med")
    print(src[max(0,idx-200):idx+200])
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("[OK] saved - uvicorn --reload will pick up")