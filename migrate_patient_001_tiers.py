"""Migrate patient_001's gold files to the three-tier schema.

Per supervisor 2026-06-17:
  Tier 1 = must-catch (clinician would consider an error to miss)
  Tier 2 = acceptable, credit-neutral (guideline-correct but not error to omit)
  Tier 3 = wrong (not stored; measured at evaluation time)

Contradictions move from per-document-pair to per-clinical-claim, satisfied
by any cross-pairing of claim_a_sources x claim_b_sources.
"""
import json
from pathlib import Path

PATIENT_DIR = Path("data/synthetic/documents/patient_001")

# ============================================================================
# Three-tier gold flags
# ============================================================================
gold_flags = {
    "patient_id": "patient_001",
    "patient_name": "Margaret Thompson",
    "patient_dob": "1954-08-15",
    "patient_nhs": "999 100 0001",
    "construction_date": "2026-06-17",
    "schema_version": "v2_three_tier",
    "design_principle": (
        "Cardiology + CKD case with intentionally planted allergy contradiction. "
        "Documents are chronologically distinct (Jan, Feb, Apr 2024) and "
        "deliberately diverse in content (GP referral / cardiology specialist letter / "
        "A&E discharge), targeting pairwise content-token Jaccard < 0.5."
    ),
    "tier_definitions": {
        "1_gold_must_catch": "A competent clinician would consider missing this an error.",
        "2_acceptable_credit_neutral": "Clinically correct, guideline-supported, but not an error to omit. Neither a coverage hit nor a precision penalty when emitted.",
        "3_wrong": "Fabrications or ungrounded flags (measured at evaluation time; not pre-recorded)."
    },
    "needs_clinician_validation": True,
    "validation_notes": (
        "Tier 1 vs Tier 2 boundary requires clinical judgement. The boundaries below "
        "are our best construction-time guess. Awaiting clinical review."
    ),
    "gold_flags": [
        {
            "tier": 1,
            "category": "ALLERGY_CONFLICT",
            "clinical_subject": "penicillin allergy",
            "severity": "HIGH",
            "rationale": (
                "Two documents disagree on allergy status (doc 01 + doc 03 say NKDA; "
                "doc 02 documents penicillin allergy). The flag should fire on the "
                "doc-02 allergy record because that is the explicit clinical statement. "
                "Missing this is unambiguously an error - allergy conflicts are HIGH-severity."
            ),
            "expected_source_document": "02_Cardiology_Thompson_28Feb2024.pdf"
        },
        {
            "tier": 1,
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "chronic kidney disease",
            "severity": "MEDIUM",
            "rationale": (
                "Last CKD-relevant clinical entry is doc 03 (04 Apr 2024). At evaluation "
                "time (mid-2026) this is well over the 90-day OVERDUE_FOLLOWUP threshold. "
                "A patient with CKD stage 3b and worsening eGFR not seen in over 2 years is "
                "a follow-up failure the system should catch."
            ),
            "expected_source_document": "03_AE_Discharge_Thompson_04Apr2024.pdf"
        },
        {
            "tier": 1,
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "heart failure",
            "severity": "MEDIUM",
            "rationale": (
                "Heart failure (HFrEF, LVEF 28%) documented across all three docs. Last "
                "entry 04 Apr 2024. At evaluation time well over 90 days. HFrEF with no "
                "follow-up in 2 years is a clinically meaningful safety gap."
            ),
            "expected_source_document": "03_AE_Discharge_Thompson_04Apr2024.pdf"
        },
        {
            "tier": 2,
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "sglt2 inhibitor in hfref with t2dm",
            "severity": "MEDIUM",
            "rationale": (
                "Patient has HFrEF (LVEF 28%) AND type 2 diabetes - guideline-directed "
                "therapy strongly indicates SGLT2 inhibitor (dapagliflozin/empagliflozin) "
                "for both indications. eGFR 32 is at the borderline but still within "
                "current SGLT2i licensing. The system flagging this is clinically correct "
                "but requires guideline knowledge beyond what's in the docs. Acceptable "
                "to emit, acceptable to omit."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "sacubitril/valsartan in hfref",
            "severity": "MEDIUM",
            "rationale": (
                "Patient has confirmed HFrEF with LVEF 28% on ramipril. Sacubitril/valsartan "
                "(Entresto) is recommended by NICE for HFrEF patients on ACE inhibitor with "
                "LVEF <=35%. Doc 02 explicitly mentions 'consider sacubitril/valsartan in "
                "4 weeks if eGFR stable' - but doc 03 (April A&E) shows no evidence this was "
                "actioned. The system flagging the gap is clinically correct but requires "
                "guideline knowledge."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "u&e recheck post-spironolactone",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 02 plan: 'Add spironolactone 25 mg OD - monitor U&E in 2 weeks'. "
                "No record of the 2-week U&E recheck in the document set. The system "
                "flagging this is clinically correct (spironolactone in CKD requires "
                "careful K monitoring) but inferring 'no result' requires reading "
                "across documents."
            ),
            "needs_clinician_validation": True
        }
    ]
}

(PATIENT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2), encoding="utf-8"
)

# ============================================================================
# Contradictions with cross-pairing match rule
# ============================================================================
gold_contradictions = {
    "patient_id": "patient_001",
    "construction_date": "2026-06-17",
    "schema_version": "v2_claim_based_matching",
    "match_rule": (
        "A gold contradiction is satisfied if the agent emits a contradiction where "
        "one side cites any document in claim_a_sources and the other side cites any "
        "document in claim_b_sources. The clinical fact is what matters, not which "
        "specific document-pair is cited."
    ),
    "gold_contradictions": [
        {
            "category": "ALLERGY",
            "severity": "HIGH",
            "claim_a": "no known drug allergies",
            "claim_b": "penicillin allergy",
            "claim_a_sources": [
                "01_GP_Referral_Thompson_12Jan2024.pdf",
                "03_AE_Discharge_Thompson_04Apr2024.pdf"
            ],
            "claim_b_sources": [
                "02_Cardiology_Thompson_28Feb2024.pdf"
            ],
            "explanation": (
                "Documents 01 and 03 record NKDA. Document 02 records a specific "
                "penicillin allergy with documented reaction date (rash 2018). These "
                "are directly opposing factual claims about the same patient. The "
                "cardiology letter is the more recent and more specific record. The "
                "A&E discharge reproduces the GP referral's NKDA error - realistic of "
                "real EHRs where bad allergy records propagate across systems."
            ),
            "rationale_for_planting": (
                "Tests whether the contradiction agent detects allergy-status "
                "disagreement, which is the highest-stakes contradiction type in "
                "clinical practice. The 2-vs-1 propagation structure tests that the "
                "matching rule is robust to multi-document fact propagation - any "
                "cross-pairing (01-vs-02, 03-vs-02) should count as the same correct "
                "detection."
            )
        }
    ]
}

(PATIENT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2), encoding="utf-8"
)

print("patient_001 migrated to three-tier schema:")
print(f"  Tier 1 flags: {sum(1 for f in gold_flags['gold_flags'] if f['tier'] == 1)}")
print(f"  Tier 2 flags: {sum(1 for f in gold_flags['gold_flags'] if f['tier'] == 2)}")
print(f"  Contradictions: {len(gold_contradictions['gold_contradictions'])} (claim-based matching)")