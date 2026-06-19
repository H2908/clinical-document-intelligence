"""Replace 'Started' column with 'Last prescribed', drop 'Flag' column.

Production decision: 'Started' as a generic field is misleading. The
data we actually have is the latest document_date where this drug was
mentioned. Renaming to 'Last prescribed' and showing that date is
honest and clinically interpretable.

'Flag' column dropped entirely - surfacing fake per-medication warnings
is worse than no warnings. Future work: build a real per-medication
warning rules engine (drug+condition, drug+drug, dose+guideline,
monitoring schedule).

Three files touched:
  1. agents/briefing_agent.py - _extract_medications now tracks max
     document_date across all entities for each drug, returns
     last_prescribed_date on each medication dict.
  2. api/routes/patients.py - shaper defaults include 'last_prescribed'
     and 'source_document_id' instead of 'started' and 'flag'.
  3. frontend/app/patients/[id]/page.tsx - column header 'Started' ->
     'Last prescribed', data binding m.started -> m.last_prescribed,
     'Flag' column removed.
"""
from pathlib import Path
import re

# ============================================================================
# 1. agents/briefing_agent.py - track max document_date
# ============================================================================
p = Path("agents/briefing_agent.py")
src = p.read_text(encoding="utf-8")

old_func = '''def _extract_medications(entities: list[dict]) -> list[dict]:
    """
    Current medications = non-negated Drug entities, deduplicated by drug-name root.
    """
    seen: OrderedDict[str, dict] = OrderedDict()
    for e in entities:
        if e.get("entity_type") != "Drug":
            continue
        if e.get("negated"):
            continue
        text = (e.get("text") or "").strip()
        if not text or len(text) < 3:
            continue
        # Dedupe on first word (drug name root)
        key = text.split()[0].lower() if text.split() else ""
        if not key or key in seen:
            continue
        # Parse dose out of text: anything after the drug-name root word
        # is treated as dose+frequency (NER span extension captures it).
        dose_part = text[len(key):].strip() if text.lower().startswith(key) else ""
        seen[key] = {
            "drug": text.split()[0] if text.split() else text,
            "normalised": e.get("normalised_value"),
            "dose": dose_part if dose_part else None,
            "source_document_id": e["document_id"],
        }
    return list(seen.values())'''

new_func = '''def _extract_medications(entities: list[dict]) -> list[dict]:
    """
    Current medications = non-negated Drug entities, deduplicated by drug-name root.

    Per-drug aggregation rules:
      - drug name = display form from the LATEST entity (preserves casing)
      - dose = the dose extracted from the LATEST entity's text
      - last_prescribed_date = max document_date across all entities for
        this drug. Defensible interpretation: "most recent document where
        we have evidence of this prescription."
      - source_document_id = document_id of the latest entity
    """
    # First pass: bucket entities by drug-name root with their document_date
    buckets: OrderedDict[str, list[dict]] = OrderedDict()
    for e in entities:
        if e.get("entity_type") != "Drug":
            continue
        if e.get("negated"):
            continue
        text = (e.get("text") or "").strip()
        if not text or len(text) < 3:
            continue
        key = text.split()[0].lower() if text.split() else ""
        if not key:
            continue
        buckets.setdefault(key, []).append(e)

    # Second pass: collapse each bucket to its latest entity by document_date
    meds: list[dict] = []
    for key, bucket_entities in buckets.items():
        # Sort by document_date descending; None dates sort last
        bucket_entities.sort(
            key=lambda e: (e.get("document_date") or ""),
            reverse=True,
        )
        latest = bucket_entities[0]
        text = (latest.get("text") or "").strip()
        # Dose lives after the drug-name root in the entity text (NER
        # span extension captures it).
        dose_part = text[len(key):].strip() if text.lower().startswith(key) else ""
        # Stringify document_date - Snowflake may return date or datetime
        last_prescribed = latest.get("document_date")
        if last_prescribed is not None and not isinstance(last_prescribed, str):
            last_prescribed = str(last_prescribed)
        meds.append({
            "drug": text.split()[0] if text.split() else text,
            "normalised": latest.get("normalised_value"),
            "dose": dose_part if dose_part else None,
            "last_prescribed_date": last_prescribed,
            "source_document_id": latest["document_id"],
        })
    return meds'''

if "last_prescribed_date" in src:
    print("[SKIP] briefing_agent already has last_prescribed_date")
elif old_func not in src:
    print("[FAIL] _extract_medications anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_func, new_func)
    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] briefing_agent: medications now include last_prescribed_date")


# ============================================================================
# 2. api/routes/patients.py - update shaper defaults
# ============================================================================
p2 = Path("api/routes/patients.py")
src2 = p2.read_text(encoding="utf-8")

old_defaults = '''            m.setdefault("dose", None)
            m.setdefault("started", None)
            m.setdefault("flag", None)'''

new_defaults = '''            m.setdefault("dose", None)
            m.setdefault("last_prescribed", m.get("last_prescribed_date"))
            m.setdefault("source_document_id", m.get("source_document_id"))'''

