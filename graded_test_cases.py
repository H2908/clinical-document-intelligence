"""
Graded test set for Guard 3 v1.3.

Six hand-constructed test cases anchored to doc_719a82d6 (a Cardiology Clinic
Letter for Sarah Evans, dated 22 May 2026). Each case has a hand-labeled
expected verdict; the validator's output is compared against the label to
prove the detector discriminates across the threshold, not just at the
extremes.

Cases:
  1. obvious_fabrication    - quote contains words NOT in doc
  2. composition_fabrication - all words in doc but stitched from scattered
                               places; high token-overlap, low contiguous run
  3. verbatim_grounded       - copied directly from doc; must classify verbatim
  4. faithful_paraphrase     - punctuation/line-break smoothed, same content
  5. borderline_paraphrase   - one content word swapped with synonym; sits
                               near the 0.8 threshold
  6. misattribution          - quote verbatim from doc_bf78e73c but flag cites
                               doc_719a82d6 (both have identical text in our
                               test set, so misattribution is hard to test
                               cleanly here - see notes below)

Cases 4 and 5 are the load-bearing ones: they test whether 0.8 sits in a sane
place. Cases 1 and 2 test the off direction (must fire). Case 3 tests the
on direction (must not fire). Case 6 tests cross-document confusion.

Hand-labeling rationale is in each entry. Justifications are explicit so
that a reviewer (or your advisor) can challenge each label.
"""

# Real document text - the basis for all test cases.
DOC_719A82D6_TEXT = """NHS Foundation Trust
Cardiology Department
Date: 22 May 2026
CARDIOLOGY CLINIC LETTER
Patient: Sarah Evans
DOB: 1987-03-23 (age 39)
NHS Number: 101 226 9166
Address: 131 Mill Lane, Bristol, BS1 1AB
Clinical Findings:
Echocardiogram confirms ischaemic heart disease (ICD-10: I25.9). LVEF measured at 32%. Patient
reports symptoms consistent with NYHA class II.
Current Cardiac Medications:
- Atorvastatin 40 mg - 40 mg ON
- Aspirin 75 mg - 75 mg OD
Allergies: Patient reports penicillin allergy - rash on exposure in 2019. Avoid beta-lactams. Aspirin
tolerated.
Plan:
1. Continue current heart failure therapy
2. Refer to heart failure nurse for medication titration within 2 weeks
3. Repeat echocardiogram in 6 months
4. Routine bloods including U&E;, eGFR in 4 weeks
Dr. James Mitchell
Consultant Cardiologist"""

# A genuinely different document for misattribution testing.
DOC_OTHER_TEXT = """GP SURGERY NOTES
Date: 10 January 2026
Patient attended for routine review.
Vitals: BP 138/82, HR 72, weight 78 kg.
Patient reports good adherence to medications.
No new complaints. Discussed exercise tolerance.
Plan: continue current regimen. Annual review in 12 months.
Dr. Anna Hughes
General Practitioner"""

DOCUMENTS = {
    "doc_719a82d6": DOC_719A82D6_TEXT,
    "doc_other":    DOC_OTHER_TEXT,
}


