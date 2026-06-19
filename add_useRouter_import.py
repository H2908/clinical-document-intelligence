"""Add the missing useRouter import to page.tsx.

The previous patch reported success but didn't actually add the import.
The browser shows 'useRouter is not defined' at runtime.

Single anchored edit: add the next/navigation import line right after
the React import.
"""
from pathlib import Path

p = Path("frontend/app/page.tsx")
src = p.read_text(encoding="utf-8")

if 'from "next/navigation"' in src and "useRouter" in src.split("\n", 5)[1:5][1]:
    print("[SKIP] useRouter already imported at top of file")
    raise SystemExit(0)

old = 'import { useEffect, useState } from "react";\nimport Link from "next/link";'
new = 'import { useEffect, useState } from "react";\nimport Link from "next/link";\nimport { useRouter } from "next/navigation";'

if old not in src:
    print("[FAIL] anchor not found - check the first few lines of page.tsx")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("[OK] useRouter imported from next/navigation")
print()
print("First 6 lines of page.tsx now:")
print()
for i, line in enumerate(src.splitlines()[:6], 1):
    print(f"  {i}: {line}")