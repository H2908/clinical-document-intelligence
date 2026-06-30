"""Build patient_013 - CKD case with planted staging-classification contradiction.

The contradiction: GP (doc 01, Jan 2024) records CKD stage 3a (eGFR 52).
Renal clinic (doc 02, May 2024) measures eGFR 28 and reclassifies to CKD
stage 4 with explicit action plan (vaccination, vascular access discussion,
low-K diet referral). GP locum (doc 03, Oct 2024) records CKD stage 3a
again with eGFR 35 - both the stage label AND the eGFR value contradict
the May renal clinic finding.

This is realistic of how locum GPs and rotational staff fail to incorporate
specialist reclassifications - the patient's chart accumulates outdated
stage tags even after the renal team has moved them to a different management
pathway.

Tests Path B's measurement-value preservation: eGFR 28 and eGFR 35 are both
eGFR measurements with clinically meaningful values that MUST NOT be merged
into a single 'egfr' identity. The dose-stripping regex requires a unit
token (mg/mcg/g/ml/units/iu) which eGFR lacks, so the values are preserved
naturally.

Three PDFs + gold flags + gold contradictions + README, written atomically.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import json

OUT_DIR = Path("data/synthetic/documents/patient_013")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Shared patient identity ----
NAME = "Christopher Walsh"
DOB = "1959-09-27"
NHS = "999 130 0013"
ADDRESS = "8 Riverdale Crescent, Sheffield, S7 1QH"
SEX = "M"
PATIENT_ID = "patient_013"


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
# DOC 1 - GP CKD Annual Review, 16 Jan 2024
# Establishes baseline: CKD STAGE 3A, eGFR 52, on ramipril + atorvastatin
# for cardiovascular risk reduction.
# ============================================================================
doc1_body = [
    "<b>Riverdale Surgery</b>",
    "Date: 16 Jan 2024",
    "<b>CKD ANNUAL REVIEW</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 64)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; <b>Chronic kidney disease stage 3a</b> (ICD-10: N18.30) &mdash; diagnosed 2021-08-15",
    "&bull; Type 2 diabetes mellitus (ICD-10: E11.9) &mdash; diagnosed 2014-06-04",
    "&bull; Hypertension (ICD-10: I10) &mdash; diagnosed 2011-09-22",
    "&bull; Hypercholesterolaemia (ICD-10: E78.0)",
    "",
    "<b>Current Medications:</b>",
    "&bull; Metformin 1 g BD &mdash; started 2014-07-01",
    "&bull; Ramipril 10 mg OD &mdash; started 2011-10-12 (dose increased 2019)",
    "&bull; Amlodipine 5 mg OD &mdash; started 2018-03-04",
    "&bull; Atorvastatin 40 mg ON &mdash; started 2015-04-20",
    "",
    "<b>Allergies:</b> NKDA &mdash; no known drug allergies recorded.",
    "",
    "<b>Examination:</b> BP 142/86, HR 74 regular. Weight 84 kg (BMI 28.1). "
    "No peripheral oedema. Foot examination unremarkable.",
    "",
    "<b>Investigations (today):</b> eGFR 52 mL/min/1.73m&sup2; (stable from 50 in July 2023); "
    "creatinine 128 &micro;mol/L; ACR 4.2 mg/mmol (mild albuminuria, A2 category); "
    "HbA1c 7.4%; potassium 4.6; bicarbonate 23; urinalysis: no blood, trace protein.",
    "",
    "<b>Assessment:</b> CKD stage 3a with mild albuminuria, stable. T2DM moderately controlled. "
    "BP slightly above target for CKD/diabetes. ACEi-treated.",
    "",
    "<b>Plan:</b>",
    "&bull; Continue current medications",
    "&bull; Lifestyle reinforcement: low salt, weight reduction target 5%",
    "&bull; Repeat U&amp;E, ACR, HbA1c in 6 months",
    "&bull; Consider amlodipine uptitration to 10 mg if BP persistently &gt;140/85 at next review",
    "&bull; Annual flu vaccine recommended (October)",
    "",
    "Dr S. Henderson, GP Partner",
]


# ============================================================================
# DOC 2 - Renal Clinic Letter, 14 May 2024
# THE RECLASSIFICATION: eGFR drops to 28, reclassified CKD stage 4 with
# full management plan. Vaccination updated, vascular access discussion
# initiated, dietetics referral.
# ============================================================================
doc2_body = [
    "<b>Sheffield Teaching Hospitals &mdash; Renal Outpatient Department</b>",
    "Date: 14 May 2024",
    "<b>CLINIC LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 64)",
    f"NHS Number: {NHS}",
    "",
    "Dear Dr Henderson,",
    "",
    "Thank you for referring Mr Walsh for renal assessment following his recent decline in "
    "kidney function. I reviewed him today in the low-clearance clinic.",
    "",
    "<b>History:</b> CKD known since 2021, previously stage 3a. Presented to GP in late March "
    "with fatigue and reduced exercise tolerance over 8 weeks. No haematuria, no flank pain, "
    "no recent NSAID use, no IV contrast exposure. Adherent with ramipril and other medications. "
    "No recent infections.",
    "",
    "<b>Examination:</b> BP 156/88, HR 76. Weight 83 kg. Trace ankle oedema bilaterally. "
    "JVP not elevated. Chest clear. No bruits.",
    "",
    "<b>Investigations (today, repeated from GP April panel):</b> "
    "<b>eGFR 28 mL/min/1.73m&sup2;</b> (down from 52 in January); "
    "creatinine 198 &micro;mol/L (up from 128); urea 14.2; potassium 5.1 (upper limit); "
    "bicarbonate 19 (mild metabolic acidosis); haemoglobin 108 g/L (anaemia of CKD); "
    "phosphate 1.42 (mildly elevated); calcium 2.28 (adjusted, low-normal); "
    "PTH 11.2 pmol/L (elevated); ACR 22 mg/mmol (now A3, moderate albuminuria); "
    "renal ultrasound: bilateral parenchymal changes consistent with chronic disease, no obstruction.",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Assessment:</b> <b>CKD has progressed to stage 4</b> (eGFR 28). Aetiology: diabetic "
    "nephropathy + hypertensive nephrosclerosis. Patient now has CKD-MBD picture emerging "
    "(elevated PTH, mild hyperphosphataemia) and renal anaemia. Trajectory suggests renal "
    "replacement therapy planning within 18-24 months. Discussed implications with patient "
    "and his wife at length.",
    "",
    "<b>Plan:</b>",
    "&bull; <b>Reclassification: CKD stage 4</b> &mdash; please update practice record",
    "&bull; Continue ramipril 10 mg OD &mdash; monitor potassium closely; reduce if K&gt;5.5",
    "&bull; Hold metformin and review for alternative agent given eGFR 28 (close to contraindication threshold of 30)",
    "&bull; Pneumococcal vaccination today; ensure annual flu and 5-yearly Hep B series initiated",
    "&bull; Dietetics referral &mdash; low potassium, low phosphate dietary education",
    "&bull; Anaemia workup: iron studies, B12/folate; consider ESA if Hb &lt;100",
    "&bull; Initial discussion of vascular access (AV fistula) given trajectory &mdash; not for action yet but for planning",
    "&bull; Repeat bloods in 6 weeks at GP",
    "&bull; Renal clinic follow-up in 3 months",
    "",
    "Yours sincerely,",
    "Dr R. Patel, Consultant Nephrologist",
]


# ============================================================================
# DOC 3 - GP Locum Review, 22 Oct 2024
# THE FLIP-BACK: locum GP records CKD stage 3a with eGFR 35. The stage
# label has reverted AND the eGFR value disagrees with the May renal
# clinic finding (eGFR 28). The doc 03 eGFR 35 is also a separate
# concrete value that's neither what doc 01 nor doc 02 recorded.
# ============================================================================
doc3_body = [
    "<b>Riverdale Surgery</b>",
    "Date: 22 Oct 2024",
    "<b>GP CONSULTATION (Locum)</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 65)",
    f"NHS Number: {NHS}",
    "",
    "<b>Reason for visit:</b> Routine medication review and BP check. Patient also requests "
    "advice on persistent fatigue.",
    "",
    "<b>Active Medical Conditions (per practice record):</b>",
    "&bull; <b>Chronic kidney disease stage 3a</b>",
    "&bull; Type 2 diabetes mellitus",
    "&bull; Hypertension",
    "&bull; Hypercholesterolaemia",
    "",
    "<b>Current Medications:</b>",
    "&bull; Metformin 1 g BD",
    "&bull; Ramipril 10 mg OD",
    "&bull; Amlodipine 5 mg OD",
    "&bull; Atorvastatin 40 mg ON",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Examination:</b> BP 148/86, HR 78. Weight 82 kg. Mild bilateral pedal oedema. "
    "Patient looks tired but otherwise well.",
    "",
    "<b>Investigations (today):</b> eGFR 35 mL/min/1.73m&sup2;; creatinine 162 &micro;mol/L; "
    "HbA1c 7.8%; potassium 5.2 (high-normal); ACR not repeated; "
    "haemoglobin 106 g/L (chronic anaemia).",
    "",
    "<b>Assessment:</b> CKD stage 3a stable on current medications. Diabetes moderately "
    "controlled. BP at upper end of target range. Fatigue likely multifactorial &mdash; chronic "
    "anaemia, age, possible sleep issues.",
    "",
    "<b>Plan:</b>",
    "&bull; Continue current medications",
    "&bull; Repeat U&amp;E in 6 months",
    "&bull; Iron studies and ferritin given anaemia &mdash; arrange via routine bloods",
    "&bull; Reinforce hydration and salt restriction",
    "&bull; Routine review in 6 months",
    "",
    "Dr L. Park (locum)",
]


# ============================================================================
# Write all three PDFs
# ============================================================================
pdf1 = write_pdf("01_GP_CKD_Review_Walsh_16Jan2024.pdf", doc1_body)
pdf2 = write_pdf("02_Renal_Clinic_Walsh_14May2024.pdf", doc2_body)
pdf3 = write_pdf("03_GP_Locum_Walsh_22Oct2024.pdf", doc3_body)
print(f"PDFs written: {pdf1.name}, {pdf2.name}, {pdf3.name}")


# ============================================================================
# gold_flags.json
# ============================================================================
gold_flags = {
    "patient_id": PATIENT_ID,
    "patient_name": NAME,
    "patient_dob": DOB,
    "patient_nhs": NHS,
    "construction_date": "2026-06-29",
    "schema_version": "v2_three_tier",
    "design_principle": (
        "CKD case with planted staging-classification contradiction. GP "
        "(doc 01, Jan 2024) records CKD stage 3a with eGFR 52. Renal clinic "
        "(doc 02, May 2024) measures eGFR 28 and reclassifies as CKD stage 4 "
        "with comprehensive management plan (vaccination, vascular access "
        "planning, low-K diet, anaemia workup, metformin hold). GP locum "
        "(doc 03, Oct 2024) records CKD stage 3a again with eGFR 35 - both "
        "the stage label and the eGFR value disagree with the May renal "
        "clinic finding. Realistic of how locum staff fail to incorporate "
        "specialist reclassifications. Documents span 9 months across "
        "primary and secondary care, targeting pairwise content-token "
        "Jaccard < 0.5. Exercises Path B measurement-value preservation: "
        "eGFR values must NOT collapse under normalisation."
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
            "clinical_subject": "ckd stage",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 (renal clinic, May 2024) explicitly reclassifies CKD as stage 4 "
                "(eGFR 28) with comprehensive justification and updated management plan. "
                "Doc 03 (GP locum, Oct 2024) records CKD stage 3a in the active conditions "
                "list. The classification has regressed without clinical justification. "
                "Missing this is unambiguously an error - stage 4 vs stage 3a drives "
                "fundamentally different management (vaccination programme, vascular access "
                "planning, dietitian referral, metformin contraindication assessment, "
                "transplant workup eligibility). The locum has rolled back the renal team's "
                "reclassification."
            ),
            "expected_source_document": "02_Renal_Clinic_Walsh_14May2024.pdf"
        },
        {
            "tier": 1,
            "category": "INVESTIGATION_VALUE_CONFLICT",
            "clinical_subject": "egfr",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 records eGFR 28 (May 2024). Doc 03 records eGFR 35 (Oct 2024) without "
                "any documented intervention that would explain the apparent improvement. eGFR "
                "improvements from 28 to 35 over 5 months are clinically implausible without "
                "specific intervention (hydration correction post-AKI, removal of nephrotoxin, "
                "etc) - none of which are documented. This is either a measurement error, a "
                "lab/transcription error, or a different eGFR-estimating equation in use. "
                "Either way, the discrepancy is clinically meaningful and should be flagged."
            ),
            "expected_source_document": "03_GP_Locum_Walsh_22Oct2024.pdf"
        },
        {
            "tier": 1,
            "category": "MEDICATION_RECONCILIATION",
            "clinical_subject": "metformin",
            "severity": "HIGH",
            "rationale": (
                "Doc 02 (renal clinic, May 2024) explicitly says 'Hold metformin and review "
                "for alternative agent given eGFR 28 (close to contraindication threshold of "
                "30)'. Doc 03 (GP locum, Oct 2024) shows metformin 1 g BD still on the "
                "current medication list with no mention of the renal team's hold instruction. "
                "Metformin in stage 4 CKD carries lactic acidosis risk. The hold instruction "
                "has not been actioned."
            ),
            "expected_source_document": "02_Renal_Clinic_Walsh_14May2024.pdf"
        },
        {
            "tier": 1,
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "chronic kidney disease",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 02 plans renal clinic follow-up at 3 months (August 2024). No record of "
                "this follow-up exists in the document set. Doc 03 (October locum visit) "
                "makes no reference to the renal clinic plan and arranges only routine GP "
                "follow-up in 6 months. At evaluation time the patient with progressive CKD "
                "stage 4 has had no specialist input in over a year."
            ),
            "expected_source_document": "02_Renal_Clinic_Walsh_14May2024.pdf"
        },
        {
            "tier": 2,
            "category": "AI_TREATMENT_INADEQUATE_RESPONSE",
            "clinical_subject": "anaemia of ckd",
            "severity": "MEDIUM",
            "rationale": (
                "Doc 02 documents Hb 108 g/L with plan for iron studies and ESA consideration "
                "if Hb<100. Doc 03 (5 months later) records Hb 106 g/L with only an iron "
                "studies request - no progression of the anaemia workup or ESA discussion. "
                "Acceptable for the system to flag inadequate response to the doc-02 plan; "
                "acceptable to omit as it requires reading the doc-02 plan to recognise."
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
    "construction_date": "2026-06-29",
    "schema_version": "v2_claim_based_matching",
    "match_rule": (
        "A gold contradiction is satisfied if the agent emits a contradiction where one side "
        "cites any document in claim_a_sources and the other side cites any document in "
        "claim_b_sources. The clinical fact is what matters, not which specific document-pair "
        "is cited."
    ),
    "gold_contradictions": [
        {
            "category": "STAGE_CLASSIFICATION",
            "severity": "HIGH",
            "claim_a": "CKD stage 4 (eGFR 28)",
            "claim_b": "CKD stage 3a",
            "claim_a_sources": [
                "02_Renal_Clinic_Walsh_14May2024.pdf"
            ],
            "claim_b_sources": [
                "01_GP_CKD_Review_Walsh_16Jan2024.pdf",
                "03_GP_Locum_Walsh_22Oct2024.pdf"
            ],
            "explanation": (
                "Doc 01 (Jan 2024) classifies as CKD stage 3a based on eGFR 52 - historically "
                "defensible at that point. Doc 02 (May 2024) reclassifies as CKD stage 4 with "
                "comprehensive justification (eGFR 28, repeated measurement, complete CKD-MBD "
                "and anaemia workup, ultrasound). Doc 03 (Oct 2024) records CKD stage 3a "
                "again, rolling back the specialist reclassification. The contradiction is "
                "between the renal clinic (claim_a) and the GP records (claim_b). Doc 01's "
                "stage 3a is historical truth at the time; doc 03's stage 3a is the error "
                "that does not incorporate the May reclassification."
            ),
            "rationale_for_planting": (
                "Tests whether the contradiction agent detects lab-value-driven disease-stage "
                "disagreement. Distinct from patient_009's text-narrative severity contradiction "
                "(mild/moderate/severe asthma) because CKD staging is anchored to eGFR cutoffs "
                "(stage 3a: 45-59, stage 3b: 30-44, stage 4: 15-29). The agent should recognise "
                "that 'stage 3a' and 'stage 4' are concrete, lab-anchored categories whose "
                "disagreement is a substantive clinical contradiction, not paraphrase. Also "
                "tests 1-vs-2 source split (specialist vs two primary care records)."
            )
        },
        {
            "category": "INVESTIGATION_VALUE",
            "severity": "MEDIUM",
            "claim_a": "eGFR 28 mL/min/1.73m2 (May 2024 renal clinic)",
            "claim_b": "eGFR 35 mL/min/1.73m2 (Oct 2024 GP locum)",
            "claim_a_sources": [
                "02_Renal_Clinic_Walsh_14May2024.pdf"
            ],
            "claim_b_sources": [
                "03_GP_Locum_Walsh_22Oct2024.pdf"
            ],
            "explanation": (
                "Both measurements are 'current eGFR' but recorded 5 months apart. eGFR "
                "increases of this magnitude in established CKD with no documented intervention "
                "are clinically implausible. The contradiction is not the time gap (CKD trajectory "
                "can vary) but the absence of an intervening clinical narrative explaining the "
                "apparent improvement. Either lab error, measurement-equation change, or "
                "transcription error - all clinically meaningful."
            ),
            "rationale_for_planting": (
                "Tests measurement-value contradictions where the values themselves are the "
                "contradiction (not derived classifications). Also tests Path B's measurement-"
                "value preservation: the matcher must NOT collapse eGFR 28 and eGFR 35 into a "
                "single 'egfr' identity because the dose-stripping regex requires a unit token "
                "(mg/mcg/g/ml/units/iu) which eGFR lacks. If Path B over-merges here, both "
                "values disappear into one and the contradiction is invisible to the matcher."
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
readme = """# patient_013 - Christopher Walsh

