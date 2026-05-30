"""
Negation detection — PATIENT SAFETY CRITICAL.

Marks entities as negated when the surrounding text negates them.

Two layers:
  1. negspacy (NegEx) — standard negation phrases via the spaCy pipeline
  2. Custom rules     — UK clinical shorthand: NKDA, NKA, denies, no history of

A negated entity must NOT be treated as a positive finding downstream.
"""

from __future__ import annotations
import re
from functools import lru_cache

import spacy
from spacy.language import Language
from negspacy.negation import Negex

from nlp.medical_ner import Entity, _load_model


# ---------------------------------------------------------------------------
# Custom negation patterns
# ---------------------------------------------------------------------------

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

ALLERGY_NEGATION_ACRONYMS = re.compile(
    r"\b(NKDA|NKA|NDKA)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_negex_model() -> Language:
    """Load scispaCy and attach the negspacy Negex component."""
    nlp = _load_model()
    if "negex" not in nlp.pipe_names:
        nlp.add_pipe("negex", config={"chunk_prefix": ["no"]})
    return nlp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """
    Split text into sentences and return (start, end) char offsets for each.
    Splits on . ! ? and newlines. Good enough for clinical prose.
    """
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
    """True if the sentence contains a negation acronym or sentence-level pattern."""
    if ALLERGY_NEGATION_ACRONYMS.search(sentence):
        return True
    return any(p.search(sentence) for p in SENTENCE_NEGATION_PATTERNS)


def _which_sentence(start: int, end: int, sentences: list[tuple[int, int]]) -> int | None:
    for i, (s, e) in enumerate(sentences):
        if s <= start and end <= e:
            return i
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_negation(text: str, entities: list[Entity]) -> list[Entity]:
    """
    Mark entities as negated based on surrounding context.

    Mutates entries in-place AND returns the list for chaining.
    """
    if not entities:
        return entities

    # Layer 1: negspacy (NegEx)
    nlp = _load_negex_model()
    doc = nlp(text)
    negex_flags: dict[tuple[int, int], bool] = {
        (ent.start_char, ent.end_char): bool(getattr(ent._, "negex", False))
        for ent in doc.ents
    }

    # Layer 2: sentence-level rules
    sentences = _sentence_spans(text)
    sentence_negated: list[bool] = [
        _sentence_contains_negation(text[s:e]) for s, e in sentences
    ]

    # Apply
    for ent in entities:
        # Dates are never "negated" in the clinical sense.
        if ent["entity_type"] == "Date":
            continue

        # negspacy first
        if negex_flags.get((ent["start_offset"], ent["end_offset"])):
            ent["negated"] = True
            continue

        # Sentence-level fallback
        sent_idx = _which_sentence(ent["start_offset"], ent["end_offset"], sentences)
        if sent_idx is not None and sentence_negated[sent_idx]:
            ent["negated"] = True

    return entities