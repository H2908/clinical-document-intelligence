"""
Medical Named Entity Recognition.

Pipeline:
  raw text  ->  scispaCy (en_core_sci_sm)  ->  typed entities

scispaCy returns generic ENTITY spans. We classify each span as one of:
  Diagnosis | Drug | Date | Conflict
using a combination of dictionaries (drug list, allergy markers) and regex
(ICD-10 codes, dates).

Returns entities in the shape required by NLP_OUTPUT.md §3:
  {
    "entity_type": "Drug" | "Diagnosis" | "Date" | "Conflict",
    "text": str,
    "start_offset": int,
    "end_offset": int,
    "negated": False,          # set later by negation_detector
    "icd10_code": str | None,
    "normalised_value": str | None,
  }
"""

from __future__ import annotations
import re
from functools import lru_cache
from typing import TypedDict, Literal

import spacy
from spacy.language import Language
from ontology.icd10_mapper import lookup as _icd10_mapper_lookup
from ontology.bnf_mapper import lookup as _bnf_mapper_lookup


EntityType = Literal["Diagnosis", "Drug", "Date", "Conflict"]


class Entity(TypedDict):
    entity_type: EntityType
    text: str
    start_offset: int
    end_offset: int
    negated: bool
    icd10_code: str | None
    bnf_code: str | None
    normalised_value: str | None


# ---------------------------------------------------------------------------
# Dictionaries
# ---------------------------------------------------------------------------

DRUG_NAMES: set[str] = {
    "amlodipine", "apixaban", "aspirin", "atorvastatin", "bisoprolol",
    "beclometasone", "furosemide", "gliclazide", "levothyroxine",
    "metformin", "omeprazole", "ramipril", "salbutamol", "sertraline",
    "spironolactone", "tiotropium", "alendronic acid", "adcal-d3",
    # SGLT2 inhibitors (added: found in synthetic patient_006 plan section)
    "dapagliflozin", "empagliflozin", "canagliflozin", "ertugliflozin",
    # GLP-1 receptor agonists
    "semaglutide", "liraglutide", "dulaglutide", "exenatide",
    # Respiratory
    "ipratropium", "tiotropium", "formoterol", "salmeterol",
    "budesonide", "fluticasone", "prednisolone",
    # Cardiology / HF
    "sacubitril", "valsartan", "eplerenone", "ivabradine",
    "dapagliflozin", "empagliflozin",
    # CKD / nephrology
    "cinacalcet", "sevelamer", "alfacalcidol",
}

CONFLICT_MARKERS: set[str] = {
    "allerg",         # matches: allergy, allergies, allergic
    "nkda",
    "intoleran",      # matches: intolerance, intolerant
}

ICD10_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b")

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                       # 2024-02-28
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),                 # 14/01/2024
    re.compile(
        r"\b\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{4}\b",
        re.IGNORECASE,
    ),                                                          # 28 Feb 2024
    # Relative phrases — resolved by date_normaliser using document_date
    re.compile(
    r"\b(?:in\s+)?\d+\s+"
    r"(?:days|weeks|months|years|day|week|month|year)"   # plurals FIRST
    r"(?:\s+ago)?\b",
    re.IGNORECASE,
),
]

NON_MEDICAL_STOPWORDS = {
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
}


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_model() -> Language:
    return spacy.load("en_core_sci_sm")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Condition-shape signal: a span is a Diagnosis if it contains one of
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


SYMPTOM_TERMS = {
    # Cardiovascular / respiratory symptoms
    "orthopnoea", "orthopnea", "dyspnoea", "dyspnea", "breathlessness",
    "palpitations", "syncope", "presyncope", "chest pain", "chest tightness",
    "wheeze", "wheezing", "cough", "haemoptysis", "hemoptysis",
    # Peripheral / fluid signs
    "ankle swelling", "leg swelling", "peripheral oedema", "peripheral edema",
    "oedema", "edema", "pitting oedema", "ascites",
    # General / neurological
    "fatigue", "weakness", "dizziness", "vertigo", "headache", "nausea",
    "vomiting", "diarrhoea", "diarrhea", "constipation",
    # Mental / sleep
    "insomnia", "anhedonia", "low mood", "suicidal ideation",
    # Genitourinary
    "polyuria", "nocturia", "haematuria", "hematuria", "dysuria",
    # MSK
    "joint pain", "myalgia", "arthralgia",
    # Other common
    "fever", "rash", "pruritus", "weight loss", "weight gain",
    "night sweats",
}


