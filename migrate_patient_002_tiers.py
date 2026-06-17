"""Migrate patient_002's gold files to the three-tier schema.

Per supervisor 2026-06-17. Mirrors the patient_001 migration: tier field
on every flag, claim-based matching for contradictions (here: empty list
but with the same schema fields for symmetry).
"""
import json
from pathlib import Path

PATIENT_DIR = Path("data/synthetic/documents/patient_002")

# ============================================================================
# Three-tier gold flags
# ============================================================================
gold_flags = {
    "patient_id": "patient_002",
    "patient_name": "Daniel Ofori",
    "patient_dob": "1968-03-22",
    "patient_nhs": "999 200 0002",
    "construction_date": "2026-06-17",
    "schema_version": "v2_three_tier",
    "design_principle": (
        "T2DM case with worsening glycaemic control. Three documents chronologically "
        "spread May 2023 - Feb 2024. Documents are deliberately diverse: GP annual "
        "review / diabetes clinic specialist letter / lab report. The lab report "
        "tests the lab_parser code path. NO planted contradictions - false-positive "
        "control."
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
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "type 2 diabetes",
            "severity": "MEDIUM",
            "rationale": (
                "Last clinical entry is doc 03 lab report (14 Feb 2024). HbA1c was 9.1% "
                "(very poor control) with a comment recommending clinical review. No "
                "follow-up documented. At evaluation time (mid-2026), this is over 2 "
                "years without follow-up on a patient with progressively worsening "
                "glycaemic control. Missing this is unambiguously a follow-up failure."
            ),
            "expected_source_document": "03_Lab_Report_Ofori_14Feb2024.pdf"
        },
        {
            "tier": 2,
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "sglt2 inhibitor in t2dm",
            "severity": "MEDIUM",
            "rationale": (
                "Patient has T2DM with HbA1c 9.1% on metformin + gliclazide, eGFR 74 "
                "(adequate for SGLT2i). NICE NG28 recommends SGLT2i as second-line "
                "intensification in patients with established cardiovascular disease "
                "or high CV risk, and current guidance increasingly favours SGLT2i over "
                "sulfonylureas. The system flagging this is clinically correct but "
                "requires guideline knowledge. Acceptable to emit, acceptable to omit."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_UNDOCUMENTED_TREATMENT",
            "clinical_subject": "glp-1 receptor agonist in t2dm with obesity",
            "severity": "MEDIUM",
            "rationale": (
                "Patient has T2DM with BMI 31.2 and HbA1c 9.1% on dual oral therapy. "
                "GLP-1 RAs (e.g. semaglutide) are NICE-recommended for T2DM with BMI "
                ">=35 or BMI 32.5+ in certain populations and have the additional "
                "benefit of weight reduction. The system flagging this gap is "
                "clinically defensible but requires guideline knowledge."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "6-month diabetes clinic follow-up",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 02 (diabetes clinic, Sep 2023) plan: 'Review in clinic at 6 months'. "
                "No record of a clinic follow-up after that point. The lab report in Feb "
                "2024 is close to that 6-month mark but isn't a clinic review. The "
                "system flagging the unactioned planned follow-up is correct but "
                "requires reading across documents."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_WORSENING_TREND",
            "clinical_subject": "hba1c trajectory",
            "severity": "MEDIUM",
            "rationale": (
                "HbA1c 8.4 -> 8.7 -> 9.1 across 9 months. Monotonic worsening despite "
                "treatment intensification. The system flagging this trend is "
                "clinically meaningful but requires longitudinal observation reasoning "
                "beyond per-document analysis. Note: AI_WORSENING_TREND is not a "
                "currently-defined system category - if emitted, the actual category "
                "label may vary."
            ),
            "needs_clinician_validation": True
        }
    ]
}

(PATIENT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2), encoding="utf-8"
)

# ============================================================================
# Contradictions - explicitly empty list with new schema fields for symmetry
# ============================================================================
gold_contradictions = {
    "patient_id": "patient_002",
    "construction_date": "2026-06-17",
    "schema_version": "v2_claim_based_matching",
    "match_rule": (
        "A gold contradiction is satisfied if the agent emits a contradiction where "
        "one side cites any document in claim_a_sources and the other side cites any "
        "document in claim_b_sources. The clinical fact is what matters, not which "
        "specific document-pair is cited."
    ),
    "gold_contradictions": [],
    "notes": (
        "patient_002 is the false-positive control. The three documents are "
        "deliberately internally consistent - same demographics, same conditions, "
        "same medication progression (metformin -> + gliclazide), same allergy "
        "status (NKDA), same renal function trend. Any contradiction the agent "
        "emits on this patient is a false positive."
    )
}

(PATIENT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2), encoding="utf-8"
)

print("patient_002 migrated to three-tier schema:")
print(f"  Tier 1 flags: {sum(1 for f in gold_flags['gold_flags'] if f['tier'] == 1)}")
print(f"  Tier 2 flags: {sum(1 for f in gold_flags['gold_flags'] if f['tier'] == 2)}")
print(f"  Contradictions: {len(gold_contradictions['gold_contradictions'])} (false-positive control)")