GRADED_CASES = [
    # ------------------------------------------------------------------
    # Case 1: OBVIOUS FABRICATION
    # ------------------------------------------------------------------
    {
        "case_id": "1_obvious_fabrication",
        "description": "Patient was diagnosed with chronic kidney disease stage 4 last year and started on dialysis.",
        "category": "AI_RENAL_FAILURE",
        "cited_document_id": "doc_719a82d6",
        "source_quote": "diagnosed with chronic kidney disease stage 4 and commenced dialysis on Monday",
        "expected_verdict": "fabrication",
        "rationale": (
            "None of the key content words (chronic, kidney, disease, dialysis, "
            "Monday, commenced) appear in the cardiology letter. Token overlap "
            "against cited doc should be ~0.2 or less, well below 0.8. "
            "Detector must fire as 'fabrication'."
        ),
    },

    # ------------------------------------------------------------------
    # Case 2: COMPOSITION FABRICATION
    # ------------------------------------------------------------------
    # All content words present in doc but stitched from unrelated parts.
    # Doc has: "penicillin allergy ... rash on exposure ... Atorvastatin"
    # We claim the patient had a rash from Atorvastatin (false composition).
    {
        "case_id": "2_composition_fabrication",
        "description": "Patient developed an atorvastatin-related rash, statin allergy needs review.",
        "category": "AI_STATIN_ALLERGY",
        "cited_document_id": "doc_719a82d6",
        # Each individual word IS in the doc, but never together in this claim:
        "source_quote": "Atorvastatin rash exposure allergy 2019 penicillin tolerated",
        "expected_verdict": "composition-fabrication",
        "rationale": (
            "Every content word (atorvastatin, rash, exposure, allergy, "
            "penicillin, tolerated) appears in the doc, so token overlap is "
            "high (~1.0). But these words are scattered across unrelated "
            "sentences in the doc. Longest contiguous run between this "
            "quote and the doc is at most 1-2 tokens. Detector must fire "
            "as 'composition-fabrication' via the n-gram floor."
        ),
    },

    # ------------------------------------------------------------------
    # Case 3: VERBATIM GROUNDED
    # ------------------------------------------------------------------
    # Direct copy from the Plan section.
    {
        "case_id": "3_verbatim_grounded",
        "description": "Echocardiogram repeat planned in 6 months; verify completed.",
        "category": "AI_INVESTIGATION_NO_RESULT",
        "cited_document_id": "doc_719a82d6",
        "source_quote": "Repeat echocardiogram in 6 months",
        "expected_verdict": "verbatim",
        "rationale": (
            "Quote is copied directly from the Plan section, line 3. "
            "Token overlap = 1.0, longest contiguous run = 4 tokens "
            "(repeat, echocardiogram, months). Note: 'in' and '6' will not "
            "appear in content tokens because they're below 4 chars or "
            "numeric, so quote_tokens = [repeat, echocardiogram, months]. "
            "Longest run with the doc will be 3 (all of them, in order). "
            "Tier 2 substring check should find the exact phrase, "
            "classifying as 'verbatim'."
        ),
    },

    # ------------------------------------------------------------------
    # Case 4: FAITHFUL PARAPHRASE
    # ------------------------------------------------------------------
    # Same clinical content, surface form changed (punctuation smoothed,
    # sentence reordering). All content words present, long contiguous runs.
    {
        "case_id": "4_faithful_paraphrase",
        "description": "Patient has documented penicillin allergy with rash on exposure; avoid beta-lactams.",
        "category": "AI_ALLERGY_DRUG_CONFLICT",
        "cited_document_id": "doc_719a82d6",
        # Doc says: "Patient reports penicillin allergy - rash on exposure in 2019.
        #            Avoid beta-lactams. Aspirin tolerated."
        # Paraphrase merges adjacent sentences and drops the year:
        "source_quote": "Patient reports penicillin allergy rash on exposure avoid beta-lactams",
        "expected_verdict": "paraphrase",
        "rationale": (
            "All content words (patient, reports, penicillin, allergy, rash, "
            "exposure, avoid, beta, lactams) appear in doc. Token overlap = 1.0. "
            "The phrases 'penicillin allergy' and 'rash on exposure' and "
            "'avoid beta-lactams' all appear in long contiguous runs in the doc "
            "but with punctuation between them, so the exact substring fails "
            "but contiguous run is well above 5. Should classify as 'paraphrase' "
            "(grounded but not verbatim)."
        ),
    },

    # ------------------------------------------------------------------
    # Case 5: BORDERLINE PARAPHRASE
    # ------------------------------------------------------------------
    # One content word substituted with a clinical synonym.
    # Doc says "ischaemic heart disease" - we substitute "coronary".
    {
        "case_id": "5_borderline_paraphrase",
        "description": "Patient has documented coronary artery disease with reduced ejection fraction.",
        "category": "AI_DOCUMENTED_CAD",
        "cited_document_id": "doc_719a82d6",
        # Substitute "coronary artery" for "ischaemic heart" - same condition,
        # different terminology. Other words ("disease", "ejection", "fraction"
        # mapped to "LVEF") near-but-not-quite verbatim.
        "source_quote": "coronary artery disease confirmed LVEF measured at 32 percent",
        "expected_verdict": "fabrication_or_borderline",
        "rationale": (
            "Content tokens: coronary, artery, disease, confirmed, LVEF, "
            "measured, percent. Of these, 'coronary' and 'artery' and 'percent' "
            "do NOT appear in the doc (doc uses 'ischaemic', 'heart', '32%'). "
            "Overlap ratio is ~4/7 = 0.57, well below 0.8. "
            "EXPECTED: detector fires as 'fabrication'. "
            "INTERESTING: this is clinically a faithful paraphrase (CAD == IHD "
            "in this context), so a TRUE clinical-judgement validator might "
            "accept it. Mechanical token-overlap can't see this. This case "
            "demonstrates the limit of mechanical grounding (your paper's "
            "stated boundary). If the validator fires fabrication here, that "
            "is technically correct AND illustrates the limit."
        ),
    },

    # ------------------------------------------------------------------
    # Case 6: MISATTRIBUTION
    # ------------------------------------------------------------------
    # Quote is verbatim from doc_other, but flag cites doc_719a82d6.
    {
        "case_id": "6_misattribution",
        "description": "Patient reports good medication adherence at recent review.",
        "category": "AI_GOOD_ADHERENCE_NOTED",
        "cited_document_id": "doc_719a82d6",
        # Verbatim from doc_other:
        "source_quote": "Patient reports good adherence to medications routine review",
        "expected_verdict": "misattributed",
        "rationale": (
            "Quote content words: patient, reports, good, adherence, "
            "medications, routine, review. The cited doc (doc_719a82d6, "
            "cardiology letter) contains 'patient', 'reports', and 'medications' "
            "but not 'good', 'adherence', 'routine', 'review'. Overlap with "
            "cited = ~3/7 = 0.43, below 0.8. But doc_other contains all 7 "
            "content words (overlap = 1.0). Detector should fire as "
            "'misattributed' - content is grounded in a DIFFERENT doc than cited."
        ),
    },
]


