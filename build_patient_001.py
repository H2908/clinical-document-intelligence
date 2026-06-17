"""Build patient_001 — cardiology + CKD case with designed allergy contradiction.

Three PDFs + gold flags + gold contradictions + README, written atomically.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import json

OUT_DIR = Path("data/synthetic/documents/patient_001")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Shared patient identity ----
NAME = "Margaret Thompson"
DOB = "1954-08-15"
NHS = "999 100 0001"
ADDRESS = "14 Beech Avenue, Manchester, M14 5RT"
SEX = "F"
PATIENT_ID = "patient_001"


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
# DOC 1 — GP Referral Letter, 12 Jan 2024 — says NKDA
# ============================================================================
doc1_body = [
    "<b>Whitfield Surgery</b>",
    "Date: 12 Jan 2024",
    "<b>REFERRAL LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 69)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Active Medical Conditions:</b>",
    "&bull; Chronic heart failure with reduced ejection fraction (ICD-10: I50.22) &mdash; diagnosed 2022-03-14",
    "&bull; Chronic kidney disease stage 3b (ICD-10: N18.32) &mdash; diagnosed 2021-11-09",
    "&bull; Hypertension (ICD-10: I10) &mdash; diagnosed 2015-04-22",
    "&bull; Type 2 diabetes mellitus (ICD-10: E11.9) &mdash; diagnosed 2017-08-30",
    "",
    "<b>Current Medications:</b>",
    "&bull; Ramipril 5 mg &mdash; 5 mg OD (started 2022-04-01)",
    "&bull; Bisoprolol 5 mg &mdash; 5 mg OD (started 2022-04-01)",
    "&bull; Furosemide 40 mg &mdash; 40 mg OD (started 2023-05-12)",
    "&bull; Metformin 500 mg &mdash; 1 g BD (started 2017-09-15)",
    "&bull; Atorvastatin 40 mg &mdash; 40 mg ON (started 2019-02-03)",
    "",
    "<b>Allergies:</b> NKDA &mdash; no known drug allergies recorded.",
    "",
    "<b>Reason for Referral:</b>",
    "Referring to cardiology for review of worsening exertional dyspnoea over the past 6 weeks. "
    "Recent eGFR 32 mL/min/1.73m&sup2;. Patient reports orthopnoea and ankle swelling. "
    "Echocardiogram requested; please review and advise on heart failure therapy optimisation.",
]

# ============================================================================
# DOC 2 — Cardiology Clinic Letter, 28 Feb 2024 — DOCUMENTS PENICILLIN ALLERGY
# (the contradiction with doc 1)
# ============================================================================
doc2_body = [
    "<b>Manchester Royal Infirmary &mdash; Cardiology Department</b>",
    "Date: 28 Feb 2024",
    "<b>CLINIC LETTER</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 69)",
    f"NHS Number: {NHS}",
    "",
    "Dear Dr Whitfield,",
    "",
    "Thank you for referring Mrs Thompson. I reviewed her today in the heart failure clinic.",
    "",
    "<b>History:</b> 6-week history of worsening exertional dyspnoea, NYHA class III. Orthopnoea on two pillows. "
    "Bilateral ankle oedema. No chest pain or palpitations. No recent admissions.",
    "",
    "<b>Examination:</b> BP 138/82, HR 72 regular. JVP elevated 4 cm. Bibasal crackles. Pitting oedema to mid-shin bilaterally.",
    "",
    "<b>Investigations:</b> Echocardiogram (today) confirms severe LV systolic dysfunction with LVEF 28% (down from 35% in 2022). "
    "Moderate mitral regurgitation. ECG: sinus rhythm, LBBB. Bloods: Na 138, K 4.6, urea 12.1, creatinine 168, eGFR 32. NT-proBNP 4200 pg/mL.",
    "",
    "<b>Allergies:</b> Patient reports penicillin allergy (rash, 2018). Avoid beta-lactams.",
    "",
    "<b>Plan:</b>",
    "&bull; Increase furosemide to 80 mg OD",
    "&bull; Add spironolactone 25 mg OD &mdash; monitor U&amp;E in 2 weeks",
    "&bull; Consider sacubitril/valsartan in 4 weeks if eGFR stable",
    "&bull; Repeat eGFR and electrolytes in 2 weeks",
    "&bull; Referral to heart failure nurse specialist for education and titration",
    "&bull; Routine cardiology follow-up in 3 months",
    "",
    "Yours sincerely,",
    "Dr S. Mitchell, Consultant Cardiologist",
]

# ============================================================================
# DOC 3 — A&E Discharge Summary, 4 Apr 2024 — REPRODUCES NKDA ERROR
# (this is realistic: bad allergy records propagate across systems)
# ============================================================================
doc3_body = [
    "<b>Manchester Royal Infirmary &mdash; Emergency Department</b>",
    "Date: 04 Apr 2024",
    "<b>DISCHARGE SUMMARY</b>",
    f"Patient: {NAME}",
    f"DOB: {DOB} (age 69)",
    f"NHS Number: {NHS}",
    f"Address: {ADDRESS}",
    "",
    "<b>Presentation:</b> Brought in by ambulance with acute shortness of breath at rest, worsening over 48 hours. "
    "Unable to lie flat. Productive cough, no fever.",
    "",
    "<b>Diagnosis:</b> Acute decompensated heart failure (ICD-10: I50.21) on background of chronic HFrEF. "
    "Likely precipitated by suboptimal compliance with new furosemide dose.",
    "",
    "<b>Examination on arrival:</b> SpO2 88% on room air, RR 28, BP 156/94, HR 104. Bibasal crackles to mid-zones. "
    "Bilateral pitting oedema to knees. CXR: pulmonary oedema with bilateral pleural effusions.",
    "",
    "<b>Treatment given:</b> IV furosemide 80 mg, oxygen via nasal cannulae, GTN infusion. Symptoms improved over 6 hours. "
    "Admitted to AMU overnight for monitoring; discharged following day.",
    "",
    "<b>Allergies:</b> NKDA.",
    "",
    "<b>Discharge medications:</b>",
    "&bull; Furosemide 80 mg OD &mdash; continue at increased dose from cardiology review",
    "&bull; Ramipril 5 mg OD &mdash; continue",
    "&bull; Bisoprolol 5 mg OD &mdash; continue",
    "&bull; Spironolactone 25 mg OD &mdash; continue",
    "&bull; Atorvastatin 40 mg ON &mdash; continue",
    "&bull; Metformin 1 g BD &mdash; continue",
    "",
    "<b>Follow-up:</b> GP review within 7 days. Heart failure nurse contact within 2 weeks. "
    "Cardiology clinic follow-up as previously arranged.",
]

# ---- Write PDFs ----
p1 = write_pdf("01_GP_Referral_Thompson_12Jan2024.pdf", doc1_body)
p2 = write_pdf("02_Cardiology_Thompson_28Feb2024.pdf", doc2_body)
p3 = write_pdf("03_AE_Discharge_Thompson_04Apr2024.pdf", doc3_body)

# ============================================================================
# GOLD FLAGS — design intent recorded at construction
# ============================================================================
gold_flags = {
    "patient_id": PATIENT_ID,
    "patient_name": NAME,
    "patient_dob": DOB,
    "patient_nhs": NHS,
    "construction_date": "2026-06-17",
    "design_principle": (
        "Cardiology + CKD case with intentionally planted allergy contradiction. "
        "Documents are chronologically distinct (Jan, Feb, Apr 2024) and "
        "deliberately diverse in content (GP referral / cardiology specialist letter / "
        "A&E discharge), targeting pairwise content-token Jaccard < 0.5."
    ),
    "gold_flags": [
        {
            "category": "ALLERGY_CONFLICT",
            "clinical_subject": "penicillin allergy",
            "severity": "HIGH",
            "rationale": (
                "Two documents disagree on allergy status (doc 01 + doc 03 say NKDA; "
                "doc 02 documents penicillin allergy). The flag should fire on the "
                "doc-02 allergy record because that is the explicit clinical statement."
            ),
            "expected_source_document": "02_Cardiology_Thompson_28Feb2024.pdf",
        },
        {
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "chronic kidney disease",
            "severity": "MEDIUM",
            "rationale": (
                "Last CKD-relevant clinical entry is doc 03 (04 Apr 2024). "
                "If evaluation is run >90 days after this date, the OVERDUE_FOLLOWUP "
                "rule should fire on chronic kidney disease."
            ),
            "expected_source_document": "03_AE_Discharge_Thompson_04Apr2024.pdf",
        },
        {
            "category": "OVERDUE_FOLLOWUP",
            "clinical_subject": "heart failure",
            "severity": "MEDIUM",
            "rationale": (
                "Heart failure is documented across all three docs. Last entry is 04 Apr 2024; "
                "if evaluation runs >90 days later, OVERDUE_FOLLOWUP should fire on heart failure."
            ),
            "expected_source_document": "03_AE_Discharge_Thompson_04Apr2024.pdf",
        },
    ],
    "additional_AI_flags_acceptable": [
        "AI_UNDOCUMENTED_TREATMENT for heart failure (ACE inhibitor is documented but the LLM "
        "may flag absence of SGLT2 inhibitor or sacubitril/valsartan — that is acceptable, "
        "though not in the gold set since it requires guideline knowledge beyond what's in the docs).",
        "AI flags surfacing the worsening eGFR (32 mL/min) as needing review — acceptable, "
        "not in gold set since it's evidence-grounded but not a deterministic rule trigger.",
    ],
    "notes": (
        "patient_001 is the CONTRADICTION case. The eval should pick up both the gold flags "
        "AND the gold contradiction below. Watch the contradiction agent specifically."
    ),
}

(OUT_DIR / "gold_flags.json").write_text(
    json.dumps(gold_flags, indent=2), encoding="utf-8"
)

# ============================================================================
# GOLD CONTRADICTIONS — design intent for the contradiction agent
# ============================================================================
gold_contradictions = {
    "patient_id": PATIENT_ID,
    "construction_date": "2026-06-17",
    "gold_contradictions": [
        {
            "category": "ALLERGY",
            "severity": "HIGH",
            "doc_a_id": "01_GP_Referral_Thompson_12Jan2024.pdf",
            "doc_a_statement": "Allergies: NKDA — no known drug allergies recorded.",
            "doc_b_id": "02_Cardiology_Thompson_28Feb2024.pdf",
            "doc_b_statement": "Patient reports penicillin allergy (rash, 2018). Avoid beta-lactams.",
            "explanation": (
                "Doc 01 (GP referral, Jan 2024) records NKDA; doc 02 (cardiology, Feb 2024) "
                "records a specific penicillin allergy with documented reaction date. These "
                "are directly opposing factual claims about the same patient. The cardiology "
                "letter is the more recent and more specific record."
            ),
            "rationale_for_planting": (
                "This contradiction is realistic of real EHRs where allergy status diverges "
                "across primary care and specialist records. It tests whether the contradiction "
                "agent detects allergy-status disagreement, which is the highest-stakes "
                "contradiction type in clinical practice."
            ),
        }
    ],
    "notes": (
        "Doc 03 (A&E discharge) ALSO records NKDA, reproducing the error from doc 01. "
        "The contradiction agent may emit the contradiction as 01-vs-02 or as 03-vs-02 "
        "(or both); either is correct. The matcher should treat these as the same "
        "underlying contradiction because they're about the same penicillin allergy."
    ),
}

(OUT_DIR / "gold_contradictions.json").write_text(
    json.dumps(gold_contradictions, indent=2), encoding="utf-8"
)

# ============================================================================
# README — the patient's clinical story
# ============================================================================
readme = """# patient_001 — Margaret Thompson

