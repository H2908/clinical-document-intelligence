"""Build patient_009 - Asthma case with planted severity-classification contradiction.

The contradiction: GP (doc 01, Mar 2024) classifies asthma as MILD INTERMITTENT
based on infrequent salbutamol use. Respiratory clinic (doc 02, Aug 2024)
reclassifies as MODERATE PERSISTENT after reviewing PEFR diary and symptom
log. A&E discharge (doc 03, Nov 2024, post-exacerbation) labels asthma
'mild' again - the severity flips back without justification.

This is realistic of how asthma severity is misclassified across UK primary,
secondary, and emergency care: GP records often lag behind specialist
reclassification, and A&E records frequently default to the patient's
self-reported or pre-existing severity tag.

Three PDFs + gold flags + gold contradictions + README, written atomically.

Convention follows patient_001 / patient_002 / patient_006 exactly.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import json

OUT_DIR = Path("data/synthetic/documents/patient_009")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Shared patient identity ----
NAME = "Lauren Bennett"
DOB = "1991-04-18"
NHS = "999 900 0009"
ADDRESS = "4 Pelham Court, Leeds, LS6 2BN"
SEX = "F"
PATIENT_ID = "patient_009"


def write_pdf(filename: str, body_paragraphs: list[str]) -> Path:
    """Write a single-page A4 PDF matching the existing synthetic-doc style."""
    out_path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 13
    flowables = []
    for para_text in body_paragraphs:
        flowables.append(Paragraph(para_text, body_style))
        flowables.append(Spacer(1, 4))
    doc.build(flowables)
    return out_path


# ============================================================================
# DOC 1 - GP Asthma Review, 11 Mar 2024
# Establishes baseline: MILD INTERMITTENT classification, salbutamol PRN only,
# no preventer. Reports symptoms 1-2 times per week.
# ============================================================================
doc1_body = [
    "<b>Pelham Court Medical Practice</b>",
    "Date: 11 Mar 2024",
    "<b>ASTHMA ANNUAL REVIEW</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 32)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; Asthma (ICD-10: J45.909) &mdash; diagnosed 2010, childhood-onset",
    "&bull; Allergic rhinitis (ICD-10: J30.9)",
    "",
    "<b>Current Medications:</b>",
    "&bull; Salbutamol 100 mcg MDI &mdash; PRN, 1-2 puffs as needed",
    "&bull; Cetirizine 10 mg OD &mdash; spring/summer for rhinitis",
    "",
    "<b>Allergies:</b> NKDA. Hay fever (grass pollen).",
    "",
    "<b>Asthma control assessment:</b> Patient reports salbutamol use 1-2 days per week, "
    "typically triggered by exercise or cold weather. No nocturnal waking with cough or wheeze. "
    "No exacerbations requiring oral steroids or A&amp;E attendance in past 12 months. "
    "ACT (Asthma Control Test) score 22/25.",
    "",
    "<b>Examination:</b> Chest clear on auscultation. PEFR 380 L/min "
    "(predicted 460 L/min, 83% of personal best). RR 16. SpO2 99% on room air.",
    "",
    "<b>Assessment:</b> Asthma classification: <b>mild intermittent</b>. Control adequate "
    "on reliever-only regime per current symptom pattern and ACT score. No preventer indicated "
    "at present per BTS/SIGN step 1.",
    "",
    "<b>Plan:</b>",
    "&bull; Continue salbutamol 100 mcg MDI PRN",
    "&bull; Inhaler technique reviewed and confirmed adequate",
    "&bull; Personalised asthma action plan provided",
    "&bull; Annual flu vaccine recommended (October)",
    "&bull; Review in 12 months or sooner if symptoms increase",
    "",
    "Dr H. Choudhury, GP",
]


# ============================================================================
# DOC 2 - Respiratory Clinic Letter, 22 Aug 2024
# THE RECLASSIFICATION: patient referred after symptom escalation; PEFR
# diary and detailed history show MODERATE PERSISTENT pattern. Starts
# beclometasone preventer. GINA step 3 reclassification with explicit
# justification (symptoms >2/week, nocturnal waking, FEV1 reduced).
# ============================================================================
doc2_body = [
    "<b>St James's Hospital &mdash; Respiratory Outpatient Department</b>",
    "Date: 22 Aug 2024",
    "<b>CLINIC LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 33)",
    f"NHS Number: {NHS}",
    "",
    "Dear Dr Choudhury,",
    "",
    "Thank you for referring Ms Bennett for respiratory review. I saw her today following "
    "her recent symptom escalation.",
    "",
    "<b>History:</b> Childhood-onset asthma, previously well-controlled on salbutamol PRN. "
    "Over the past 4 months symptoms have escalated. She now reports salbutamol use 4-5 days "
    "per week, nocturnal waking with cough 2 nights per week, and reduced exercise tolerance. "
    "No identified new triggers (no pets, no smoking, no occupational exposure). "
    "ACT score has fallen to 15/25.",
    "",
    "<b>PEFR diary (2 weeks):</b> Mean morning PEFR 280 L/min, mean evening 360 L/min, "
    "diurnal variability 22% (significant variability &gt;20% is indicative of poorly "
    "controlled asthma).",
    "",
    "<b>Examination:</b> RR 18, SpO2 97% on air. Chest: occasional end-expiratory wheeze, "
    "no crackles. No accessory muscle use at rest.",
    "",
    "<b>Spirometry (today):</b> FEV1 2.18 L (72% predicted), FVC 3.20 L (94% predicted), "
    "FEV1/FVC 0.68 (reduced, consistent with obstructive defect). 12% reversibility post-bronchodilator.",
    "",
    "<b>Allergies:</b> NKDA. Atopy with seasonal allergic rhinitis.",
    "",
    "<b>Assessment:</b> Symptom pattern, ACT score, PEFR variability, and spirometry are "
    "consistent with <b>moderate persistent asthma</b> (GINA classification, step 3). "
    "Patient previously on reliever-only therapy which is inadequate given current control. "
    "Requires initiation of inhaled corticosteroid as preventer.",
    "",
    "<b>Plan:</b>",
    "&bull; <b>Start beclometasone dipropionate 200 mcg MDI BD</b> (Clenil Modulite)",
    "&bull; Continue salbutamol 100 mcg MDI as reliever PRN",
    "&bull; Updated asthma action plan provided; education on preventer-vs-reliever distinction",
    "&bull; Inhaler technique reviewed - good MDI technique with spacer recommended",
    "&bull; PEFR diary to continue for 8 weeks",
    "&bull; Respiratory clinic follow-up at 12 weeks to assess response",
    "&bull; If poor response, consider step-up to ICS/LABA combination",
    "",
    "Yours sincerely,",
    "Dr M. Singh, Consultant Respiratory Physician",
]


# ============================================================================
# DOC 3 - A&E Discharge Summary, 09 Nov 2024
# THE FLIP-BACK: patient presents with acute exacerbation, treated and
# discharged. Discharge document records 'mild asthma, no preventer
# previously, started inhaler today' - missing entirely that respiratory
# clinic had reclassified to moderate persistent and started beclometasone
# 3 months earlier. Severity tag reverts; the patient's preventer history
# is misrepresented as 'new today'.
# ============================================================================
doc3_body = [
    "<b>St James's Hospital &mdash; Emergency Department</b>",
    "Date: 09 Nov 2024",
    "<b>DISCHARGE SUMMARY</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 33)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Presentation:</b> Self-presented with 2-day history of worsening shortness of breath "
    "and audible wheeze. Increased salbutamol use (every 2 hours) with diminishing response. "
    "Symptoms began following an upper respiratory tract infection 5 days ago.",
    "",
    "<b>Past Medical History:</b>",
    "&bull; <b>Mild asthma</b> (childhood-onset)",
    "&bull; Allergic rhinitis",
    "",
    "<b>Examination on arrival:</b> RR 26, SpO2 92% on air, HR 112, BP 124/76, "
    "afebrile. Chest: widespread polyphonic wheeze, prolonged expiratory phase, "
    "accessory muscle use. PEFR 180 L/min on arrival (39% of personal best).",
    "",
    "<b>Diagnosis:</b> Acute moderate asthma exacerbation, viral-triggered.",
    "",
    "<b>Treatment given:</b> Salbutamol 5 mg nebulised x2 with ipratropium 500 mcg added to "
    "second neb. Oral prednisolone 40 mg administered. Reassessed at 60 minutes: PEFR "
    "improved to 320 L/min, SpO2 97% on air, RR 20.",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Discharge medications:</b>",
    "&bull; Prednisolone 40 mg OD for 5 days (3 days remaining)",
    "&bull; Salbutamol 100 mcg MDI &mdash; 2 puffs QDS regularly for 48 hours then PRN",
    "&bull; <b>Started beclometasone 200 mcg BD today as new preventer inhaler</b>",
    "",
    "<b>Follow-up:</b> GP review within 48 hours. Patient advised inhaler technique "
    "should be reviewed at GP appointment. No respiratory clinic follow-up arranged.",
    "",
    "Dr P. Khan, Emergency Medicine Registrar",
]


# ============================================================================
# Write all three PDFs
# ============================================================================
pdf1 = write_pdf("01_GP_Asthma_Review_Bennett_11Mar2024.pdf", doc1_body)
pdf2 = write_pdf("02_Respiratory_Clinic_Bennett_22Aug2024.pdf", doc2_body)
pdf3 = write_pdf("03_AE_Discharge_Bennett_09Nov2024.pdf", doc3_body)
print(f"PDFs written: {pdf1.name}, {pdf2.name}, {pdf3.name}")


# ============================================================================
# gold_flags.json
# ============================================================================
gold_flags = {
    "patient_id": PATIENT_ID,
    "patient_name": NAME,
    "patient_dob": DOB,
    "patient_nhs": NHS,
    "construction_date": "2026-06-28",
    "schema_version": "v2_three_tier",
    "design_principle": (
        "Asthma case with planted severity-classification contradiction. GP "
        "(doc 01, Mar 2024) classifies as mild intermittent on reliever-only "
        "regime. Respiratory clinic (doc 02, Aug 2024) reclassifies as "
        "moderate persistent with full justification (ACT, PEFR variability, "
        "FEV1) and initiates beclometasone preventer. A&E (doc 03, Nov 2024) "
        "records the asthma as 'mild' again and labels beclometasone as 'new "
        "today', erasing the August initiation. Documents span 8 months "
        "across primary, secondary, and emergency care settings, targeting "
        "pairwise content-token Jaccard < 0.5."
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
            "category": "CLASSIFICATION_CONFLICT",
            "clinical_subject": "asthma severity",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 (respiratory clinic, Aug 2024) reclassifies asthma as moderate "
                "persistent with explicit justification (ACT 15/25, PEFR variability 22%, "
                "FEV1 72% predicted, reversibility 12%). Doc 03 (A&E, Nov 2024) records "
                "asthma as 'mild' in the past medical history. The classification has "
                "regressed without clinical justification. Missing this is an error - "
                "severity classification drives the asthma management ladder; misclassifying "
                "moderate persistent as mild leads to under-treatment and avoidable exacerbations."
            ),
            "expected_source_document": "02_Respiratory_Clinic_Bennett_22Aug2024.pdf"
        },
        {
            "tier": 1,
            "category": "MEDICATION_HISTORY_ERROR",
            "clinical_subject": "beclometasone",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 (Aug 2024) initiates beclometasone 200 mcg BD as preventer with full "
                "counselling and follow-up plan. Doc 03 (Nov 2024) labels beclometasone as 'started "
                "today as new preventer', erasing the 3-month preceding history. This is a "
                "medication-history error: the patient has been on the preventer for 3 months "
                "before A&E presentation. If treated as a newly-initiated drug, response monitoring "
                "and titration timelines reset incorrectly."
            ),
            "expected_source_document": "03_AE_Discharge_Bennett_09Nov2024.pdf"
        },
        {
            "tier": 1,
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "asthma",
            "severity": "MEDIUM",
            "rationale": (
                "Last respiratory-specific review is doc 02 (22 Aug 2024). Doc 03 explicitly "
                "states 'no respiratory clinic follow-up arranged' after the exacerbation. The "
                "12-week respiratory clinic follow-up planned in doc 02 has not been documented. "
                "At evaluation time (mid-2026) this is well over the threshold for a patient who "
                "has had an exacerbation requiring oral steroids."
            ),
            "expected_source_document": "02_Respiratory_Clinic_Bennett_22Aug2024.pdf"
        },
        {
            "tier": 2,
            "category": "AI_TREATMENT_INADEQUATE_RESPONSE",
            "clinical_subject": "asthma exacerbation",
            "severity": "MEDIUM",
            "rationale": (
                "Patient on beclometasone 200 mcg BD preventer (started Aug 2024) presents with "
                "moderate exacerbation in Nov 2024. Per GINA step-up logic, an exacerbation on "
                "step 3 therapy suggests step-up to ICS/LABA combination. Doc 02 explicitly notes "
                "'if poor response, consider step-up to ICS/LABA combination'. The Nov exacerbation "
                "is arguably that trigger. Acceptable for the system to flag; acceptable to omit "
                "because it requires reading the doc-02 plan."
            ),
            "needs_clinician_validation": True
        },
        {
            "tier": 2,
            "category": "AI_INVESTIGATION_NO_RESULT",
            "clinical_subject": "pefr diary",
            "severity": "LOW",
            "rationale": (
                "Doc 02 requests an 8-week PEFR diary continuation. Doc 03 (12 weeks later) makes "
                "no mention of the PEFR diary results or whether the patient continued recording. "
                "Acceptable to flag; acceptable to omit as cross-document inference."
            ),
            "needs_clinician_validation": True
        }
    ]
}

(OUT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)
print(f"gold_flags.json written: {len(gold_flags['gold_flags'])} gold flags")


# ============================================================================
# gold_contradictions.json
# ============================================================================
gold_contradictions = {
    "patient_id": PATIENT_ID,
    "construction_date": "2026-06-28",
    "schema_version": "v2_claim_based_matching",
    "match_rule": (
        "A gold contradiction is satisfied if the agent emits a contradiction where one side "
        "cites any document in claim_a_sources and the other side cites any document in "
        "claim_b_sources. The clinical fact is what matters, not which specific document-pair "
        "is cited."
    ),
    "gold_contradictions": [
        {
            "category": "SEVERITY_CLASSIFICATION",
            "severity": "HIGH",
            "claim_a": "asthma classified as moderate persistent (GINA step 3) with explicit clinical justification",
            "claim_b": "asthma classified as mild",
            "claim_a_sources": [
                "02_Respiratory_Clinic_Bennett_22Aug2024.pdf"
            ],
            "claim_b_sources": [
                "01_GP_Asthma_Review_Bennett_11Mar2024.pdf",
                "03_AE_Discharge_Bennett_09Nov2024.pdf"
            ],
            "explanation": (
                "Doc 01 (Mar 2024) classifies the patient as mild intermittent based on then-"
                "current symptom pattern. Doc 02 (Aug 2024) reclassifies as moderate persistent "
                "with comprehensive justification (ACT 15/25, PEFR variability 22%, FEV1 72%, "
                "reversibility 12%). Doc 03 (Nov 2024) records mild again in the past medical "
                "history without acknowledging the Aug reclassification. The contradiction is "
                "between the specialist reclassification (claim_a) and the primary/emergency-care "
                "record (claim_b). Doc 01's mild label is historically defensible (it pre-dates "
                "the reclassification); doc 03's mild label is the error."
            ),
            "rationale_for_planting": (
                "Tests whether the contradiction agent detects disease-classification disagreement "
                "- a distinct shape from medication-list (patient_006) or allergy (patient_001) "
                "contradictions. Disease classification drives treatment ladders, so misclassification "
                "is a high-stakes EHR failure. The 1-vs-2 source split tests that the agent can "
                "identify the specialist reclassification as the authoritative claim, even though "
                "two documents support the alternative. Tests claim_a_sources=specialist vs "
                "claim_b_sources={primary, emergency} matching."
            )
        },
        {
            "category": "MEDICATION_HISTORY",
            "severity": "HIGH",
            "claim_a": "patient on beclometasone 200 mcg BD as established preventer since Aug 2024",
            "claim_b": "beclometasone started today (Nov 2024) as new preventer",
            "claim_a_sources": [
                "02_Respiratory_Clinic_Bennett_22Aug2024.pdf"
            ],
            "claim_b_sources": [
                "03_AE_Discharge_Bennett_09Nov2024.pdf"
            ],
            "explanation": (
                "Doc 02 initiates beclometasone 200 mcg BD as preventer with explicit start. "
                "Doc 03 (3 months later) describes beclometasone as 'started today as new "
                "preventer inhaler'. These are contradictory claims about whether the patient "
                "is preventer-naive at the time of A&E presentation. Realistic of how A&E "
                "documentation often defaults to the patient's primary care record rather than "
                "cross-checking specialist letters."
            ),
            "rationale_for_planting": (
                "A second contradiction in the same chart, distinct in category from the severity "
                "contradiction. Tests that the agent doesn't conflate two distinct disagreements "
                "into one. Also tests dose-stripped matching ('beclometasone' vs 'beclometasone "
                "200 mcg BD') under Path B normalisation."
            )
        }
    ]
}

(OUT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)
print(f"gold_contradictions.json written: {len(gold_contradictions['gold_contradictions'])} contradiction(s)")


# ============================================================================
# README.md
# ============================================================================
readme = """# patient_009 - Lauren Bennett

