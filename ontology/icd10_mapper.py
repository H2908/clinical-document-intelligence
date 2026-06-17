"""ICD-10 mapper - CSV fallback.

Phase 4 L2. Maps free-text condition mentions (from scispaCy NER or LLM
emission) to ICD-10 codes via a curated CSV. This is the fallback when
QuickUMLS/UMLS is not yet indexed; once UMLS is in place, this module
will be the documented baseline for comparison.

Three-tier match:
  - Exact (case-insensitive, whitespace-normalised) -> confidence "high"
  - Substring (entity contains synonym or vice versa) -> confidence "medium"
  - No match -> None

Identity rule deliberately mirrors the matcher: lowercase + strip. Keeps
ICD-10 mapping paraphrase-robust the same way flag identity is.

Out of scope for this CSV path: fuzzy matching, abbreviation expansion
beyond what's in the synonyms column, multi-code suggestions. These are
QuickUMLS territory.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import csv
import re

# ----------------------------------------------------------------------------
# CSV location
# ----------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent / "data"
_CSV_PATH = _DATA_DIR / "icd10_common.csv"


# ----------------------------------------------------------------------------
# CSV loader - cached at module import
# ----------------------------------------------------------------------------

def _canonical(s: str) -> str:
    """Lowercase + collapse internal whitespace + strip. Same rule used
    everywhere identity matters (matcher, gold flags, this mapper)."""
    return re.sub(r"\s+", " ", s).strip().lower()


def _load_csv(path: Path) -> list[dict]:
    """Load the curated ICD-10 CSV into a list of canonicalised entries.

    Each row in the returned list:
      {
        "code": "I50.22",
        "primary_term": "chronic systolic heart failure",
        "primary_canon": "chronic systolic heart failure",
        "synonyms_canon": ["hfref", "chronic heart failure with reduced ejection fraction", ...],
        "chapter": "Cardiovascular",
      }
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"ICD-10 CSV not found at {path}. "
            "Expected ontology/data/icd10_common.csv."
        )

    entries = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["code"].strip()
            primary = row["primary_term"].strip()
            synonyms = [s.strip() for s in row.get("synonyms", "").split(";") if s.strip()]
            chapter = row.get("chapter", "").strip()
            entries.append({
                "code": code,
                "primary_term": primary,
                "primary_canon": _canonical(primary),
                "synonyms_canon": [_canonical(s) for s in synonyms],
                "chapter": chapter,
            })
    return entries


_ENTRIES: list[dict] = _load_csv(_CSV_PATH)


# ----------------------------------------------------------------------------
# Lookup
# ----------------------------------------------------------------------------

def lookup(text: str) -> Optional[dict]:
    """Map a free-text condition mention to an ICD-10 entry.

    Returns:
        {
          "code": "I50.22",
          "description": "Chronic systolic heart failure",
          "chapter": "Cardiovascular",
          "confidence": "high" | "medium",
          "match_type": "exact" | "substring",
          "matched_against": "<the synonym or primary term that matched>",
        }
        or None if no match.

    Match algorithm:
      1. Canonicalise the query (lowercase, collapse whitespace, strip).
      2. Exact match against primary_canon or any synonym_canon -> high confidence.
      3. Substring match (query in primary/synonym, or primary/synonym in query)
         -> medium confidence. Returns the LONGEST matching term so that
         more-specific matches win (e.g., "chronic heart failure with reduced
         ejection fraction" matches "HFrEF" but the longer match returns
         the more specific code).
      4. None.

    The substring tier prefers the longest matching reference term to avoid
    "ckd" inside "chronic kidney disease" winning over the full phrase.
    """
    if not text or not text.strip():
        return None

    query = _canonical(text)

    # --- Tier 1: exact ---
    for entry in _ENTRIES:
        if entry["primary_canon"] == query:
            return _result(entry, "high", "exact", entry["primary_term"])
        for syn_canon, syn_original in zip(entry["synonyms_canon"], _raw_synonyms(entry)):
            if syn_canon == query:
                return _result(entry, "high", "exact", syn_original)

    # --- Tier 2: substring (direction-aware) ---
    # Match only in the direction "reference IS CONTAINED IN query". This
    # ensures the mapper never assigns specificity the query did not justify.
    # Example: "chronic heart failure" (query) should NOT match
    # "chronic heart failure with preserved ejection fraction" (reference)
    # because the query did not say "preserved". The reverse - query DOES
    # contain reference - is the only safe direction: a longer query CAN
    # legitimately map to its shorter, less-specific reference.
    #
    # Among valid matches, the LONGEST reference wins (most specific
    # specificity the query actually contained). E.g., query
    # "patient with chronic heart failure with reduced ejection fraction"
    # matches both "heart failure" and "chronic heart failure with reduced
    # ejection fraction" as substrings; the longer one wins.
    candidates = []
    for entry in _ENTRIES:
        if _contains_word(query, entry["primary_canon"]):
            candidates.append((entry, entry["primary_term"], len(entry["primary_canon"])))
        for syn_canon, syn_original in zip(entry["synonyms_canon"], _raw_synonyms(entry)):
            if _contains_word(query, syn_canon):
                candidates.append((entry, syn_original, len(syn_canon)))

    if candidates:
        entry, matched, _ = max(candidates, key=lambda c: c[2])
        return _result(entry, "medium", "substring", matched)

    return None


def _raw_synonyms(entry: dict) -> list[str]:
    """Recover the original (non-canonical) synonyms for a row. We didn't
    cache them; re-read from CSV on demand for the entry's code."""
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["code"].strip() == entry["code"]:
                return [s.strip() for s in row.get("synonyms", "").split(";") if s.strip()]
    return []


def _contains_word(query: str, term: str) -> bool:
    """True iff term appears in query bounded by word boundaries.

    Uses regex \b. 'RA' matches 'patient with RA' but not 'barotrauma'.
    Empty term returns False.
    """
    if not term:
        return False
    pattern = r"\b" + re.escape(term) + r"\b"
    return bool(re.search(pattern, query))


def _result(entry: dict, confidence: str, match_type: str, matched_against: str) -> dict:
    return {
        "code": entry["code"],
        "description": entry["primary_term"],
        "chapter": entry["chapter"],
        "confidence": confidence,
        "match_type": match_type,
        "matched_against": matched_against,
    }


# ----------------------------------------------------------------------------
# CLI for quick checks
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ontology/icd10_mapper.py '<condition text>'")
        print("Example: python ontology/icd10_mapper.py 'chronic heart failure'")
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    result = lookup(query)
    if result is None:
        print(f"No match for: {query!r}")
    else:
        print(f"Query: {query!r}")
        for k, v in result.items():
            print(f"  {k}: {v}")