def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Accepts if ANY of:
      - Direct match on a known condition term (CONDITION_TERMS)
      - Contains a known condition term as a WORD-BOUNDARY match
      - Contains a known condition root suffix as a WORD-BOUNDARY match
      - Direct match on a known symptom term (SYMPTOM_TERMS)
      - Contains a known symptom term as a WORD-BOUNDARY match

    Word boundaries (regex \\b) prevent short medical abbreviations from
    leaking into unrelated common words. Before this fix, 'uti' (urinary
    tract infection) leaked into 'routine' and 'pe' (pulmonary embolism)
    leaked into 'specialist', producing false-positive Diagnosis entities.

    Symptoms are absorbed as "Diagnosis" because the 4-type entity schema
    does not model them separately. Signal preserved at the cost of
    schematic looseness.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Word-boundary match on any condition term
    for term in CONDITION_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return True
    # Direct match on a symptom term
    if lower in SYMPTOM_TERMS:
        return True
    # Word-boundary match on any symptom term
    for term in SYMPTOM_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return True
    # Word-boundary match on any condition root suffix.
    # Roots like 'itis', 'osis', 'pathy' are intentional suffixes - they
    # match at word END not as separate words. We use a different pattern:
    # the root must appear at the end of any word in the span.
    for root in CONDITION_ROOTS:
        if re.search(rf"{re.escape(root)}\b", lower):
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

    # Diagnosis-noun compounds containing allerg* are diagnoses, not conflicts.
    # e.g. "allergic rhinitis", "seasonal allergic rhinitis", "allergic asthma"
    _DIAG_NOUN_RE = re.compile(
        r"allerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
        r"|eczema|urticaria|bronchitis|sinusitis)",
        re.IGNORECASE,
    )
    if _DIAG_NOUN_RE.search(lower):
        return "Diagnosis"

    # Conflict markers
    import re as _re2
    _diag_nouns = r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis|eczema|urticaria|bronchitis|sinusitis)\b"
    if _re2.search(_diag_nouns, lower, _re2.IGNORECASE):
        return "Diagnosis"

    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"

    # ==== A+B exclusion gate ====
    # A: structural / address / stopword rejects BEFORE accepting as Diagnosis
    if "\n" in span_text or "\r" in span_text:
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

    return "Diagnosis"


def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
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
    return result["code"] if result is not None else None


def _bnf_for_drug(text: str) -> str | None:
    """Resolve BNF code for a drug span via the curated mapper.

    Mapper handles dose-stripping internally. Returns None for unknown
    drugs. Pure additive: doesn't change drug classification, only
    annotates the entity with a code when one is available.
    """
    if not text:
        return None
    result = _bnf_mapper_lookup(text)
    return result["bnf_code"] if result is not None else None


# Dose suffix regex - tight to avoid false positives. Matches:
#   "5 mg", "2.5 mg", "100 mcg", "1 g", "0.5 ml"
#   "5mg" (no space) also OK
#   Optional frequency: "5 mg OD", "2.5 mg BD", "10 mg nocte"
_DOSE_RE = re.compile(
    r"\s*"                                              # optional ws after drug
    r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|iu))"   # number + unit
    r"(\s+(?:OD|BD|TDS|QDS|PRN|nocte|mane|"             # optional frequency
    r"once\s+daily|twice\s+daily|three\s+times\s+daily))?",
    flags=re.IGNORECASE,
)


def _extend_drug_span_with_dose(text: str, start: int, end: int) -> int:
    """If a dose pattern starts within 5 chars after `end`, return the
    extended end_offset that includes it. Otherwise return `end` unchanged.

    The look-ahead is intentionally short - dose should be adjacent to the
    drug name in clinical text. We don't want to glue distant dose strings
    onto the wrong drug.
    """
    if end >= len(text):
        return end
    # Look at the next ~30 chars
    tail = text[end:end + 30]
    m = _DOSE_RE.match(tail)
    if m is None:
        return end
    # Found a dose. Extend the entity's end to include it.
    return end + m.end()


