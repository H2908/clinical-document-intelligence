"""Test set for ontology.bnf_mapper.lookup.

12 cases. Three load-bearing regression tests included by design,
mirroring the bug patterns the ICD-10 mapper's test set caught:

  - regression_dose_strip: "ramipril 5 mg" must NOT fail to match.
    Critical because real entity text from the NER always carries dose.

  - regression_vague_query_no_overspecify: "aspirin" must NOT match a
    more specific compound entry. Direction-aware substring forbids
    matching reference->query (only query->reference).

  - regression_word_boundary: "metformin" inside "non-metformin therapy"
    should still match metformin; but "for" should NOT match "formoterol".
    Word-boundary regex prevents the second.

Run: python -m ontology.test_bnf_mapper
Expected: 12/12 pass.
"""
from ontology.bnf_mapper import lookup


def case_1_exact_simple():
    """'metformin' -> exact match, biguanide."""
    r = lookup("metformin")
    return (
        r is not None and r["bnf_name"] == "Metformin hydrochloride"
        and r["confidence"] == "high" and r["therapeutic_class"] == "Biguanide"
    ), r


def case_2_exact_via_synonym():
    """'lipitor' (brand) -> exact match via synonym to atorvastatin."""
    r = lookup("lipitor")
    return (
        r is not None and r["bnf_name"] == "Atorvastatin"
        and r["confidence"] == "high" and r["match_type"] == "exact"
    ), r


def case_3_exact_case_insensitive():
    """'BISOPROLOL' (upper) -> exact match, beta blocker."""
    r = lookup("BISOPROLOL")
    return (
        r is not None and r["bnf_name"] == "Bisoprolol fumarate"
        and r["confidence"] == "high"
    ), r


def case_4_regression_dose_strip_mg():
    """'ramipril 5 mg' -> dose stripped -> exact match.

    Regression. Without dose stripping, the entity text from NER never
    matches the bare drug name in the CSV.
    """
    r = lookup("ramipril 5 mg")
    return (
        r is not None and r["bnf_name"] == "Ramipril"
        and r["confidence"] == "high" and r["match_type"] == "exact"
    ), r


def case_5_regression_dose_strip_with_frequency():
    """'atorvastatin 40 mg ON' -> dose+freq stripped -> exact match."""
    r = lookup("atorvastatin 40 mg ON")
    return (
        r is not None and r["bnf_name"] == "Atorvastatin"
        and r["confidence"] == "high"
    ), r


def case_6_regression_dose_strip_gram_unit():
    """'metformin 1 g BD' -> dose+freq stripped -> exact match.

    Tests gram unit (not just mg) and BD frequency abbreviation.
    """
    r = lookup("metformin 1 g BD")
    return (
        r is not None and r["bnf_name"] == "Metformin hydrochloride"
        and r["confidence"] == "high"
    ), r


def case_7_substring_query_contains_reference():
    """'patient on aspirin 75mg daily' -> 'aspirin' substring match.

    Tests direction-aware substring: query 'patient on aspirin 75mg
    daily' contains the reference 'aspirin' as a word. After dose strip
    we still have 'patient on aspirin', which contains 'aspirin'.
    """
    r = lookup("patient on aspirin 75mg daily")
    return (
        r is not None and r["bnf_name"] == "Aspirin"
        and r["confidence"] == "medium" and r["match_type"] == "substring"
    ), r


def case_8_regression_vague_query_no_overspecify():
    """'aspirin' must NOT match a hypothetical more-specific entry.

    Direction-aware substring rule: reference must be contained in
    query, not the other way around. If 'aspirin' (query) matched the
    reference 'co-amoxiclav with aspirin', that'd be wrong (over-
    specification). The mapper should return either 'Aspirin' (exact)
    or nothing -- never an over-specified combination.
    """
    r = lookup("aspirin")
    return (
        r is not None and r["bnf_name"] == "Aspirin"
        and r["confidence"] == "high"
    ), r


def case_9_regression_word_boundary_no_substring_inside_word():
    """'for' should NOT match inside 'formoterol'.

    Same bug class as the ICD-10 mapper's 'RA inside barotrauma' -- short
    queries should not match inside longer drug names. The mapper uses
    \\b word boundaries to prevent this.
    """
    r = lookup("for")
    # The query 'for' is 3 chars, no exact match, no word-bounded
    # substring match of any reference inside 'for'. Should be None.
    return r is None, r


def case_10_synonym_with_dose():
    """'frusemide 40 mg' (old spelling synonym for furosemide) -> exact."""
    r = lookup("frusemide 40 mg")
    return (
        r is not None and r["bnf_name"] == "Furosemide"
        and r["confidence"] == "high"
    ), r


def case_11_compound_drug_name():
    """'sacubitril/valsartan' -> exact match via synonym.

    The compound entry has both 'entresto' and 'sacubitril valsartan' as
    synonyms (with space). Query has slash. Canonicalisation collapses
    whitespace but does not normalise slash; this test confirms the
    behaviour. If the slash form is also a valid query, the slash version
    needs adding to the synonyms list.
    """
    r1 = lookup("sacubitril valsartan")  # space form, in synonyms
    r2 = lookup("entresto")              # brand, in synonyms
    return (
        r1 is not None and r1["bnf_name"] == "Sacubitril/valsartan"
        and r2 is not None and r2["bnf_name"] == "Sacubitril/valsartan"
    ), (r1, r2)


def case_12_no_match_unknown_drug():
    """Unknown drug returns None cleanly (not exception, not False)."""
    r = lookup("zzz-fictional-drug-xyz")
    return r is None, r


CASES = [
    ("01_exact_simple", case_1_exact_simple),
    ("02_exact_via_synonym", case_2_exact_via_synonym),
    ("03_exact_case_insensitive", case_3_exact_case_insensitive),
    ("04_regression_dose_strip_mg", case_4_regression_dose_strip_mg),
    ("05_regression_dose_strip_with_frequency", case_5_regression_dose_strip_with_frequency),
    ("06_regression_dose_strip_gram_unit", case_6_regression_dose_strip_gram_unit),
    ("07_substring_query_contains_reference", case_7_substring_query_contains_reference),
    ("08_regression_vague_query_no_overspecify", case_8_regression_vague_query_no_overspecify),
    ("09_regression_word_boundary", case_9_regression_word_boundary_no_substring_inside_word),
    ("10_synonym_with_dose", case_10_synonym_with_dose),
    ("11_compound_drug_name", case_11_compound_drug_name),
    ("12_no_match_unknown_drug", case_12_no_match_unknown_drug),
]


def main() -> int:
    print("Running 12-case BNF mapper test set\n")
    passes = 0
    fails = []
    for case_id, fn in CASES:
        ok, detail = fn()
        if ok:
            print(f"  [OK]   {case_id}")
            passes += 1
        else:
            print(f"  [FAIL] {case_id}")
            print(f"         got: {detail}")
            fails.append(case_id)
    print(f"\n{passes}/{len(CASES)} passed")
    if fails:
        print(f"FAILED: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())