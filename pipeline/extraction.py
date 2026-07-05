"""
pipeline/extraction.py — standalone PDF-to-typed-entities extraction,
faithfully assembled from the real production modules (worker/document_processor.py's
process_document orchestration, nlp/medical_ner.py, nlp/negation_detector.py,
parsers/pdf_parser.py, parsers/text_cleaner.py).

This is a deliberately narrower slice than the full production worker:
lab-observation parsing (nlp/lab_parser.py) and full relative-date
normalisation (nlp/date_normaliser.py) are NOT included here, since they
are not central to this paper's claims (safety flags, grounding
validation, contradiction detection) and porting them would be scope
creep for a reviewer-facing reproducibility script. This scope
limitation is stated explicitly in the pipeline README, not hidden.

Everything that IS included — PDF parsing, text cleaning, NER (scispaCy
+ dictionary/regex augmentation, including the drug-dictionary and
condition-pattern fixes described in the paper's Evaluation section),
and two-layer negation detection (negspacy + custom UK-clinical-
shorthand rules) — is the real logic, not a simplified reimplementation.
"""
from __future__ import annotations
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import TypedDict, Literal, Any

import fitz  # PyMuPDF
import spacy
from spacy.language import Language

try:
    from negspacy.negation import Negex  # noqa: F401  (registers the "negex" factory)
    _NEGSPACY_AVAILABLE = True
except ImportError:
    _NEGSPACY_AVAILABLE = False


# ============================================================================
# Stage 1: PDF -> raw text (faithful port of parsers/pdf_parser.py)
# ============================================================================

PDF_MAGIC = b"%PDF-"