def _icd10_confidence_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    """Confidence label for the ICD-10 assignment from _icd10_for_span.

    Returns 'explicit' if the document gave us the code, 'mapper-high' or
    'mapper-medium' if the curated mapper fell back, None if no code found.
    Stored in normalised_value for Diagnosis entities (which otherwise
    don't use that field).
    """
    window = full_text[end : end + 50]
    if ICD10_RE.search(window):
        return "explicit"
    result = _icd10_mapper_lookup(text)
    if result is None:
        return None
    return f"mapper-{result['confidence']}"


def _find_drugs_by_dictionary(text: str) -> list[Entity]:
    """
    Independent drug pass — scans text directly for known drug names.
    Closes scispaCy's inconsistent recall on drug strings.
    """
    found: list[Entity] = []
    for drug in DRUG_NAMES:
        pattern = re.compile(rf"\b{re.escape(drug)}\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            extended_end = _extend_drug_span_with_dose(text, start, end)
            span_text = text[start:extended_end]
            found.append(Entity(
                entity_type="Drug",
                text=span_text,
                start_offset=start,
                end_offset=extended_end,
                negated=False,
                icd10_code=None,
                bnf_code=_bnf_for_drug(span_text),
                normalised_value=drug,
            ))
    return found


def _find_conditions_by_pattern(text: str) -> list[Entity]:
    """Pattern-based condition extraction for disease-classification
    statements that scispaCy en_core_sci_sm misses."""
    import re as _re
    PATS = [
        _re.compile(
            r"\b(mild\s+intermittent|mild\s+persistent|moderate\s+persistent|severe\s+persistent)\s+asthma\b",
            _re.IGNORECASE,
        ),
        _re.compile(r"\bCKD\s+stage\s+[1-5][ab]?\b", _re.IGNORECASE),
        _re.compile(
            r"\bchronic\s+kidney\s+disease\s+stage\s+[1-5][ab]?\b",
            _re.IGNORECASE,
        ),
        _re.compile(r"\bHF(?:rEF|pEF|mrEF)\b"),
        _re.compile(r"\bNYHA\s+class\s+[IViv]+\b", _re.IGNORECASE),
        _re.compile(r"\bGOLD\s+(?:stage\s+)?[1-4]\b", _re.IGNORECASE),
    ]
    found: list[Entity] = []
    for pat in PATS:
        for match in pat.finditer(text):
            span = match.group(0)
            if "\n" in span or "\r" in span:
                continue
            found.append(Entity(
                entity_type="Diagnosis",
                text=span,
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=span.lower().strip(),
            ))
    return found

def _find_conflicts_by_dictionary(text: str) -> list[Entity]:
    """Independent conflict/allergy pass - catches what scispaCy misses.
    Matches allergy-related terms so the negation detector has something
    to mark in "no known drug allergies" sentences.
    """
    CONFLICT_PHRASES = [
        r"drug\s+allerg\w*",
        r"\ballerg\w+",
        r"\bintoleran\w+",
        r"\bNKDA\b",
        r"\bNKA\b",
    ]
    # Diagnosis compounds containing allerg* are NOT allergy-conflict
    # markers (e.g. "allergic rhinitis", "allergic asthma").
    DIAGNOSIS_NOUNS_RE = re.compile(
        r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis|eczema|urticaria|bronchitis|sinusitis)\b",
        re.IGNORECASE,
    )
    found: list[Entity] = []
    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            span_text = text[start:end]
            # Skip paragraph-boundary bleed
            if "\n" in span_text or "\r" in span_text:
                continue
            # Skip diagnosis compounds
            context = text[max(0, start - 5):min(len(text), end + 30)]
            if DIAGNOSIS_NOUNS_RE.search(context):
                continue
            found.append(Entity(
                entity_type="Conflict",
                text=span_text,
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=None,
            ))
    return found