**Construction date:** 2026-06-17
**Domain:** cardiology + chronic kidney disease
**Type:** CONTRADICTION case (planted allergy contradiction)

## Patient

- Name: Margaret Thompson
- DOB: 1954-08-15 (age 69 at first document)
- NHS: 999 100 0001
- Sex: F

## Clinical story

A 69-year-old woman with chronic heart failure with reduced ejection fraction
(HFrEF, LVEF 28%), CKD stage 3b (eGFR 32), hypertension, and type 2 diabetes.
Presents in early 2024 with worsening exertional dyspnoea; referred from GP
to cardiology; reviewed by cardiology who optimises HF therapy; subsequently
admitted to A&E with acute decompensated heart failure approximately 5 weeks
after the cardiology review.

## Documents

| Doc | Date | Type | Clinical content |
|---|---|---|---|
| 01 | 12 Jan 2024 | GP Referral Letter | Conditions list, current meds, NKDA, referral reason |
| 02 | 28 Feb 2024 | Cardiology Clinic Letter | Echo confirms LVEF 28%, optimise HF therapy, **penicillin allergy** documented |
| 03 | 04 Apr 2024 | A&E Discharge Summary | Acute HF decompensation, hospitalisation, NKDA (reproduces error) |

## The planted contradiction

Doc 01 says **NKDA**.
Doc 02 says **penicillin allergy (rash, 2018), avoid beta-lactams**.
Doc 03 says **NKDA** (the error propagates).