**Construction date:** 2026-06-29
**Domain:** chronic kidney disease (CKD)
**Type:** CONTRADICTION case (planted staging-classification contradiction)

## Patient

- Name: Christopher Walsh
- DOB: 1959-09-27 (age 64 at first document)
- NHS: 999 130 0013
- Sex: M

## Clinical story

A 64-year-old man with established CKD on a background of type 2 diabetes
and long-standing hypertension - the most common UK CKD aetiology profile.
GP annual review (Jan 2024) records CKD stage 3a with eGFR 52, stable
trajectory, treated with ramipril and standard cardiovascular risk
management. Renal clinic (May 2024) measures eGFR 28 and reclassifies as
CKD stage 4 with comprehensive management changes: vaccination programme,
metformin hold, dietetics referral, anaemia workup, vascular access
discussion. GP locum (Oct 2024) records CKD stage 3a again with eGFR 35,
metformin still active, no reference to the renal clinic plan.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 16 Jan 2024 | GP CKD Annual Review | **CKD stage 3a**, eGFR 52, ramipril 10 mg OD, stable trajectory |
| 02 | 14 May 2024 | Renal Clinic Letter | **eGFR 28, reclassified CKD stage 4**, hold metformin, dietetics referral, vaccinations, vascular access discussion |
| 03 | 22 Oct 2024 | GP Locum Consultation | **CKD stage 3a** again, **eGFR 35**, metformin still on list, no reference to renal clinic plan |

