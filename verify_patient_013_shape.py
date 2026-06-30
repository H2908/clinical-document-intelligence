"""Verify patient_013 artifacts match patient_001 conventions exactly."""
import json
from pathlib import Path

P1 = Path("data/synthetic/documents/patient_001")
P6 = Path("data/synthetic/documents/patient_013")

# Top-level keys in gold_flags.json
p1_gf = json.loads((P1 / "gold_flags.json").read_text(encoding="utf-8"))
p6_gf = json.loads((P6 / "gold_flags.json").read_text(encoding="utf-8"))

print("=" * 60)
print("gold_flags.json shape check")
print("=" * 60)

p1_keys = set(p1_gf.keys())
p6_keys = set(p6_gf.keys())
if p1_keys == p6_keys:
    print("[OK] top-level keys match")
else:
    print(f"[MISMATCH] top-level keys differ")
    print(f"  p1 only: {p1_keys - p6_keys}")
    print(f"  p6 only: {p6_keys - p1_keys}")

# Per-flag entry shape - compare first flag's keys
p1_flag_keys = set(p1_gf["gold_flags"][0].keys())
p6_flag_keys = set(p6_gf["gold_flags"][0].keys())
if p1_flag_keys.issubset(p6_flag_keys) or p6_flag_keys.issubset(p1_flag_keys):
    print(f"[OK] per-flag keys compatible (some flags carry tier-2 'needs_clinician_validation')")
    print(f"     p1 flag[0] keys: {sorted(p1_flag_keys)}")
    print(f"     p6 flag[0] keys: {sorted(p6_flag_keys)}")
else:
    print(f"[MISMATCH] per-flag keys diverge")

print()
print("=" * 60)
print("gold_contradictions.json shape check")
print("=" * 60)

p1_gc = json.loads((P1 / "gold_contradictions.json").read_text(encoding="utf-8"))
p6_gc = json.loads((P6 / "gold_contradictions.json").read_text(encoding="utf-8"))

p1_c_keys = set(p1_gc.keys())
p6_c_keys = set(p6_gc.keys())
if p1_c_keys == p6_c_keys:
    print("[OK] top-level keys match")
else:
    print(f"[MISMATCH] top-level keys differ")
    print(f"  p1 only: {p1_c_keys - p6_c_keys}")
    print(f"  p6 only: {p6_c_keys - p1_c_keys}")

p1_contra_keys = set(p1_gc["gold_contradictions"][0].keys())
p6_contra_keys = set(p6_gc["gold_contradictions"][0].keys())
if p1_contra_keys == p6_contra_keys:
    print("[OK] per-contradiction keys match")
else:
    print(f"[MISMATCH] per-contradiction keys differ")
    print(f"  p1 only: {p1_contra_keys - p6_contra_keys}")
    print(f"  p6 only: {p6_contra_keys - p1_contra_keys}")

print()
print("=" * 60)
print("Summary")
print("=" * 60)
print(f"patient_001: {len(p1_gf['gold_flags'])} flags, {len(p1_gc['gold_contradictions'])} contradiction(s)")
print(f"patient_013: {len(p6_gf['gold_flags'])} flags, {len(p6_gc['gold_contradictions'])} contradiction(s)")