This is realistic of how real EHRs behave: allergy records diverge across primary
and specialist care, and bad records propagate. The contradiction agent should
detect this as a HIGH-severity allergy disagreement. See `gold_contradictions.json`.

## Gold flags (design intent)

See `gold_flags.json` for the structured record.

- HIGH `ALLERGY_CONFLICT` on `penicillin allergy`
- MEDIUM `OVERDUE_FOLLOWUP` on `chronic kidney disease`
- MEDIUM `OVERDUE_FOLLOWUP` on `heart failure`

## What this tests

- Contradiction agent: HIGH-severity allergy contradiction detection
- Flag agent: allergy-conflict rule firing on documented allergy
- Flag agent: overdue-followup rule firing on chronic conditions
- Matcher: that the same allergy contradiction recorded across multiple documents
  collapses correctly rather than counting as multiple separate contradictions
"""

(OUT_DIR / "README.md").write_text(readme, encoding="utf-8")

# ---- Summary ----
print(f"\nWrote patient_001 to {OUT_DIR}/")
print(f"  {p1.name} ({p1.stat().st_size} bytes)")
print(f"  {p2.name} ({p2.stat().st_size} bytes)")
print(f"  {p3.name} ({p3.stat().st_size} bytes)")
print(f"  gold_flags.json")
print(f"  gold_contradictions.json")
print(f"  README.md")