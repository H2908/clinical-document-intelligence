"""Step 6-and-7 combined: upgrade evaluation/metrics._flag_key to
spec-compliant Path B matcher, then rewire the test file to use it.

Path B (per spec sec 5-6) extends the previous strip().lower() matcher with:
  - Abbreviation table: ACEi <-> ACE inhibitor, eGFR <-> estimated
    glomerular filtration rate, HbA1c <-> glycated haemoglobin, etc.
    Curated, conservative: unlisted pairs do NOT merge.
  - Dose-suffix stripping for drug-type subjects: "Furosemide 80 mg"
    -> "furosemide". The regex requires a unit token (mg/mcg/g/ml/
    units/iu) so measurement subjects like "eGFR 32" or "LVEF 28%"
    are naturally NOT stripped - they lack a unit token.

Why this matters:
  - Without abbreviation handling, the matcher counts ACEi and "ACE
    inhibitor" as distinct identities. Clinical text uses both
    constantly; this inflates the distinct-flag count and undercounts
    reproducibility.
  - Without dose-stripping, "Furosemide" and "Furosemide 80 mg" appear
    as distinct subjects even though they refer to the same drug. Rule
    layer emits the bare drug name; LLM layer emits whatever's in text.

Guardrail: v1.3 grounding instrument untouched. This is a matcher
extension only - no prompts, no validation logic, no severity rubric
changes here. canonical(s) was strip+lower; now it is normalise_subject(s).

Two file edits below.
"""
from pathlib import Path
import re

# ============================================================================
# 1. evaluation/metrics.py - add normalise_subject() + update _flag_key
# ============================================================================
p = Path("evaluation/metrics.py")
src = p.read_text(encoding="utf-8")

# 1a. Insert normalise_subject() helper near the top of the file, right
# after the imports. Use a marker we know is at file-top.
helper_block = '''

# ---------------------------------------------------------------------------
# Clinical subject normalisation (spec sec 5-6)
# ---------------------------------------------------------------------------

# Curated abbreviation table. Maps spelled-out form -> canonical abbreviation.
# Conservative: unlisted pairs do NOT merge. Add to this table only when a
# pair appears in clinical text often enough to cause distinct-flag inflation.
_ABBREVIATION_TABLE = {
    "ace inhibitor":                          "acei",
    "ace inhibitors":                         "acei",
    "estimated glomerular filtration rate":   "egfr",
    "glycated haemoglobin":                   "hba1c",
    "glycated hemoglobin":                    "hba1c",
    "left ventricular ejection fraction":     "lvef",
    "b-type natriuretic peptide":             "bnp",
    "n-terminal pro-bnp":                     "nt-probnp",
}

# Dose-suffix regex. Requires a unit token, so measurement subjects like
# "eGFR 32" or "LVEF 28%" (no unit) are naturally NOT stripped. Drug
# subjects "Furosemide 80 mg" / "Spironolactone 25 mg OD" are stripped
# to the bare drug name.
_DOSE_SUFFIX_RE = re.compile(
    r"\\s+\\d+[\\d.]*\\s*(mg|mcg|g|ml|units?|iu)\\b.*$",
    flags=re.IGNORECASE,
)


def normalise_subject(subject: str) -> str:
    """Normalise clinical_subject for identity comparison (spec sec 6).

    Pipeline:
      1. lowercase
      2. strip leading/trailing whitespace
      3. collapse internal whitespace
      4. apply abbreviation table (full form -> canonical abbreviation)
      5. strip dose suffix (drug-type subjects only, discriminated by unit)

    Returns the normalised string used for matcher comparison.
    Empty / None / whitespace-only inputs return empty string.
    """
    if not subject:
        return ""
    s = subject.lower().strip()
    s = re.sub(r"\\s+", " ", s)
    s = _ABBREVIATION_TABLE.get(s, s)
    s = _DOSE_SUFFIX_RE.sub("", s).strip()
    return s


'''

