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


EntityType = Literal["Diagnosis", "Drug", "Date", "Conflict"]


class Entity(TypedDict):
    entity_type: EntityType
    text: str
    start_offset: int
    end_offset: int
    negated: bool
    icd10_code: str | None
    normalised_value: str | None


# ---------------------------------------------------------------------------
# Dictionaries
# ---------------------------------------------------------------------------

DRUG_NAMES: set[str] = {
    "amlodipine", "apixaban", "aspirin", "atorvastatin", "bisoprolol",
    "beclometasone", "furosemide", "gliclazide", "levothyroxine",
    "metformin", "omeprazole", "ramipril", "salbutamol", "sertraline",
    "spironolactone", "tiotropium", "alendronic acid", "adcal-d3",
}

CONFLICT_MARKERS: set[str] = {
    "allerg",         # matches: allergy, allergies, allergic
    "nkda",
    "intoleran",      # matches: intolerance, intolerant
}

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
]

NON_MEDICAL_STOPWORDS = {
    "patient", "patients", "reports", "report", "history", "examination",
    "review", "follow", "follow-up", "plan", "letter", "department",
    "consultant", "doctor", "dr", "nhs", "dob", "date", "address",
    "name", "phone", "tel", "email", "weeks", "months", "years",
    "symptoms", "consistent",
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

def _classify_span(span_text: str) -> EntityType | None:
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

    return None


def _icd10_for_span(text: str, full_text: str, start: int, end: int) -> str | None:
    window = full_text[end : end + 50]
    m = ICD10_RE.search(window)
    return m.group(1) if m else None


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
            found.append(Entity(
                entity_type="Drug",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                normalised_value=drug,
            ))
    return found

def _find_conflicts_by_dictionary(text: str) -> list[Entity]:
    """
    Independent conflict/allergy pass — catches what scispaCy misses.
    Matches allergy-related terms directly so the negation detector has
    something to mark in 'no known drug allergies' sentences.
    """
    # Words that, when found, mean this span is allergy/conflict-related.
    CONFLICT_PHRASES = [
        r"drug\s+allerg\w*",       # 'drug allergy', 'drug allergies'
        r"\ballerg\w+",            # 'allergy', 'allergies', 'allergic'
        r"\bintoleran\w+",         # 'intolerance', 'intolerant'
        r"\bNKDA\b",
        r"\bNKA\b",
    ]
    found: list[Entity] = []
    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            found.append(Entity(
                entity_type="Conflict",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
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
                normalised_value=None,
            ))
    return found


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    """If two entities overlap, keep the one with the larger span."""
    if not entities:
        return []
    by_length = sorted(
        entities,
        key=lambda e: (e["end_offset"] - e["start_offset"]),
        reverse=True,
    )
    kept: list[Entity] = []
    occupied: list[tuple[int, int]] = []
    for ent in by_length:
        s, e = ent["start_offset"], ent["end_offset"]
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        kept.append(ent)
        occupied.append((s, e))
    return kept


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
        entities.append(Entity(
            entity_type=etype,
            text=ent.text,
            start_offset=ent.start_char,
            end_offset=ent.end_char,
            negated=False,
            icd10_code=(
                _icd10_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis" else None
            ),
            normalised_value=(
                ent.text.lower().split()[0] if etype == "Drug" else None
            ),
        ))

    # Pass 2: dictionary-based drug detection (catches what scispaCy misses)
    entities.extend(_find_drugs_by_dictionary(text))
    # Pass 2.5: dictionary-based conflict/allergy detection
    entities.extend(_find_conflicts_by_dictionary(text))
    # Pass 3: dates via regex
    entities.extend(_find_dates(text))

    # Dedupe overlapping spans — keep the longer one
    entities = _deduplicate(entities)

    # Sort by position
    entities.sort(key=lambda e: e["start_offset"])
    return entities