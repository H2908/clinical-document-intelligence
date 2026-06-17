"""Test set for ontology.icd10_mapper.lookup.

Twelve cases covering:
  - Tier 1 (exact) on primary term and on synonym
  - Tier 2 (substring) with direction-aware matching
  - The regression case: 'chronic heart failure' must NOT match I50.32
    (diastolic) even though that reference contains the query as substring.
    This was a real bug 2026-06-17 caught at first run.
  - Case insensitivity, whitespace normalisation, abbreviations
  - Vague queries returning vague codes (refuses to over-specify)
  - No match returns None
"""
from ontology.icd10_mapper import lookup


CASES = [
    # --- Tier 1 (exact match) ---
    {
        "id": "exact_primary",
        "query": "Essential hypertension",
        "expect_code": "I10",
        "expect_confidence": "high",
        "expect_match_type": "exact",
        "rationale": "Direct match on primary term (case-insensitive)",
    },
    {
        "id": "exact_synonym",
        "query": "HFrEF",
        "expect_code": "I50.22",
        "expect_confidence": "high",
        "expect_match_type": "exact",
        "rationale": "Match on abbreviation synonym",
    },
    {
        "id": "exact_synonym_caps",
        "query": "T2DM",
        "expect_code": "E11.9",
        "expect_confidence": "high",
        "expect_match_type": "exact",
        "rationale": "Case-insensitive synonym match",
    },

    # --- Tier 2 (substring, direction-aware) ---
    {
        "id": "substring_query_contains_short_synonym",
        "query": "patient with documented penicillin allergy from 2018",
        "expect_code": "Z88.0",
        "expect_confidence": "medium",
        "expect_match_type": "substring",
        "rationale": "Long query contains short synonym 'penicillin allergy'",
    },
    {
        "id": "substring_query_contains_full_term",
        "query": "presenting with chronic kidney disease stage 3b and worsening eGFR",
        "expect_code": "N18.32",
        "expect_confidence": "medium",
        "expect_match_type": "substring",
        "rationale": "Long query contains the full primary term for N18.32",
    },
    {
        "id": "substring_longest_wins",
        "query": "ongoing management of chronic heart failure with reduced ejection fraction",
        "expect_code": "I50.22",
        "expect_confidence": "medium",
        "expect_match_type": "substring",
        "rationale": "Query contains both 'heart failure' (-> I50.9) and 'chronic heart failure with reduced ejection fraction' (-> I50.22); the longer (more specific) wins",
    },

    # --- REGRESSION: vague query must NOT match specific code ---
    {
        "id": "regression_vague_query_no_overspecify",
        "query": "chronic heart failure",
        "expect_code": "I50.9",
        "expect_confidence": "medium",
        "expect_match_type": "substring",
        "rationale": (
            "REGRESSION TEST. Before the direction-aware fix, this query matched "
            "the longer reference 'chronic heart failure with preserved ejection "
            "fraction' and returned I50.32 (diastolic) - clinically wrong, the "
            "query didn't say preserved. Must now return I50.9 (unspecified)."
        ),
    },

    # --- Whitespace / casing ---
    {
        "id": "whitespace_normalisation",
        "query": "  type 2  diabetes  mellitus  ",
        "expect_code": "E11.9",
        "expect_confidence": "high",
        "expect_match_type": "exact",
        "rationale": "Multiple spaces collapse to single; leading/trailing strip",
    },
    {
        "id": "mixed_case",
        "query": "Asthma",
        "expect_code": "J45.9",
        "expect_confidence": "high",
        "expect_match_type": "exact",
        "rationale": "Title-case query maps to lowercase synonym",
    },

    # --- Multi-condition queries (substring tier handles by length) ---
    {
        "id": "embedded_in_clinical_note",
        "query": "Mr Ofori has type 2 diabetes with HbA1c 9.1 percent and obesity BMI 31.2",
        "expect_code": "E11.9",
        "expect_confidence": "medium",
        "expect_match_type": "substring",
        "rationale": "Query contains 'type 2 diabetes' synonym - longest reference fitting the query wins",
    },

    # --- No match ---
    {
        "id": "no_match_unknown_term",
        "query": "barotrauma of the inner ear",
        "expect_code": None,
        "expect_confidence": None,
        "expect_match_type": None,
        "rationale": "Not in curated set - returns None",
    },
    {
        "id": "no_match_empty_string",
        "query": "   ",
        "expect_code": None,
        "expect_confidence": None,
        "expect_match_type": None,
        "rationale": "Empty/whitespace-only returns None",
    },
]


def run() -> int:
    passes = []
    fails = []
    for case in CASES:
        result = lookup(case["query"])
        if case["expect_code"] is None:
            if result is None:
                passes.append(case["id"])
            else:
                fails.append((case["id"], case, result))
            continue

        if result is None:
            fails.append((case["id"], case, None))
            continue

        ok = (
            result["code"] == case["expect_code"]
            and result["confidence"] == case["expect_confidence"]
            and result["match_type"] == case["expect_match_type"]
        )
        if ok:
            passes.append(case["id"])
        else:
            fails.append((case["id"], case, result))

    print(f"\n{len(passes)}/{len(CASES)} cases passed")
    if passes:
        print("\nPASSED:")
        for pid in passes:
            print(f"  [OK]   {pid}")
    if fails:
        print("\nFAILED:")
        for fid, case, result in fails:
            print(f"  [FAIL] {fid}")
            print(f"         query:          {case['query']!r}")
            print(f"         expected:       code={case['expect_code']!r} "
                  f"confidence={case['expect_confidence']!r} type={case['expect_match_type']!r}")
            if result is None:
                print(f"         got:            None")
            else:
                print(f"         got:            code={result.get('code')!r} "
                      f"confidence={result.get('confidence')!r} "
                      f"type={result.get('match_type')!r} "
                      f"matched={result.get('matched_against')!r}")
            print(f"         rationale:      {case['rationale']}")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    sys.exit(run())