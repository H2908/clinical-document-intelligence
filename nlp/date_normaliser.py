"""
Date normalisation — converts every Date entity's text to ISO 8601.

Two layers:
  1. dateparser library — handles 28 Feb 2024, 14/01/2024, 2024-02-28, etc.
  2. Relative-phrase rules — '2 weeks', '4 weeks ago', 'in 6 months'
     resolved against the document_date passed in.

Mutates the entity list in place: sets entity['normalised_value'] to an ISO
date string ('YYYY-MM-DD') when parsing succeeds, or leaves it None.
"""

from __future__ import annotations
import re 
from datetime import date, timedelta 
from typing import Optional

import dateparser

from nlp.medical_ner import Entity

# ---------------------------------------------------------------------------
# Relative phrases — '2 weeks', '4 weeks ago', 'in 6 months', '3 days'
# These are resolved relative to the document_date.
# ---------------------------------------------------------------------------

#Captures (amount, unit, direction). direction is 'ago'/'past' or '' (future/unspecified)
RELATIVE_RE = re.compile(
    r"(?:\bin\s+)?"
    r"(\d+)\s+"
    r"(days|weeks|months|years|day|week|month|year)"   # plurals FIRST
    r"(?:\s+(ago|past))?",
    re.IGNORECASE,
)
UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30,    # approximate — fine for clinical timeline ordering
    "year": 365, "years": 365,
}


def _try_relative(text: str, document_date: date)-> Optional[str]:
    """
    Parse a relative phrase like '2 weeks ago' against document_date.
    Returns ISO string or None if not a relative phrase.
    """
    m=RELATIVE_RE.search(text)
    if not m:
        return None
    amount = int(m.group(1))
    unit=m.group(2).lower()
    direction =(m.group(3) or '').lower()
    days= amount*UNIT_DAYS[unit]
    delta = timedelta(days=days)

    # 'ago'/'past' -> subtract; 'in X' or bare 'X weeks' (forward plan) -> add
    target = document_date - delta if direction in {"ago", "past"} else document_date + delta
    return target.isoformat()

def _try_absolute(text: str) -> Optional[str]:
    """
    Parse an absolute date string.
    ISO dates are detected directly (no dateparser ambiguity); everything
    else goes through dateparser with UK day-first preference.
    """
    text = text.strip()

    # ISO date: fast path, unambiguous
    iso_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        # validate by parsing
        try:
            parsed = date.fromisoformat(text)
            return parsed.isoformat()
        except ValueError:
            return None

    # Everything else: dateparser with UK convention
    settings = {
        "DATE_ORDER": "DMY",
        "STRICT_PARSING": False,
        "PREFER_DAY_OF_MONTH": "first",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    parsed = dateparser.parse(text, settings=settings)
    if parsed is None:
        return None
    return parsed.date().isoformat()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalise_dates(entities: list[Entity], document_date: Optional[date] = None)-> list[Entity]:
    """
    Set normalised_value on every Date entity.

    Args:
        entities: entity list from extract_entities + detect_negation.
        document_date: the document's clinical date (used to resolve
                       relative phrases like '2 weeks ago'). If None,
                       relative phrases cannot be resolved and stay None.

    Returns:
        The same list, mutated in place.
    """
    for ent in entities:
        if ent["entity_type"] != "Date":
            continue
        if ent.get("normalised_value"):
            continue  # already set, don't overwrite
        text = ent["text"]

        # Try relative parsing first IF we have a document_date.
        # ('2 weeks ago' is unambiguously relative, can't be parsed as absolute)

        if document_date is not None:
            iso = _try_relative(text, document_date)
            if iso:
                ent["normalised_value"] = iso
                continue

        # Try absolute parsing
        iso = _try_absolute(text)
        if iso:
            ent['normalised_value']=iso

    return entities            