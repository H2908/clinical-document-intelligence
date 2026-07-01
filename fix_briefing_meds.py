from pathlib import Path

p = Path("demo/api/main.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# Find the briefing medications section (the one without sorted())
# Look for the specific pattern in briefing
target_start = None
for i, line in enumerate(lines):
    if '"medications": list({' in line and target_start is None:
        # Check if this is the briefing one (no sorted() in next few lines)
        context = "".join(lines[i:i+15])
        if "for m in f.get" in context and "sorted" not in context:
            target_start = i
            break

if target_start is None:
    print("[FAIL] briefing medications block not found")
    raise SystemExit(1)

# Find the end of this block
target_end = None
for i in range(target_start, target_start + 20):
    if "}.values())," in lines[i]:
        target_end = i
        break

if target_end is None:
    print("[FAIL] end of briefing medications block not found")
    raise SystemExit(1)

print(f"[OK] found briefing medications at lines {target_start+1}-{target_end+1}")
print("Current block:")
for i in range(target_start, target_end+1):
    print(f"  {i+1}: {lines[i]}", end="")

replacement = '''            "medications": list({
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
            }.values()),
'''

lines = lines[:target_start] + [replacement] + lines[target_end+1:]
result = "".join(lines)

import ast
try:
    ast.parse(result)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

p.write_text(result, encoding="utf-8")
print("[OK] briefing medications fixed - sorted descending by date, noise filtered")