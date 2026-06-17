"""Fix the NER classifier overreach: tighten _classify_span and
_icd10_for_span window so document noise stops becoming "Diagnosis"
entities with wrong/spurious ICD-10 codes.

Two changes, both anchored:

1. _classify_span: stop accepting "any noun >=4 chars" as Diagnosis.
   New rule for Diagnosis acceptance:
     - reject anything containing a newline (document structure noise)
     - reject anything containing 'icd' (the label leaking)
     - reject extended NON_MEDICAL_STOPWORDS
     - reject address/place tokens
     - accept if: (a) followed by explicit (ICD-10: code), OR
                  (b) matches a condition-shape pattern (known root
                      word or known clinical condition family)
     - otherwise reject

2. _icd10_for_span: tighten the trailing-window regex so postcodes
   (M14 5RT, B12 8QR pattern) don't match. The regex now requires that
   the candidate code NOT be followed by " <digit><letter>" (postcode
   format).

A+B per design: A is the exclusion list expansion + structural rejects;
B is the positive-signal requirement (condition-shape OR explicit code).
"""
from pathlib import Path

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# 1. Extend NON_MEDICAL_STOPWORDS with the noise from the smoke output
# ============================================================================
old_stops = '''NON_MEDICAL_STOPWORDS = {
    "patient", "patients", "reports", "report", "history", "examination",
    "review", "follow", "follow-up", "plan", "letter", "department",
    "consultant", "doctor", "dr", "nhs", "dob", "date", "address",
    "name", "phone", "tel", "email", "weeks", "months", "years",
    "symptoms", "consistent",
}'''

new_stops = '''NON_MEDICAL_STOPWORDS = {
    # Document structure / metadata
    "patient", "patients", "reports", "report", "history", "examination",
    "review", "follow", "follow-up", "plan", "letter", "department",
    "consultant", "doctor", "dr", "nhs", "dob", "date", "address",
    "name", "phone", "tel", "email", "weeks", "months", "years",
    "symptoms", "consistent",
    # Generic clinical verbs / nouns NOT diagnoses themselves
    "diagnosed", "diagnosis", "worsening", "advise", "advised", "advice",
    "therapy", "optimisation", "optimization", "management", "treatment",
    "medication", "medications", "prescribing", "prescribed", "investigation",
    "investigations", "ongoing", "stable", "active", "current", "new",
    "additional", "specialist", "primary", "secondary",
    # Specialty/department names (not diagnoses)
    "cardiology", "cardiac", "neurology", "neurological", "respiratory",
    "renal", "endocrine", "haematology", "haematological", "oncology",
    "psychiatry", "psychiatric", "psychology", "dermatology", "ophthalmology",
    "urology", "urological", "gastroenterology", "rheumatology",
    "musculoskeletal", "infectious",
    # Investigation names (clinically real but not diagnoses)
    "echocardiogram", "echocardiography", "ecg", "egfr", "fbc", "lft",
    "u&e", "ues", "hba1c", "tft", "trop", "troponin", "crp", "esr",
    "ct", "mri", "xray", "x-ray", "ultrasound", "endoscopy", "colonoscopy",
    "biopsy", "spirometry",
    # Address / geography (cities, common road words)
    "manchester", "london", "birmingham", "liverpool", "leeds", "sheffield",
    "newcastle", "bristol", "glasgow", "edinburgh", "cardiff", "belfast",
    "oxford", "cambridge", "croydon", "avenue", "street", "road", "lane",
    "drive", "close", "way", "boulevard", "place",
    # Common nouns appearing in clinical letters but not diagnoses
    "yours", "sincerely", "regards", "thank", "thanks", "today",
    "presentation", "arrival", "discharge", "admission",
}'''

if old_stops not in src:
    print("[FAIL] NON_MEDICAL_STOPWORDS anchor not found")
    raise SystemExit(1)
src = src.replace(old_stops, new_stops)

# ============================================================================
# 2. Tighten _classify_span with condition-shape positive signal
# ============================================================================
old_classify = '''def _classify_span(span_text: str) -> EntityType | None:
    lower = span_text.lower().strip()

    if len(lower) < 3 or not any(c.isalpha() for c in lower):
        return None

    if lower in DRUG_NAMES:
        return "Drug"
    first_token = lower.split()[0] if lower.split() else ""
    if first_token in DRUG_NAMES:
        return "Drug"

    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"

    if lower in NON_MEDICAL_STOPWORDS:
        return None

    if len(lower) >= 4:
        return "Diagnosis"

    return None'''

