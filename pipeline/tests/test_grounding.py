"""
tests/test_grounding.py — pytest suite for grounding.py's Guard 3
(contiguous-grounding check), the paper's principal technical
contribution.

These are the SAME cases used to validate the calibration fix
described in the paper's Evaluation section, re-run here against the
extracted, standalone module so a reviewer can verify Guard 3 actually
works as claimed without needing an API key, the rest of the pipeline,
or this paper's authors' say-so.

Run:
    pytest tests/test_grounding.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grounding import (
    check_contiguous_grounding,
    check_trivial_quote,
    check_phantom_citation,
    check_subject_relevance,
    run_four_guards,
)


# ============================================================================
# Guard 3 — the paper's flagship regression cases
# ============================================================================

def test_nyha_composition_fabrication_still_rejected():
    """The paper's flagship example of composition-fabrication: a quote
    that stitches two non-adjacent, individually-real sentence fragments
    into a claim the source document never actually makes. Must be
    rejected regardless of any calibration changes."""
    quote = "NYHA class II consistent with heart failure therapy"
    source = (
        "Patient reports symptoms consistent with NYHA class II. "
        "Plan: Continue current heart failure therapy."
    )
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is False
    assert result["verdict"] == "composition-fabrication"


def test_egfr_paraphrase_accepted():
    """A genuine paraphrase (surface smoothing of punctuation/line breaks,
    all content words present and contiguous) must be accepted."""
    quote = "bloods including eGFR in 4 weeks"
    source = "Routine bloods including U&E, eGFR in 4 weeks"
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is True


def test_echocardiogram_verbatim_accepted():
    """A genuinely verbatim, terse clinical instruction must be accepted,
    even though it is short — this is exactly the kind of quote Guard 2's
    soft branch and Guard 3's length-scaled floor exist to protect."""
    quote = "Repeat echocardiogram in 6 months"
    source = "Plan: 3. Repeat echocardiogram in 6 months"
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is True


def test_metformin_dose_quote_accepted_after_calibration_fix():
    """This is THE case that motivated the calibration fix described in
    the paper: a short, genuinely fully-contiguous dose-bearing quote
    that the pre-fix tokenizer and threshold logic could never accept,
    regardless of true fidelity, because it discarded numeric tokens
    and required an absolute 5-token floor unreachable by short quotes."""
    quote = "Metformin 1000 mg"
    source = "3. Metformin 1000 mg p.o. b.i.d."
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is True
    assert result["verdict"] == "verbatim"


def test_digoxin_dose_quote_accepted_after_calibration_fix():
    """Second confirmed case from the same calibration fix."""
    quote = "Digoxin 0.25 mg"
    source = "6. Digoxin 0.25 mg p.o. daily."
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is True


def test_pure_fabrication_rejected():
    """A quote with low token overlap against the source — genuine
    invention, not merely a citation-fidelity problem — must be
    rejected as fabrication, distinct from composition-fabrication."""
    quote = "patient has a documented severe penicillin anaphylaxis reaction"
    source = "Patient reports mild seasonal hay fever symptoms in spring."
    result = check_contiguous_grounding(quote, source)
    assert result["passes"] is False
    assert result["verdict"] in ("fabrication", "composition-fabrication")


def test_misattribution_detected_when_other_doc_provided():
    """A quote that doesn't ground against the cited document but DOES
    ground against a different document in the patient's record is a
    distinct failure mode: wrong citation, not invention."""
    quote = "Metformin 1000 mg twice daily with meals"
    cited_doc_text = "Patient has hypertension, well controlled on amlodipine."
    other_docs = {
        "other_doc_1": "Discharge medications: Metformin 1000 mg twice daily with meals."
    }
    result = check_contiguous_grounding(quote, cited_doc_text, other_docs)
    assert result["passes"] is False
    assert result["verdict"] == "misattributed"


# ============================================================================
# Guard 1 — phantom citation
# ============================================================================

def test_guard1_rejects_unknown_document_id():
    assert check_phantom_citation("doc_999", {"doc_001", "doc_002"}) is False


def test_guard1_accepts_known_document_id():
    assert check_phantom_citation("doc_001", {"doc_001", "doc_002"}) is True


# ============================================================================
# Guard 2 — trivial quote floor
# ============================================================================

def test_guard2_rejects_single_word_quote():
    assert check_trivial_quote("insulin", "AI_DRUG_CONCERN", "insulin dosing concern") is False


def test_guard2_soft_branch_accepts_terse_grounded_instruction():
    # 5 words, shares "echocardiogram" with description -> soft pass
    assert check_trivial_quote(
        "Repeat echocardiogram in 6 months",
        "AI_INVESTIGATION_NO_RESULT",
        "echocardiogram follow-up not documented",
    ) is True


# ============================================================================
# Guard 4 — subject relevance
# ============================================================================

def test_guard4_rejects_unrelated_quote():
    assert check_subject_relevance(
        "patient prefers tea over coffee in the morning",
        "AI_RENAL_DRUG_CONTRAINDICATION",
        "metformin in chronic renal failure",
    ) is False


def test_guard4_accepts_related_quote():
    assert check_subject_relevance(
        "Metformin 1000 mg prescribed",
        "AI_RENAL_DRUG_CONTRAINDICATION",
        "metformin in chronic renal failure",
    ) is True


# ============================================================================
# Full orchestration
# ============================================================================

def test_run_four_guards_full_accept():
    flag = {
        "cited_document_id": "doc_001",
        "source_quote": "Metformin 1000 mg",
        "category": "AI_RENAL_DRUG_CONTRAINDICATION",
        "description": "Metformin prescribed alongside documented renal failure",
    }
    result = run_four_guards(
        flag,
        cited_document_text="3. Metformin 1000 mg p.o. b.i.d.",
        valid_document_ids={"doc_001"},
    )
    assert result["accepted"] is True
    assert result["failed_guard"] is None


def test_run_four_guards_full_reject_phantom_citation():
    flag = {
        "cited_document_id": "doc_999",
        "source_quote": "Metformin 1000 mg",
        "category": "AI_RENAL_DRUG_CONTRAINDICATION",
        "description": "Metformin prescribed alongside documented renal failure",
    }
    result = run_four_guards(
        flag,
        cited_document_text="3. Metformin 1000 mg p.o. b.i.d.",
        valid_document_ids={"doc_001"},
    )
    assert result["accepted"] is False
    assert result["failed_guard"] == 1
