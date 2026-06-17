"""BNF drug-name mapper - curated CSV fallback.

Phase 4 L2. Maps free-text drug mentions (from scispaCy NER or LLM emission)
to BNF (British National Formulary) codes via a curated CSV. Same shape as
the ICD-10 mapper, adapted for drugs.

Architectural decisions baked in from ICD-10 mapper's two-bug history:

  1. Three-tier match:
     - Exact (case-insensitive, dose-stripped, whitespace-collapsed)
       -> confidence "high"
     - Direction-aware substring (reference contained in query, word-bounded)
       -> confidence "medium"
     - No match -> None

  2. Dose stripping: drug entities arrive with dose attached
     ("ramipril 5 mg", "atorvastatin 40 mg ON"). The mapper strips
     dose/frequency tokens before lookup so "ramipril 5mg" matches the
     "ramipril" synonym for the ACE inhibitor ramipril.

  3. Word-boundary substring matching (regex \b): prevents short drug
     abbreviations (e.g. 3-char prefixes) from matching inside unrelated
     words. Same fix as the ICD-10 mapper's "RA inside barotrauma" bug.

  4. Direction-aware substring: only matches in the direction "reference
     contained in query". "aspirin" (query) does NOT match the longer
     reference "low-dose aspirin therapy"; "patient on low-dose aspirin"
     (query) DOES match the reference "aspirin". Vague queries get vague
     codes; the mapper refuses to over-specify.

  5. Out of scope for this CSV path: fuzzy matching, brand-to-generic
     normalisation beyond what's in the synonyms column, multi-code
     suggestions (combination products). These are QuickUMLS/RxNorm
     territory.
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
_CSV_PATH = _DATA_DIR / "bnf_common.csv"


# ----------------------------------------------------------------------------
# Dose stripping
# ----------------------------------------------------------------------------

# Patterns that, when matched at end of a drug string, are dose/frequency
# rather than part of the drug name. Conservative: only strips when
# clearly a dose pattern.
_DOSE_PATTERNS = [
    re.compile(r"\s+\d+(?:\.\d+)?\s*(?:mg|mcg|microgram|g|ml|units?|iu|%)\b.*$", re.IGNORECASE),
    re.compile(r"\s+\d+(?:\.\d+)?\s*(?:mg|mcg|microgram|g|ml|units?|iu|%)$", re.IGNORECASE),
    # Trailing frequency without dose
    re.compile(r"\s+(?:od|bd|tds|qds|prn|nocte|mane|on|once daily|twice daily)\s*$", re.IGNORECASE),
]


def _strip_dose(text: str) -> str:
    """Strip dose and frequency tokens from a drug string.

    Examples:
      "Ramipril 5 mg"             -> "Ramipril"
      "Atorvastatin 40 mg ON"      -> "Atorvastatin"
      "Metformin 1 g BD"          -> "Metformin"
      "Insulin 10 units"          -> "Insulin"
      "Aspirin"                   -> "Aspirin"
    """
    result = text
    for pat in _DOSE_PATTERNS:
        result = pat.sub("", result)
    return result.strip()


# ----------------------------------------------------------------------------
# Canonicalisation
# ----------------------------------------------------------------------------

def _canonical(s: str) -> str:
    """Lowercase + collapse internal whitespace + strip. Same rule used
    everywhere identity matters (matcher, gold flags, this mapper)."""
    return re.sub(r"\s+", " ", s).strip().lower()


def _contains_word(query: str, term: str) -> bool:
    """True iff term appears in query bounded by word boundaries.

    Same word-boundary rule as the ICD-10 mapper. Prevents short drug
    abbreviations from matching inside unrelated words.
    """
    if not term:
        return False
    pattern = r"\b" + re.escape(term) + r"\b"
    return bool(re.search(pattern, query))


# ----------------------------------------------------------------------------
# CSV loader
# ----------------------------------------------------------------------------

def _load_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(
            f"BNF CSV not found at {path}. "
            "Expected ontology/data/bnf_common.csv."
        )

    entries = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bnf_code = row["bnf_code"].strip()
            primary = row["bnf_name"].strip()
            synonyms = [s.strip() for s in row.get("synonyms", "").split(";") if s.strip()]
            entries.append({
                "bnf_code": bnf_code,
                "bnf_name": primary,
                "primary_canon": _canonical(primary),
                "synonyms_canon": [_canonical(s) for s in synonyms],
                "synonyms_original": synonyms,
                "bnf_chapter": row.get("bnf_chapter", "").strip(),
                "bnf_paragraph": row.get("bnf_paragraph", "").strip(),
                "therapeutic_class": row.get("therapeutic_class", "").strip(),
            })
    return entries


_ENTRIES: list[dict] = _load_csv(_CSV_PATH)


# ----------------------------------------------------------------------------
# Result builder
# ----------------------------------------------------------------------------

def _result(entry: dict, confidence: str, match_type: str, matched_against: str) -> dict:
    return {
        "bnf_code": entry["bnf_code"],
        "bnf_name": entry["bnf_name"],
        "bnf_chapter": entry["bnf_chapter"],
        "bnf_paragraph": entry["bnf_paragraph"],
        "therapeutic_class": entry["therapeutic_class"],
        "confidence": confidence,
        "match_type": match_type,
        "matched_against": matched_against,
    }


# ----------------------------------------------------------------------------
# Lookup
# ----------------------------------------------------------------------------

def lookup(text: str) -> Optional[dict]:
    """Map a free-text drug mention to a BNF entry.

    Returns:
        {
          "bnf_code": "0205051F0",
          "bnf_name": "Ramipril",
          "bnf_chapter": "Cardiovascular",
          "bnf_paragraph": "Angiotensin-converting enzyme inhibitors",
          "therapeutic_class": "ACE inhibitor",
          "confidence": "high" | "medium",
          "match_type": "exact" | "substring",
          "matched_against": "<the term that matched>",
        }
        or None if no match.

    Match algorithm:
      0. Strip dose/frequency tokens from the query.
      1. Canonicalise (lowercase, collapse whitespace, strip).
      2. Exact match against primary_canon or any synonym_canon
         -> high confidence.
      3. Direction-aware substring (reference contained in query,
         word-bounded) -> medium confidence. Longest matching term wins
         so that more-specific drug names beat generic ones.
      4. None.
    """
    if not text or not text.strip():
        return None

    query = _canonical(_strip_dose(text))
    if not query:
        return None

    # --- Tier 1: exact ---
    for entry in _ENTRIES:
        if entry["primary_canon"] == query:
            return _result(entry, "high", "exact", entry["bnf_name"])
        for syn_canon, syn_original in zip(entry["synonyms_canon"], entry["synonyms_original"]):
            if syn_canon == query:
                return _result(entry, "high", "exact", syn_original)

    # --- Tier 2: substring (direction-aware, word-bounded) ---
    candidates = []
    for entry in _ENTRIES:
        if _contains_word(query, entry["primary_canon"]):
            candidates.append((entry, entry["bnf_name"], len(entry["primary_canon"])))
        for syn_canon, syn_original in zip(entry["synonyms_canon"], entry["synonyms_original"]):
            if _contains_word(query, syn_canon):
                candidates.append((entry, syn_original, len(syn_canon)))

    if candidates:
        entry, matched, _ = max(candidates, key=lambda c: c[2])
        return _result(entry, "medium", "substring", matched)

    return None


# ----------------------------------------------------------------------------
# CLI for quick checks
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ontology/bnf_mapper.py '<drug text>'")
        print("Example: python ontology/bnf_mapper.py 'ramipril 5 mg'")
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    result = lookup(query)
    if result is None:
        print(f"No match for: {query!r}")
    else:
        print(f"Query: {query!r}")
        for k, v in result.items():
            print(f"  {k}: {v}")