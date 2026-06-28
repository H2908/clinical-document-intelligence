"""Fix the module-level skipif so fixture-sanity tests run regardless of
whether the matcher exists. The skip should apply only to tests that
import flags_have_same_identity or normalise_subject.
"""
from pathlib import Path

p = Path("tests/test_clinical_subject_matcher.py")
src = p.read_text(encoding="utf-8")

old = '''# Skip all tests if matcher hasn't been built yet (Step 6 not done)
pytestmark = pytest.mark.skipif(
    not MATCHER_AVAILABLE,
    reason="agents.clinical_subject_matcher not yet implemented (Step 6 pending).",
)'''

new = '''# Per-test skip marker for tests that need the matcher implementation.
# Fixture-sanity tests do NOT need this — they verify the JSON fixture itself
# and must run even before Step 6.
needs_matcher = pytest.mark.skipif(
    not MATCHER_AVAILABLE,
    reason="agents.clinical_subject_matcher not yet implemented (Step 6 pending).",
)'''

if "needs_matcher = pytest.mark.skipif" in src:
    print("[SKIP] already fixed")
elif old not in src:
    print("[FAIL] module-level skipif anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old, new)
    # Now apply needs_matcher to each test that uses the matcher
    decorations = [
        ('@pytest.mark.parametrize("case", _load_fixture()["must_stay_distinct"], ids=lambda c: c["id"])\ndef test_must_stay_distinct(case: dict) -> None:',
         '@needs_matcher\n@pytest.mark.parametrize("case", _load_fixture()["must_stay_distinct"], ids=lambda c: c["id"])\ndef test_must_stay_distinct(case: dict) -> None:'),
        ('@pytest.mark.parametrize("case", _load_fixture()["must_merge"], ids=lambda c: c["id"])\ndef test_must_merge(case: dict) -> None:',
         '@needs_matcher\n@pytest.mark.parametrize("case", _load_fixture()["must_merge"], ids=lambda c: c["id"])\ndef test_must_merge(case: dict) -> None:'),
        ('def test_normalise_subject(raw: str, expected: str) -> None:',
         None),  # special handling below
    ]
    for old_dec, new_dec in decorations[:2]:
        if old_dec not in src:
            print(f"[FAIL] could not find {old_dec[:60]}...")
            raise SystemExit(1)
        src = src.replace(old_dec, new_dec)

    # test_normalise_subject has a parametrize decorator already; insert @needs_matcher above it
    norm_anchor = '''@pytest.mark.parametrize("raw,expected", [
    ("Metformin", "metformin"),'''
    norm_new = '''@needs_matcher
@pytest.mark.parametrize("raw,expected", [
    ("Metformin", "metformin"),'''
    if norm_anchor not in src:
        print("[FAIL] could not find normalise_subject parametrize anchor")
        raise SystemExit(1)
    src = src.replace(norm_anchor, norm_new)

    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] skip scope fixed: matcher tests skip, fixture-sanity tests run")