## The planted contradictions

**Contradiction 1: stage classification.**
Doc 02 reclassifies as CKD stage 4 (eGFR 28) with full justification.
Doc 03 records CKD stage 3a, ignoring the specialist reclassification.
Doc 01's stage 3a is historically defensible; doc 03's stage 3a is the error.

**Contradiction 2: eGFR investigation value.**
Doc 02 records eGFR 28. Doc 03 records eGFR 35 five months later with no
documented intervention. Implausible improvement; likely measurement,
equation, or transcription discrepancy. Either way, clinically meaningful.

Realistic of how locum GPs and rotational staff fail to incorporate
specialist reclassifications - the patient's primary care chart accumulates
outdated stage tags even after the renal team has moved them to a different
management pathway. The downstream cost is real: stage 4 patients need
vaccination, vascular access planning, dietetics input, and metformin
contraindication review. Recording stage 3a means none of those happen.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `CLASSIFICATION_CONFLICT` on `ckd stage`
- HIGH `INVESTIGATION_VALUE_CONFLICT` on `egfr`
- HIGH `MEDICATION_RECONCILIATION` on `metformin` (hold instruction not actioned)
- MEDIUM `OVERDUE_FOLLOWUP` on `chronic kidney disease`
- Plus 1 tier-2 acceptable-credit flag on anaemia-of-CKD inadequate response