**Construction date:** 2026-06-28
**Domain:** asthma (respiratory)
**Type:** CONTRADICTION case (planted severity-classification contradiction)

## Patient

- Name: Lauren Bennett
- DOB: 1991-04-18 (age 32 at first document)
- NHS: 999 900 0009
- Sex: F

## Clinical story

A 32-year-old woman with childhood-onset asthma and allergic rhinitis. GP
annual review (Mar 2024) classifies her asthma as mild intermittent based on
infrequent salbutamol use and a high ACT score. Five months later, after
symptom escalation, the respiratory clinic reclassifies as moderate persistent
based on ACT, PEFR variability, and spirometry, and initiates beclometasone
preventer. Three months after that, she presents to A&E with a viral-triggered
exacerbation - and the A&E discharge summary records her asthma as 'mild' in
the past medical history and labels her beclometasone (which she's been on
for 3 months) as 'started today as new preventer'.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 11 Mar 2024 | GP Asthma Annual Review | Mild intermittent, salbutamol PRN, ACT 22/25, PEFR 83% predicted |
| 02 | 22 Aug 2024 | Respiratory Clinic Letter | **Reclassified moderate persistent**, **beclometasone 200 mcg BD initiated**, ACT 15/25, PEFR variability 22%, FEV1 72% |
| 03 | 09 Nov 2024 | A&E Discharge Summary | Moderate exacerbation, **records asthma as mild**, **beclometasone described as 'new today'** |