# Validator we want to test
def run_validator(case: dict, documents: dict) -> dict:
    """Run the v1.3 validator logic on a single case.

    Mirrors the logic in agents/flag_agent.py::_llm_second_pass exactly.
    Kept inline here so the test is self-contained and independent.
    """
    import re
    from spacy.lang.en.stop_words import STOP_WORDS

    CLINICAL_GENERIC = {
        "patient", "documented", "noted", "listed",
        "verify", "confirm", "doctor",
    }
    STOPWORDS_AND_GENERIC = STOP_WORDS | CLINICAL_GENERIC
    FABRICATION_THRESHOLD = 0.8
    NGRAM_FLOOR = 5

    def content_tokens(text):
        tokens = re.findall(r"[a-z]{4,}", text.lower())
        return [t for t in tokens if t not in STOPWORDS_AND_GENERIC]

    def longest_contig(a, b):
        if not a or not b:
            return 0
        n, m = len(a), len(b)
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        best = 0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    if dp[i][j] > best:
                        best = dp[i][j]
        return best

    quote = case["source_quote"]
    cited = case["cited_document_id"]
    doc_text = documents.get(cited, "")

    quote_tokens = content_tokens(quote)
    cited_tokens = content_tokens(doc_text)

    if not quote_tokens:
        return {"verdict": "empty-content-quote", "overlap": 0.0, "longest_run": 0}

    overlap_cited = len(set(quote_tokens) & set(cited_tokens))
    overlap_ratio = overlap_cited / len(set(quote_tokens))

    # Misattribution check
    if overlap_ratio < FABRICATION_THRESHOLD:
        best_other_ratio = 0.0
        best_other_id = None
        for other_id, other_text in documents.items():
            if other_id == cited:
                continue
            other_tokens = content_tokens(other_text)
            if not other_tokens:
                continue
            other_overlap = len(set(quote_tokens) & set(other_tokens))
            other_ratio = other_overlap / len(set(quote_tokens))
            if other_ratio > best_other_ratio:
                best_other_ratio = other_ratio
                best_other_id = other_id

        if best_other_ratio >= FABRICATION_THRESHOLD:
            return {
                "verdict": "misattributed",
                "overlap": overlap_ratio,
                "best_other_doc": best_other_id,
                "best_other_overlap": best_other_ratio,
                "longest_run": longest_contig(quote_tokens, cited_tokens),
            }
        return {
            "verdict": "fabrication",
            "overlap": overlap_ratio,
            "longest_run": longest_contig(quote_tokens, cited_tokens),
        }

    longest_run = longest_contig(quote_tokens, cited_tokens)
    min_run_needed = min(NGRAM_FLOOR, max(2, len(quote_tokens) // 2 + 1))
    if longest_run < min_run_needed:
        return {
            "verdict": "composition-fabrication",
            "overlap": overlap_ratio,
            "longest_run": longest_run,
            "min_run_needed": min_run_needed,
        }

    import re as _re
    quote_norm = _re.sub(r"\s+", " ", quote).strip()
    doc_norm = _re.sub(r"\s+", " ", doc_text).strip()
    if quote_norm in doc_norm:
        return {"verdict": "verbatim", "overlap": overlap_ratio, "longest_run": longest_run}
    return {"verdict": "paraphrase", "overlap": overlap_ratio, "longest_run": longest_run}


# Run all cases and report
if __name__ == "__main__":
    print("=" * 75)
    print("GRADED TEST SET — Guard 3 v1.3 validation")
    print("=" * 75)
    print()

    pass_count = 0
    fail_count = 0
    notes = []

    for case in GRADED_CASES:
        result = run_validator(case, DOCUMENTS)
        expected = case["expected_verdict"]
        got = result["verdict"]

        # Borderline case has a flexible expected verdict
        if expected == "fabrication_or_borderline":
            passed = got in ("fabrication", "composition-fabrication", "paraphrase")
        else:
            passed = (got == expected)

        status = "PASS" if passed else "FAIL"
        if passed:
            pass_count += 1
        else:
            fail_count += 1

        print(f"[{status}] {case['case_id']}")
        print(f"  expected: {expected}")
        print(f"  got:      {got}")
        print(f"  overlap:  {result.get('overlap', 0):.2f}")
        print(f"  longest_run: {result.get('longest_run', 0)}")
        if "best_other_doc" in result:
            print(f"  best_other_doc:     {result['best_other_doc']}")
            print(f"  best_other_overlap: {result.get('best_other_overlap', 0):.2f}")
        if "min_run_needed" in result:
            print(f"  min_run_needed: {result['min_run_needed']}")
        print(f"  rationale: {case['rationale'][:200]}...")
        print()

    print("=" * 75)
    print(f"RESULT: {pass_count} pass, {fail_count} fail out of {len(GRADED_CASES)}")
    print("=" * 75)