new_classify = '''# Condition-shape signal: a span is a Diagnosis if it contains one of
# these condition roots or matches a known clinical condition family.
# Positive-signal gate (component B of the A+B fix): without this, we
# silently classify any noun span >=4 chars as Diagnosis.
CONDITION_ROOTS = {
    "failure", "disease", "syndrome", "deficiency", "neoplasm", "tumour",
    "tumor", "infarction", "embolism", "thrombosis", "haemorrhage",
    "hemorrhage", "infection", "inflammation", "itis",  # arthritis, pancreatitis, ...
    "osis",   # cirrhosis, psychosis, fibrosis, ...
    "aemia",  # anaemia, leukaemia, ...
    "emia",   # anemia, leukemia (US)
    "pathy",  # neuropathy, myopathy, ...
    "stenosis", "ischaemia", "ischemia", "dyspnoea", "dyspnea",
}

CONDITION_TERMS = {
    "diabetes", "hypertension", "asthma", "copd", "depression", "anxiety",
    "schizophrenia", "epilepsy", "parkinson", "alzheimer", "stroke",
    "cva", "tia", "psoriasis", "eczema", "obesity", "hyperlipidaemia",
    "hyperlipidemia", "hypercholesterolaemia", "hypothyroidism",
    "hyperthyroidism", "thyrotoxicosis", "osteoporosis", "osteoarthritis",
    "fibromyalgia", "gout", "hiv", "hepatitis", "tuberculosis", "pneumonia",
    "sepsis", "cancer", "carcinoma", "lymphoma", "leukaemia", "leukemia",
    "myeloma", "melanoma", "psoriasis", "dermatitis", "reflux", "gord",
    "gerd", "ckd", "aki", "uti", "bph", "afib", "fibrillation", "arrhythmia",
    "cardiomyopathy", "angina", "ischaemic heart", "ischemic heart",
    "heart failure", "kidney disease", "renal failure", "back pain",
    "low back pain", "depressive disorder", "anxiety disorder",
    "bipolar", "dementia", "delirium", "asthma exacerbation",
    "myocardial infarction", "deep vein thrombosis", "dvt", "pe",
    "pulmonary embolism",
}


def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Either contains a known condition root suffix (disease, failure,
    itis, ...) OR matches a known clinical condition term/family.
    Returns True iff yes.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Contains a known condition term as a substring
    for term in CONDITION_TERMS:
        if term in lower:
            return True
    # Contains a known condition root suffix
    for root in CONDITION_ROOTS:
        if root in lower:
            return True
    return False


def _classify_span(span_text: str) -> EntityType | None:
    lower = span_text.lower().strip()

    # Length + has-alpha minimum
    if len(lower) < 3 or not any(c.isalpha() for c in lower):
        return None

    # Drugs win first (dictionary)
    if lower in DRUG_NAMES:
        return "Drug"
    first_token = lower.split()[0] if lower.split() else ""
    if first_token in DRUG_NAMES:
        return "Drug"

    # Conflict markers
    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"

    # ==== A+B exclusion gate ====
    # A: structural / address / stopword rejects BEFORE accepting as Diagnosis
    if "\\n" in span_text or "\\r" in span_text:
        # Document structure noise spanning a line break
        return None
    if "icd" in lower:
        # The label "ICD-10" leaking as an entity
        return None
    if lower in NON_MEDICAL_STOPWORDS:
        return None
    # Reject if ANY token of the span is in stopwords AND the span is short
    # (catches "Margaret Thompson" type entities where every token is a name)
    tokens = lower.split()
    if tokens and all(t.strip(".,") in NON_MEDICAL_STOPWORDS for t in tokens):
        return None

    # B: positive-signal gate - must look like a condition
    if not _looks_like_condition(lower):
        return None

    return "Diagnosis"'''

if old_classify not in src:
    print("[FAIL] _classify_span anchor not found")
    raise SystemExit(1)
src = src.replace(old_classify, new_classify)

# ============================================================================
# 3. Tighten _icd10_for_span to reject postcode matches
# ============================================================================
old_icd10 = '''def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    """Resolve ICD-10 code for a diagnosis span.

    Two-tier:
      1. Explicit code in trailing 50-char window (existing behaviour).
         Example: "chronic heart failure (ICD-10: I50.22)" - regex hits.
      2. Fallback: ontology.icd10_mapper.lookup on the span text itself.
         Example: "chronic kidney disease stage 3b" with no explicit code
         in window - mapper returns N18.32.

    Explicit codes win because they're the document's own assertion.
    The mapper fires only when no explicit code is present.
    """
    window = full_text[end : end + 50]
    m = ICD10_RE.search(window)
    if m:
        return m.group(1)
    # Fallback: curated CSV mapper
    result = _icd10_mapper_lookup(text)
    return result["code"] if result is not None else None'''

new_icd10 = '''def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    """Resolve ICD-10 code for a diagnosis span.

    Three-tier:
      1. Explicit code with the literal label 'ICD-10' or 'ICD10' in the
         trailing 50-char window. Required to defeat the UK-postcode
         collision (M14 5RT contains M14, a real ICD-10 code; without
         the label requirement the regex would falsely match it).
      2. Bare-regex match in trailing window IF NOT followed by " <digit>"
         (postcode-shape). Fallback when the label is absent but the code
         pattern is unambiguous.
      3. ontology.icd10_mapper.lookup on the span text itself.
    """
    window = full_text[end : end + 50]

    # Tier 1: explicit "ICD-10:" label nearby
    if "ICD-10" in window or "ICD10" in window:
        m = ICD10_RE.search(window)
        if m:
            return m.group(1)

    # Tier 2: bare regex match - but reject UK postcode shape "<code> <digit><letter>"
    m = ICD10_RE.search(window)
    if m:
        code = m.group(1)
        # Look at what follows the matched code in the window
        after_match = window[m.end():m.end() + 4]
        # UK postcode pattern: " 5RT", " 8QR" - space then digit then letter
        is_postcode = (
            len(after_match) >= 3
            and after_match[0] == " "
            and after_match[1].isdigit()
            and after_match[2].isalpha()
        )
        if not is_postcode:
            return code

    # Tier 3: curated CSV mapper
    result = _icd10_mapper_lookup(text)
    return result["code"] if result is not None else None'''

if old_icd10 not in src:
    print("[FAIL] _icd10_for_span anchor not found")
    raise SystemExit(1)
src = src.replace(old_icd10, new_icd10)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK NER classifier tightened (A+B fix)")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")