## What this tests

- Contradiction agent: lab-value-anchored classification contradictions
  (distinct from patient_009's narrative-text severity contradiction)
- Contradiction agent: 1-vs-2 source split (specialist single doc vs two
  primary care docs); tests that the agent identifies the specialist as
  authoritative when its position is clinically and quantitatively justified
- Contradiction agent: measurement-value contradictions where the numbers
  themselves are the disagreement (eGFR 28 vs eGFR 35)
- Flag agent: classification-conflict rule firing on CKD stage disagreement
- Flag agent: investigation-value-conflict rule firing on eGFR disagreement
- Flag agent: medication-reconciliation rule firing on metformin hold
  instruction not actioned
- **Matcher: Path B measurement-value preservation** - the matcher must
  NOT collapse `egfr 28` and `egfr 35` into a single `egfr` identity.
  The dose-stripping regex requires a unit token (mg/mcg/g/ml/units/iu)
  which eGFR lacks, so the values are preserved naturally. If this
  preservation fails (e.g., a future matcher change), the contradiction
  becomes invisible at evaluation time.
"""

(OUT_DIR / "README.md").write_text(readme, encoding="utf-8")
print(f"README.md written: {len(readme)} chars")


print()
print("=" * 60)
print(f"patient_013 build complete: {OUT_DIR}")
print("=" * 60)
files = sorted(OUT_DIR.iterdir())
for f in files:
    print(f"  {f.name:<48} {f.stat().st_size:>6} bytes")