def parse_pdf(file_path: str | Path) -> str:
    """Extract text from a PDF file. Raises FileNotFoundError / ValueError
    on missing file, non-PDF, encrypted PDF, or (if no OCR engine is wired
    in this standalone build) no extractable text."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    with open(path, "rb") as f:
        header = f.read(5)
    if header != PDF_MAGIC:
        raise ValueError(
            f"Not a PDF (header was {header!r}, expected {PDF_MAGIC!r}): {path}"
        )

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ValueError(f"Could not open PDF {path}: {e}") from e

    try:
        if doc.is_encrypted:
            raise ValueError(f"PDF is encrypted: {path}")
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    text = "\n".join(pages)
    if not text.strip():
        raise ValueError(
            f"No extractable text in {path}. This standalone pipeline does "
            f"not include an OCR fallback for scanned/image-based PDFs; "
            f"the full production worker does (see paper, Section 2, "
            f"'Availability and licensing')."
        )
    return text


# ============================================================================
# Stage 2: text cleaning (faithful port of parsers/text_cleaner.py)
# ============================================================================

_WEIRD_WS = re.compile(r"[\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]")
_RUN_OF_SPACES = re.compile(r"[ \t]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalise whitespace/encoding from PyMuPDF output without altering
    medical content. Idempotent: clean_text(clean_text(x)) == clean_text(x)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _WEIRD_WS.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    lines = [_RUN_OF_SPACES.sub(" ", line) for line in lines]
    text = "\n".join(lines)
    text = _MANY_NEWLINES.sub("\n\n", text)
    return text.strip()


# ============================================================================
# Stage 3: NER (faithful port of nlp/medical_ner.py)
# ============================================================================

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


DRUG_NAMES: set[str] = {
    "amlodipine", "apixaban", "aspirin", "atorvastatin", "bisoprolol",
    "beclometasone", "furosemide", "gliclazide", "levothyroxine",
    "metformin", "omeprazole", "ramipril", "salbutamol", "sertraline",
    "spironolactone", "tiotropium", "alendronic acid", "adcal-d3",
    "dapagliflozin", "empagliflozin", "canagliflozin", "ertugliflozin",
    "semaglutide", "liraglutide", "dulaglutide", "exenatide",
    "ipratropium", "formoterol", "salmeterol",
    "budesonide", "fluticasone", "prednisolone",
    "sacubitril", "valsartan", "eplerenone", "ivabradine",
    "cinacalcet", "sevelamer", "alfacalcidol",
    "digoxin", "lisinopril", "prednisone", "clindamycin", "labetalol",
    "phenytoin", "docusate", "simvastatin", "glipizide", "diltiazem",
    "lorazepam", "insulin", "warfarin", "heparin", "morphine",
    "hydrochlorothiazide", "amiodarone", "clopidogrel", "pantoprazole",
    "ativan", "glucotrol", "cardizem", "cardizem cd", "lipitor",
    "norvasc", "colace", "dilantin", "renagel", "sensipar", "zocor",
    "coumadin", "lasix", "prilosec", "protonix", "plavix", "toprol",
    "glucophage",
}

CONFLICT_MARKERS: set[str] = {"allerg", "nkda", "intoleran"}

ICD10_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b")

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(
        r"\b\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:in\s+)?\d+\s+"
        r"(?:days|weeks|months|years|day|week|month|year)"
        r"(?:\s+ago)?\b",
        re.IGNORECASE,
    ),
]

NON_MEDICAL_STOPWORDS = {
    "patient", "patients", "reports", "report", "history", "examination",
    "review", "follow", "follow-up", "plan", "letter", "department",
    "consultant", "doctor", "dr", "nhs", "dob", "date", "address",
    "name", "phone", "tel", "email", "weeks", "months", "years",
    "symptoms", "consistent",
    "diagnosed", "diagnosis", "worsening", "advise", "advised", "advice",
    "therapy", "optimisation", "optimization", "management", "treatment",
    "medication", "medications", "prescribing", "prescribed", "investigation",
    "investigations", "ongoing", "stable", "active", "current", "new",
    "additional", "specialist", "primary", "secondary",
    "cardiology", "cardiac", "neurology", "neurological", "respiratory",
    "renal", "endocrine", "haematology", "haematological", "oncology",
    "psychiatry", "psychiatric", "psychology", "dermatology", "ophthalmology",
    "urology", "urological", "gastroenterology", "rheumatology",
    "musculoskeletal", "infectious",
    "echocardiogram", "echocardiography", "ecg", "egfr", "fbc", "lft",
    "u&e", "ues", "hba1c", "tft", "trop", "troponin", "crp", "esr",
    "ct", "mri", "xray", "x-ray", "ultrasound", "endoscopy", "colonoscopy",
    "biopsy", "spirometry",
    "manchester", "london", "birmingham", "liverpool", "leeds", "sheffield",
    "newcastle", "bristol", "glasgow", "edinburgh", "cardiff", "belfast",
    "oxford", "cambridge", "croydon", "avenue", "street", "road", "lane",
    "drive", "close", "way", "boulevard", "place",
    "yours", "sincerely", "regards", "thank", "thanks", "today",
    "presentation", "arrival", "discharge", "admission",
}

CONDITION_ROOTS = {
    "failure", "disease", "syndrome", "deficiency", "neoplasm", "tumour",
    "tumor", "infarction", "embolism", "thrombosis", "haemorrhage",
    "hemorrhage", "infection", "inflammation", "itis", "osis",
    "aemia", "emia", "pathy", "stenosis", "ischaemia", "ischemia",
    "dyspnoea", "dyspnea",
}

CONDITION_TERMS = {
    "diabetes", "hypertension", "asthma", "copd", "depression", "anxiety",
    "schizophrenia", "epilepsy", "parkinson", "alzheimer", "stroke",
    "cva", "tia", "psoriasis", "eczema", "obesity", "hyperlipidaemia",
    "hyperlipidemia", "hypercholesterolaemia", "hypothyroidism",
    "hyperthyroidism", "thyrotoxicosis", "osteoporosis", "osteoarthritis",
    "fibromyalgia", "gout", "hiv", "hepatitis", "tuberculosis", "pneumonia",
    "sepsis", "cancer", "carcinoma", "lymphoma", "leukaemia", "leukemia",
    "myeloma", "melanoma", "dermatitis", "reflux", "gord",
    "gerd", "ckd", "aki", "uti", "bph", "afib", "fibrillation", "arrhythmia",
    "cardiomyopathy", "angina", "ischaemic heart", "ischemic heart",
    "heart failure", "kidney disease", "renal failure", "back pain",
    "low back pain", "depressive disorder", "anxiety disorder",
    "bipolar", "dementia", "delirium", "asthma exacerbation",
    "myocardial infarction", "deep vein thrombosis", "dvt", "pe",
    "pulmonary embolism",
}

SYMPTOM_TERMS = {
    "orthopnoea", "orthopnea", "dyspnoea", "dyspnea", "breathlessness",
    "palpitations", "syncope", "presyncope", "chest pain", "chest tightness",
    "wheeze", "wheezing", "cough", "haemoptysis", "hemoptysis",
    "ankle swelling", "leg swelling", "peripheral oedema", "peripheral edema",
    "oedema", "edema", "pitting oedema", "ascites",
    "fatigue", "weakness", "dizziness", "vertigo", "headache", "nausea",
    "vomiting", "diarrhoea", "diarrhea", "constipation",
    "insomnia", "anhedonia", "low mood", "suicidal ideation",
    "polyuria", "nocturia", "haematuria", "hematuria", "dysuria",
    "joint pain", "myalgia", "arthralgia",
    "fever", "rash", "pruritus", "weight loss", "weight gain",
    "night sweats",
}

_DIAG_NOUN_RE = re.compile(
    r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
    r"|eczema|urticaria|bronchitis|sinusitis)\b",
    re.IGNORECASE,
)

_DOSE_RE = re.compile(
    r"\s*"
    r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|iu))"
    r"(\s+(?:OD|BD|TDS|QDS|PRN|nocte|mane|"
    r"once\s+daily|twice\s+daily|three\s+times\s+daily))?",
    flags=re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_model() -> Language:
    return spacy.load("en_core_sci_sm")


def _looks_like_condition(lower: str) -> bool:
    if lower in CONDITION_TERMS:
        return True
    for term in CONDITION_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return True
    if lower in SYMPTOM_TERMS:
        return True
    for term in SYMPTOM_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return True
    for root in CONDITION_ROOTS:
        if re.search(rf"{re.escape(root)}\b", lower):
            return True
    return False


def _classify_span(span_text: str) -> EntityType | None:
    lower = span_text.lower().strip()

    if len(lower) < 3 or not any(c.isalpha() for c in lower):
        return None

    if lower in DRUG_NAMES:
        return "Drug"
    first_token = lower.split()[0] if lower.split() else ""
    if first_token in DRUG_NAMES:
        return "Drug"

    if _DIAG_NOUN_RE.search(lower):
        return "Diagnosis"

    if any(m in lower for m in CONFLICT_MARKERS):
        return "Conflict"

    if "\n" in span_text or "\r" in span_text:
        return None
    if "icd" in lower:
        return None
    if lower in NON_MEDICAL_STOPWORDS:
        return None
    tokens = lower.split()
    if tokens and all(t.strip(".,") in NON_MEDICAL_STOPWORDS for t in tokens):
        return None

    if not _looks_like_condition(lower):
        return None

    return "Diagnosis"


def _extend_drug_span_with_dose(text: str, start: int, end: int) -> int:
    if end >= len(text):
        return end
    tail = text[end:end + 30]
    m = _DOSE_RE.match(tail)
    if m is None:
        return end
    return end + m.end()


def _find_drugs_by_dictionary(text: str) -> list[Entity]:
    found: list[Entity] = []
    for drug in DRUG_NAMES:
        pattern = re.compile(rf"\b{re.escape(drug)}\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            extended_end = _extend_drug_span_with_dose(text, start, end)
            span_text = text[start:extended_end]
            found.append(Entity(
                entity_type="Drug", text=span_text,
                start_offset=start, end_offset=extended_end,
                negated=False, icd10_code=None, bnf_code=None,
                normalised_value=drug,
            ))
    return found


def _find_conditions_by_pattern(text: str) -> list[Entity]:
    PATS = [
        re.compile(
            r"\b(mild\s+intermittent|mild\s+persistent|moderate\s+persistent"
            r"|severe\s+persistent)\s+asthma\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bCKD\s+stage\s+[1-5][ab]?\b", re.IGNORECASE),
        re.compile(
            r"\bchronic\s+kidney\s+disease\s+stage\s+[1-5][ab]?\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bHF(?:rEF|pEF|mrEF)\b"),
        re.compile(r"\bNYHA\s+class\s+[IViv]+\b", re.IGNORECASE),
        re.compile(r"\bGOLD\s+(?:stage\s+)?[1-4]\b", re.IGNORECASE),
    ]
    found: list[Entity] = []
    for pat in PATS:
        for match in pat.finditer(text):
            span = match.group(0)
            if "\n" in span or "\r" in span:
                continue
            found.append(Entity(
                entity_type="Diagnosis", text=span,
                start_offset=match.start(), end_offset=match.end(),
                negated=False, icd10_code=None, bnf_code=None,
                normalised_value=span.lower().strip(),
            ))
    return found


def _find_conflicts_by_dictionary(text: str) -> list[Entity]:
    CONFLICT_PHRASES = [
        r"drug\s+allerg\w*", r"\ballerg\w+", r"\bintoleran\w+",
        r"\bNKDA\b", r"\bNKA\b",
    ]
    found: list[Entity] = []
    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            span_text = text[start:end]
            if "\n" in span_text or "\r" in span_text:
                continue
            context = text[max(0, start - 5):min(len(text), end + 30)]
            if _DIAG_NOUN_RE.search(context):
                continue
            found.append(Entity(
                entity_type="Conflict", text=span_text,
                start_offset=start, end_offset=end,
                negated=False, icd10_code=None, bnf_code=None,
                normalised_value=None,
            ))
    return found


def _find_dates(text: str) -> list[Entity]:
    found: list[Entity] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            found.append(Entity(
                entity_type="Date", text=match.group(0),
                start_offset=match.start(), end_offset=match.end(),
                negated=False, icd10_code=None, bnf_code=None,
                normalised_value=None,
            ))
    return found


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    if not entities:
        return []

    dates = [e for e in entities if e["entity_type"] == "Date"]
    date_spans = [(d["start_offset"], d["end_offset"]) for d in dates]
    non_dates = [e for e in entities if e["entity_type"] != "Date"]

    def overlaps_a_date(s: int, e: int) -> bool:
        return any(not (e <= ds or s >= de) for ds, de in date_spans)

    non_dates_no_overlap = [
        e for e in non_dates
        if not overlaps_a_date(e["start_offset"], e["end_offset"])
    ]

    by_length = sorted(
        non_dates_no_overlap,
        key=lambda e: (e["end_offset"] - e["start_offset"]),
        reverse=True,
    )
    kept_non_dates: list[Entity] = []
    occupied: list[tuple[int, int]] = []
    for ent in by_length:
        s, e = ent["start_offset"], ent["end_offset"]
        if any(not (e <= os_ or s >= oe) for os_, oe in occupied):
            continue
        kept_non_dates.append(ent)
        occupied.append((s, e))

    kept_dates: list[Entity] = []
    occupied_dates: list[tuple[int, int]] = []
    for ent in sorted(dates, key=lambda e: (e["end_offset"] - e["start_offset"]), reverse=True):
        s, e = ent["start_offset"], ent["end_offset"]
        if any(not (e <= os_ or s >= oe) for os_, oe in occupied_dates):
            continue
        kept_dates.append(ent)
        occupied_dates.append((s, e))

    return kept_non_dates + kept_dates


def extract_entities(text: str) -> list[Entity]:
    """Run NER over cleaned text. Returns typed entities sorted by
    start_offset, overlaps deduplicated."""
    if not text or not text.strip():
        return []

    nlp = _load_model()
    doc = nlp(text)

    entities: list[Entity] = []

    for ent in doc.ents:
        etype = _classify_span(ent.text)
        if etype is None:
            continue
        if etype == "Drug":
            extended_end = _extend_drug_span_with_dose(text, ent.start_char, ent.end_char)
            span_text = text[ent.start_char:extended_end]
            span_end = extended_end
        else:
            span_text = ent.text
            span_end = ent.end_char
        entities.append(Entity(
            entity_type=etype, text=span_text,
            start_offset=ent.start_char, end_offset=span_end,
            negated=False, icd10_code=None, bnf_code=None,
            normalised_value=(span_text.lower().split()[0] if etype == "Drug" else None),
        ))

    entities.extend(_find_drugs_by_dictionary(text))
    entities.extend(_find_conditions_by_pattern(text))
    entities.extend(_find_conflicts_by_dictionary(text))
    entities.extend(_find_dates(text))

    entities = _deduplicate(entities)
    entities.sort(key=lambda e: e["start_offset"])
    return entities


# ============================================================================
# Stage 4: negation detection (faithful port of nlp/negation_detector.py)
# ============================================================================

SENTENCE_NEGATION_PATTERNS = [
    re.compile(r"\bno\s+known\s+", re.IGNORECASE),
    re.compile(r"\bno\s+history\s+of\s+", re.IGNORECASE),
    re.compile(r"\bnil\s+(known\s+)?", re.IGNORECASE),
    re.compile(r"\bdenies\s+", re.IGNORECASE),
    re.compile(r"\babsence\s+of\s+", re.IGNORECASE),
    re.compile(r"\bruled\s+out\s+", re.IGNORECASE),
    re.compile(r"\bnot\s+on\s+", re.IGNORECASE),
    re.compile(r"\bno\s+", re.IGNORECASE),
]

ALLERGY_NEGATION_ACRONYMS = re.compile(r"\b(NKDA|NKA|NDKA)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _load_negex_model() -> Language:
    """Load scispaCy and attach the negspacy Negex component, if available.
    Falls back to sentence-rule-only negation if negspacy is not installed
    (documented explicitly, not silently degraded)."""
    nlp = _load_model()
    if _NEGSPACY_AVAILABLE and "negex" not in nlp.pipe_names:
        nlp.add_pipe("negex", config={"chunk_prefix": ["no"]})
    return nlp


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"[.!?\n]+", text):
        end = m.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if start < len(text) and text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _sentence_contains_negation(sentence: str) -> bool:
    if ALLERGY_NEGATION_ACRONYMS.search(sentence):
        return True
    return any(p.search(sentence) for p in SENTENCE_NEGATION_PATTERNS)


def _which_sentence(start: int, end: int, sentences: list[tuple[int, int]]) -> int | None:
    for i, (s, e) in enumerate(sentences):
        if s <= start and end <= e:
            return i
    return None


def detect_negation(text: str, entities: list[Entity]) -> list[Entity]:
    """Mark entities as negated based on surrounding context. Mutates
    in-place and returns the list for chaining."""
    if not entities:
        return entities

    if _NEGSPACY_AVAILABLE:
        nlp = _load_negex_model()
        doc = nlp(text)
        negex_flags: dict[tuple[int, int], bool] = {
            (ent.start_char, ent.end_char): bool(getattr(ent._, "negex", False))
            for ent in doc.ents
        }
    else:
        negex_flags = {}

    sentences = _sentence_spans(text)
    sentence_negated = [_sentence_contains_negation(text[s:e]) for s, e in sentences]

    for ent in entities:
        if ent["entity_type"] == "Date":
            continue
        if negex_flags.get((ent["start_offset"], ent["end_offset"])):
            ent["negated"] = True
            continue
        sent_idx = _which_sentence(ent["start_offset"], ent["end_offset"], sentences)
        if sent_idx is not None and sentence_negated[sent_idx]:
            ent["negated"] = True

    return entities


# ============================================================================
# Public API: full extraction pipeline, PDF path in, typed entities out
# ============================================================================

def extract_from_pdf(file_path: str | Path) -> dict[str, Any]:
    """Run the full extraction pipeline on a single PDF: parse, clean,
    NER, negation. Returns a dict with the cleaned text and the final
    typed, negation-marked entity list.

    NOTE: this standalone pipeline does not include lab-observation
    parsing or full relative-date normalisation (see module docstring).
    """
    raw_text = parse_pdf(file_path)
    cleaned = clean_text(raw_text)
    entities = extract_entities(cleaned)
    detect_negation(cleaned, entities)
    return {
        "extracted_text": cleaned,
        "entities": entities,
    }
