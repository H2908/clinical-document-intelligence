"""
Hand-constructed 8-case test set for the flag-identity matching rule.

Per spec at paper/config/flag_identity_v1.md:
    Two flags A and B are the same flag iff:
        A.category == B.category
        AND
        canonical(A.clinical_subject) == canonical(B.clinical_subject)

Four "must merge" cases: same category + same subject, varied wording in
the description. The matcher MUST return True (same flag).

Four "must stay distinct" cases: same category, shared condition word in
the description, but DIFFERENT clinical_subject. The matcher MUST return
False (different flags). These are the load-bearing cases — they prove
the matcher refuses to over-merge.

Construct before implementing the matcher, per supervisor Day 5 sign-off.
Spec committed before code.
"""

# ============================================================================
# MUST MERGE - same category + same canonical subject, different description
# ============================================================================
MUST_MERGE = [
    {
        "case_id": "merge_1_penicillin_punctuation",
        "rationale": "Same allergy flag; descriptions differ only in punctuation "
                     "(semicolon vs period). This is exactly the Day 4 finding "
                     "that motivated the new rule.",
        "flag_a": {
            "category": "AI_ALLERGY_DRUG_CONFLICT",
            "clinical_subject": "penicillin allergy",
            "description": "Documented penicillin allergy with rash; verify no beta-lactams.",
        },
        "flag_b": {
            "category": "AI_ALLERGY_DRUG_CONFLICT",
            "clinical_subject": "penicillin allergy",
            "description": "Documented penicillin allergy with rash. Verify no beta-lactams.",
        },
    },
    {
        "case_id": "merge_2_atorvastatin_doc_count",
        "rationale": "Same duplicate-medication flag for the same drug. "
                     "Description varies only in the document-count integer "
                     "(an artefact of upload state, not a clinical difference).",
        "flag_a": {
            "category": "POSSIBLE_DUPLICATE_MEDICATION",
            "clinical_subject": "Atorvastatin",
            "description": "Atorvastatin mentioned across 5 documents. Confirm current dose.",
        },
        "flag_b": {
            "category": "POSSIBLE_DUPLICATE_MEDICATION",
            "clinical_subject": "Atorvastatin",
            "description": "Atorvastatin mentioned across 6 documents. Confirm current dose.",
        },
    },
    {
        "case_id": "merge_3_case_difference",
        "rationale": "Same subject differing only by case. Canonical = lower.strip(), "
                     "so 'Heart Failure' and 'heart failure' canonicalise identically.",
        "flag_a": {
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "Heart Failure",
            "description": "Heart Failure last documented 834 days ago.",
        },
        "flag_b": {
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "heart failure",
            "description": "heart failure last documented 835 days ago. Consider review.",
        },
    },
    {
        "case_id": "merge_4_egfr_phrasing",
        "rationale": "Same investigation-no-result flag; descriptions paraphrase "
                     "the same clinical content with different prose.",
        "flag_a": {
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "eGFR follow-up",
            "description": "Bloods including eGFR were requested in 4 weeks; no result found in records.",
        },
        "flag_b": {
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "eGFR follow-up",
            "description": "Routine bloods including eGFR ordered at 4-week interval; results not documented.",
        },
    },
]


# ============================================================================
# MUST STAY DISTINCT - same category + shared condition word, but
# clinical_subject is GENUINELY DIFFERENT. The matcher must refuse to merge.
# These are the load-bearing cases.
# ============================================================================
MUST_STAY_DISTINCT = [
    {
        "case_id": "distinct_1_hf_acei_vs_followup",
        "rationale": "Both flags concern heart failure but address completely "
                     "different clinical issues: one is about missing guideline-"
                     "directed therapy (ACEi absence), the other is about follow-up "
                     "timing. A matcher that merged these on the shared 'heart "
                     "failure' word would falsely inflate reproducibility.",
        "flag_a": {
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "ACEi/ARNi absence in HF",
            "description": "Heart failure documented but no ACE inhibitor or ARNi prescribed.",
        },
        "flag_b": {
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "heart failure follow-up timing",
            "description": "Heart failure follow-up appointment overdue by 4 weeks.",
        },
    },
    {
        "case_id": "distinct_2_dm_hba1c_vs_egfr",
        "rationale": "Both flags concern overdue diabetes investigations but the "
                     "subjects are different tests. Conflating them would lose a "
                     "real clinical distinction the system correctly identified.",
        "flag_a": {
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "HbA1c follow-up",
            "description": "Patient with type 2 diabetes; HbA1c last recorded 14 months ago.",
        },
        "flag_b": {
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "eGFR follow-up",
            "description": "Patient with type 2 diabetes; eGFR not checked in last year.",
        },
    },
    {
        "case_id": "distinct_3_dupes_different_drugs",
        "rationale": "Two duplicate-medication flags for two different drugs. The "
                     "shared category and shared template wording must not collapse "
                     "them — they're flags about distinct medications.",
        "flag_a": {
            "category": "POSSIBLE_DUPLICATE_MEDICATION",
            "clinical_subject": "Atorvastatin",
            "description": "Atorvastatin mentioned across 5 documents. Confirm current dose.",
        },
        "flag_b": {
            "category": "POSSIBLE_DUPLICATE_MEDICATION",
            "clinical_subject": "Aspirin",
            "description": "Aspirin mentioned across 5 documents. Confirm current dose.",
        },
    },
    {
        "case_id": "distinct_4_allergy_different_drugs",
        "rationale": "Two allergy-drug-conflict flags concerning different allergens. "
                     "Both descriptions mention 'allergy' and 'beta-lactams', but the "
                     "subjects (the allergens themselves) are distinct.",
        "flag_a": {
            "category": "AI_ALLERGY_DRUG_CONFLICT",
            "clinical_subject": "penicillin allergy",
            "description": "Documented penicillin allergy with rash; verify no beta-lactams.",
        },
        "flag_b": {
            "category": "AI_ALLERGY_DRUG_CONFLICT",
            "clinical_subject": "sulfa allergy",
            "description": "Documented sulfa allergy; verify no sulfonamide prescribing.",
        },
    },
]


# ============================================================================
# Test runner: imports the matcher (once implemented) and asserts all 8 pass.
# ============================================================================
def run_tests(matcher_fn) -> tuple[int, int, list[str]]:
    """Run the 8-case test set against a candidate matcher.

    matcher_fn: callable taking (flag_a: dict, flag_b: dict) -> bool

    Returns (pass_count, fail_count, failure_messages).
    """
    failures: list[str] = []

    for case in MUST_MERGE:
        result = matcher_fn(case["flag_a"], case["flag_b"])
        if not result:
            failures.append(
                f"[FAIL] {case['case_id']}: expected MERGE, got DISTINCT. "
                f"Rationale: {case['rationale']}"
            )

    for case in MUST_STAY_DISTINCT:
        result = matcher_fn(case["flag_a"], case["flag_b"])
        if result:
            failures.append(
                f"[FAIL] {case['case_id']}: expected DISTINCT, got MERGE. "
                f"Rationale: {case['rationale']}"
            )

    total = len(MUST_MERGE) + len(MUST_STAY_DISTINCT)
    return total - len(failures), len(failures), failures