def _find_dates(text: str) -> list[Entity]:
    found: list[Entity] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            found.append(Entity(
                entity_type="Date",
                text=match.group(0),
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=None,
            ))
    return found


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    """
    Resolve overlapping entities.

    Rule: Date entities are preserved over non-Date entities (otherwise a
    long scispaCy diagnosis span can silently eat a short Date entity).
    Among entities of the same type, the longer span wins.
    """
    if not entities:
        return []

    # Pass 1: Dates are sacred. Keep all of them first.
    dates = [e for e in entities if e["entity_type"] == "Date"]
    date_spans = [(d["start_offset"], d["end_offset"]) for d in dates]

    # Pass 2: Non-Date entities. Drop any that overlap a Date.
    non_dates = [e for e in entities if e["entity_type"] != "Date"]

    def overlaps_a_date(s: int, e: int) -> bool:
        return any(not (e <= ds or s >= de) for ds, de in date_spans)

    non_dates_no_date_overlap = [
        e for e in non_dates
        if not overlaps_a_date(e["start_offset"], e["end_offset"])
    ]

    # Pass 3: Among non-Date survivors, longer span wins on overlap.
    by_length = sorted(
        non_dates_no_date_overlap,
        key=lambda e: (e["end_offset"] - e["start_offset"]),
        reverse=True,
    )
    kept_non_dates: list[Entity] = []
    occupied: list[tuple[int, int]] = []
    for ent in by_length:
        s, e = ent["start_offset"], ent["end_offset"]
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        kept_non_dates.append(ent)
        occupied.append((s, e))

    # Pass 4: Among Dates, also dedupe (regex can match overlapping forms).
    kept_dates: list[Entity] = []
    occupied_dates: list[tuple[int, int]] = []
    for ent in sorted(dates, key=lambda e: (e["end_offset"] - e["start_offset"]), reverse=True):
        s, e = ent["start_offset"], ent["end_offset"]
        if any(not (e <= os or s >= oe) for os, oe in occupied_dates):
            continue
        kept_dates.append(ent)
        occupied_dates.append((s, e))

    return kept_non_dates + kept_dates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_entities(text: str) -> list[Entity]:
    """
    Run NER over cleaned text.

    Returns a list of Entity dicts matching NLP_OUTPUT.md §3.
    Entities are sorted by start_offset. Overlapping entities are deduplicated.
    """
    if not text or not text.strip():
        return []

    nlp = _load_model()
    doc = nlp(text)

    entities: list[Entity] = []

    # Pass 1: scispaCy spans, classified by our rules
    for ent in doc.ents:
        etype = _classify_span(ent.text)
        if etype is None:
            continue
        # For Drug entities, extend the span forward to capture any dose
        # suffix (e.g. "Ramipril 5 mg" instead of just "Ramipril").
        if etype == "Drug":
            extended_end = _extend_drug_span_with_dose(text, ent.start_char, ent.end_char)
            span_text = text[ent.start_char:extended_end]
            span_end = extended_end
        else:
            span_text = ent.text
            span_end = ent.end_char
        entities.append(Entity(
            entity_type=etype,
            text=span_text,
            start_offset=ent.start_char,
            end_offset=span_end,
            negated=False,
            icd10_code=(
                _icd10_for_span(span_text, text, ent.start_char, span_end)
                if etype == "Diagnosis" else None
            ),
            bnf_code=(_bnf_for_drug(span_text) if etype == "Drug" else None),
            normalised_value=(
                span_text.lower().split()[0] if etype == "Drug"
                else _icd10_confidence_for_span(span_text, text, ent.start_char, span_end)
                if etype == "Diagnosis"
                else None
            ),
        ))

    # Pass 2: dictionary-based drug detection (catches what scispaCy misses)
    entities.extend(_find_drugs_by_dictionary(text))
    # Pass 2.5: pattern-based condition classification + conflict/allergy detection
    entities.extend(_find_conditions_by_pattern(text))
    entities.extend(_find_conflicts_by_dictionary(text))
    # Pass 3: dates via regex
    entities.extend(_find_dates(text))

    # Dedupe overlapping spans — keep the longer one
    entities = _deduplicate(entities)

    # Sort by position
    entities.sort(key=lambda e: e["start_offset"])
    return entities