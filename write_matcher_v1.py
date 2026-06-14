"""Update _flag_key in evaluation/metrics.py to match on
(category, canonical(clinical_subject)) instead of (category, description).

This is the matcher gate for paper Day 5 / Task 6.
Atomic: aborts if anchor missing.
"""
from pathlib import Path

p = Path("evaluation/metrics.py")
src = p.read_text(encoding="utf-8")

old = '''def _flag_key(flag: dict) -> tuple[str, str]:
    """Canonical identity for a flag for set comparisons.

    Two flags are considered the same if they share (category, description).
    Severity / source_document_id deliberately excluded \u2014 the same clinical
    issue cited from a different doc is still the same flag.
    """
    return (
        flag.get("category", ""),
        flag.get("description", "").strip(),
    )'''

new = '''def _flag_key(flag: dict) -> tuple[str, str]:
    """Canonical identity for a flag for set comparisons.

    Identity = (category, canonical(clinical_subject)).
    canonical(s) = s.strip().lower().

    Two flags are the same iff they have the same category AND the same
    canonical clinical_subject. Severity, source_document_id,
    cited_document_id, and description are all deliberately excluded from
    identity:
      - severity is a label not an identity
      - {source,cited}_document_id can differ for the same clinical issue
        cited in different docs
      - description is paraphrasable; the whole point of clinical_subject
        as a first-class field is to make identity robust to paraphrase.

    Flags missing clinical_subject get an empty-string key. They will
    collapse together into a single "no-subject" bucket, which is the
    correct behaviour for the matcher (and an obvious diagnostic signal
    that the upstream is dropping the field).
    """
    return (
        (flag.get("category") or "").strip(),
        (flag.get("clinical_subject") or "").strip().lower(),
    )'''

if old not in src:
    print("[FAIL] anchor not found in evaluation/metrics.py - aborting")
    raise SystemExit(1)
if src.count(old) > 1:
    print(f"[FAIL] anchor matched {src.count(old)} times - aborting")
    raise SystemExit(1)

txt = src.replace(old, new)
p.write_text(txt, encoding="utf-8", newline="\n")
print(f"Wrote {p}")
print(f"Lines now: {len(txt.splitlines())}")
print(f"clinical_subject occurrences: {txt.count('clinical_subject')}")