# Anchor on the import block end - find the last import-like line near the top.
# Look for the existing module-level definitions to insert before them.
anchor_for_helper = "def _flag_key(flag: dict) -> tuple[str, str]:"

if "def normalise_subject" in src:
    print("[SKIP] normalise_subject() already defined")
else:
    if anchor_for_helper not in src:
        print(f"[FAIL] could not find anchor: {anchor_for_helper!r}")
        raise SystemExit(1)
    src = src.replace(anchor_for_helper, helper_block + anchor_for_helper, 1)
    print("[OK] normalise_subject() helper added to evaluation/metrics.py")

# 1b. Update _flag_key to call normalise_subject
old_flag_key_body = '''    return (
        (flag.get("category") or "").strip(),
        (flag.get("clinical_subject") or "").strip().lower(),
    )'''

new_flag_key_body = '''    return (
        (flag.get("category") or "").strip(),
        normalise_subject(flag.get("clinical_subject") or ""),
    )'''

if "normalise_subject(flag.get" in src:
    print("[SKIP] _flag_key already uses normalise_subject")
elif old_flag_key_body not in src:
    print("[FAIL] _flag_key body anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_flag_key_body, new_flag_key_body, 1)
    print("[OK] _flag_key now uses normalise_subject (was strip+lower)")

# 1c. Also need `import re` at the top if not already there
if "import re" not in src.split("def normalise_subject")[0]:
    # Insert at the very top before everything else
    if src.startswith('"""'):
        # module docstring - insert after it
        end_doc = src.find('"""', 3) + 3
        src = src[:end_doc] + "\nimport re" + src[end_doc:]
    else:
        src = "import re\n" + src
    print("[OK] import re added to evaluation/metrics.py")

p.write_text(src, encoding="utf-8", newline="\n")


# ============================================================================
# 2. tests/test_clinical_subject_matcher.py - rewire to real matcher
# ============================================================================
p2 = Path("tests/test_clinical_subject_matcher.py")
src2 = p2.read_text(encoding="utf-8")

old_import = '''# Import target - does not exist yet (Step 6 will create it)
# pytest will report ImportError until then; that is the expected red state.
try:
    from agents.clinical_subject_matcher import flags_have_same_identity, normalise_subject
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False'''

new_import = '''# The matcher lives in evaluation/metrics.py as _flag_key (tuple identity)
# and normalise_subject. We bridge flags_have_same_identity as a tuple
# equality wrapper so the test file reads naturally.
try:
    from evaluation.metrics import _flag_key, normalise_subject

    def flags_have_same_identity(flag_a: dict, flag_b: dict) -> bool:
        """Bridge: two flags share identity iff their _flag_key tuples match."""
        return _flag_key(flag_a) == _flag_key(flag_b)

    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False'''

if "from evaluation.metrics import _flag_key" in src2:
    print("[SKIP] test file already wired to evaluation/metrics")
elif old_import not in src2:
    print("[FAIL] test file import anchor not found")
    raise SystemExit(1)
else:
    src2 = src2.replace(old_import, new_import, 1)
    p2.write_text(src2, encoding="utf-8", newline="\n")
    print("[OK] test file rewired to evaluation.metrics._flag_key + normalise_subject")


print()
print("=== Summary ===")
print("evaluation/metrics.py:")
print("  - normalise_subject() helper added (spec sec 6)")
print("  - _flag_key() now uses normalise_subject (was strip+lower)")
print("  - Abbreviation table + dose-suffix stripping wired in")
print()
print("tests/test_clinical_subject_matcher.py:")
print("  - Imports rewired to real matcher in evaluation/metrics")
print("  - flags_have_same_identity bridged as tuple equality wrapper")
print()
print("Guardrail: v1.3 grounding instrument untouched.")
print()
print("Next: pytest tests/test_clinical_subject_matcher.py -v")
print("Expect: 8 case tests + 19 normalisation tests + 3 fixture sanity = 30 passed")