## The planted contradictions

**Contradiction 1: severity classification.**
Doc 02 explicitly reclassifies the asthma as moderate persistent (GINA step 3)
with comprehensive justification. Doc 03 reverts to 'mild' in the past medical
history without acknowledging the Aug reclassification.

**Contradiction 2: medication history.**
Doc 02 initiates beclometasone 200 mcg BD in Aug 2024. Doc 03 (Nov 2024)
describes beclometasone as 'started today as new preventer', erasing the
3-month established history.

Both are realistic of how A&E records frequently default to the patient's
self-reported severity and inherited medication list rather than cross-checking
recent specialist correspondence. Under-classification leads directly to
under-treatment.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `CLASSIFICATION_CONFLICT` on `asthma severity`
- HIGH `MEDICATION_HISTORY_ERROR` on `beclometasone`
- MEDIUM `OVERDUE_FOLLOWUP` on `asthma`
- Plus 2 tier-2 acceptable-credit flags (treatment-inadequate-response, PEFR diary)

## What this tests

- Contradiction agent: disease-classification contradictions (distinct from
  medication-reconciliation in patient_006 and allergy-status in patient_001)
- Contradiction agent: 1-vs-2 source asymmetry (specialist claim vs
  primary/emergency claim) - tests that specialist reclassification is
  identified as the authoritative position
- Contradiction agent: same-chart multiple contradictions (severity AND
  medication-history) without conflation
- Flag agent: classification-conflict rule firing on documented severity disagreement
- Flag agent: medication-history-error rule firing on preventer history erasure
- Flag agent: overdue-followup on respiratory follow-up gap
- Matcher: dose-stripped matching (`beclometasone` vs `beclometasone 200 mcg BD`)
  under Path B normalisation
"""

(OUT_DIR / "README.md").write_text(readme, encoding="utf-8")
print(f"README.md written: {len(readme)} chars")


print()
print("=" * 60)
print(f"patient_009 build complete: {OUT_DIR}")
print("=" * 60)
files = sorted(OUT_DIR.iterdir())
for f in files:
    print(f"  {f.name:<48} {f.stat().st_size:>6} bytes")