if "last_prescribed" in src2 and "m.setdefault" in src2.split("medications")[1][:2000]:
    print("[SKIP] patients.py shaper already updated")
elif old_defaults not in src2:
    print("[FAIL] patients.py shaper anchor not found")
    raise SystemExit(1)
else:
    src2 = src2.replace(old_defaults, new_defaults)
    p2.write_text(src2, encoding="utf-8", newline="\n")
    print("[OK] patients.py: shaper exposes last_prescribed, drops started/flag")


# ============================================================================
# 3. frontend/app/patients/[id]/page.tsx - rename column, drop Flag
# ============================================================================
p3 = Path("frontend/app/patients/[id]/page.tsx")
src3 = p3.read_text(encoding="utf-8")

# 3a. Rename column header
old_header = '''                    <th className="px-5 py-2 text-left font-medium">Dose</th>
                    <th className="px-5 py-2 text-left font-medium">Started</th>
                    <th className="px-5 py-2 text-left font-medium">Flag</th>'''

new_header = '''                    <th className="px-5 py-2 text-left font-medium">Dose</th>
                    <th className="px-5 py-2 text-left font-medium">Last prescribed</th>'''

if "Last prescribed" in src3:
    print("[SKIP] frontend already has Last prescribed column")
elif old_header not in src3:
    print("[FAIL] frontend column header anchor not found")
    raise SystemExit(1)
else:
    src3 = src3.replace(old_header, new_header)
    print("[OK] frontend: column header renamed, Flag column removed")

# 3b. Update the table row rendering - drop the Flag cell, rename Started -> last_prescribed
# The Started + Flag cells are consecutive in the row; replace both.
old_cells = '''                      <td className="px-5 py-3 text-slate-500 text-xs font-mono">{m.started || "—"}</td>
                      <td className="px-5 py-3">
                        {m.flag ? (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                            <WarnIcon />
                            {m.flag}'''

# Match more flexibly because the closing JSX might wrap differently
old_cells_pattern = re.compile(
    r'<td className="px-5 py-3 text-slate-500 text-xs font-mono">\{m\.started \|\| "—"\}</td>\s*'
    r'<td className="px-5 py-3">\s*'
    r'\{m\.flag \?[^}]*\?[^}]*\}[^<]*</td>',
    re.DOTALL,
)
# That regex is tricky; use a simpler one targeting just the start and end markers
old_cells_simple = re.compile(
    r'<td className="px-5 py-3 text-slate-500 text-xs font-mono">\{m\.started \|\| "—"\}</td>.*?\{m\.flag[^}]*?\}\)\}\s*</td>',
    re.DOTALL,
)

new_cells = '<td className="px-5 py-3 text-slate-500 text-xs font-mono">{m.last_prescribed || "—"}</td>'

if 'm.last_prescribed' in src3:
    print("[SKIP] frontend cell already updated")
elif old_cells_simple.search(src3):
    src3 = old_cells_simple.sub(new_cells, src3)
    print("[OK] frontend: cells updated, Flag cell removed")
else:
    print("[WARN] cell-pattern regex didn't match; will need manual review")
    print("       Look at page.tsx around the medications table tr/td block")

p3.write_text(src3, encoding="utf-8", newline="\n")

# ============================================================================
# Also update frontend types if needed
# ============================================================================
p4 = Path("frontend/lib/api.ts")
src4 = p4.read_text(encoding="utf-8")

# Look for the Medication type definition
if "last_prescribed" in src4:
    print("[SKIP] api.ts already has last_prescribed in type")
else:
    # Find the Medication type. Try to add last_prescribed near started/flag.
    old_med_type = re.search(
        r'(\w+:\s*\{\s*[^}]*started\??\??:\s*string[^;]*;[^}]*flag\??\??:[^;]*;\s*\})',
        src4,
    )
    if old_med_type:
        # We found a Medication-like type with started + flag. Add
        # last_prescribed.
        replaced = old_med_type.group(1).replace(
            "started?:", "last_prescribed?: string | null;\n    source_document_id?: string | null;\n    started?:"
        ).replace(
            "started:", "last_prescribed?: string | null;\n    source_document_id?: string | null;\n    started?:"
        )
        if replaced != old_med_type.group(1):
            src4 = src4.replace(old_med_type.group(1), replaced)
            p4.write_text(src4, encoding="utf-8", newline="\n")
            print("[OK] api.ts: added last_prescribed + source_document_id to medication type")
        else:
            print("[INFO] api.ts: medication type found but couldn't auto-insert; manual review")
    else:
        print("[INFO] api.ts: no obvious medication type with started/flag; check by hand")

print()
print("=== Summary ===")
print("briefing_agent: last_prescribed_date computed as max document_date per drug")
print("patients.py shaper: surfaces last_prescribed and source_document_id; drops started/flag")
print("frontend page.tsx: column 'Started' -> 'Last prescribed', Flag column removed")
print("api.ts type: medication carries last_prescribed?: string | null")
print()
print("Re-process needed: cleanup_pat_test_01_entities.py to refresh MART with new field")