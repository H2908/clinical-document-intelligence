"""
Lab observation parser — Phase 3 Task 7.

Extracts structured lab values (test name, value, unit, date) from cleaned
clinical text. Hybrid design:
  1. Dictionary of common UK lab test names (synonyms folded)
  2. Regex matches around recognised test names
  3. Returns observation dicts matching CORE.observation columns

Called by worker on every document (lab values appear in clinic letters too,
not just dedicated lab reports). Output shape matches what
database/snowflake_writer.write_observations expects.

Output contract (per DB_SCHEMA.md CORE.observation):
    list[dict] with keys:
        test                 (str — canonical test name, e.g. "eGFR")
        value                (str — measured value, e.g. "32" or "<0.1")
        unit                 (str | None — units, e.g. "mL/min/1.73m2")
        observation_date     (date | None — defaults to document_date if absent)
        source_document_id   (str)
"""

from __future__ import annotations
import re
import logging
from datetime import date
from typing import Iterable

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lab test dictionary — canonical name -> synonyms / abbreviations
# ---------------------------------------------------------------------------
#
# Order matters within each value list: longer/more-specific synonyms first
# so that "NT-proBNP" matches before "BNP".

_LAB_TESTS: dict[str, list[str]] = {
    # Renal
    "eGFR":          ["egfr", "estimated gfr", "estimated glomerular filtration rate"],
    "Creatinine":    ["creatinine", "creat"],
    "Urea":          ["urea", "blood urea nitrogen", "bun"],
    "Sodium":        ["sodium", "na+", "serum sodium"],
    "Potassium":     ["potassium", "k+", "serum potassium"],
    # Liver
    "ALT":           ["alt", "alanine transaminase", "alanine aminotransferase"],
    "AST":           ["ast", "aspartate transaminase", "aspartate aminotransferase"],
    "ALP":           ["alp", "alkaline phosphatase"],
    "Bilirubin":     ["bilirubin", "total bilirubin", "tbil"],
    "Albumin":       ["albumin", "serum albumin"],
    # Haematology
    "Haemoglobin":   ["haemoglobin", "hemoglobin", "hb"],
    "WCC":           ["wcc", "white cell count", "white blood cell count", "wbc"],
    "Platelets":     ["platelets", "platelet count", "plt"],
    "MCV":           ["mcv", "mean cell volume", "mean corpuscular volume"],
    "INR":           ["inr", "international normalised ratio"],
    # Diabetes
    "HbA1c":         ["hba1c", "hb a1c", "glycated haemoglobin", "glycosylated haemoglobin"],
    "Glucose":       ["glucose", "fasting glucose", "random glucose", "blood glucose"],
    # Cardiac
    "NT-proBNP":     ["nt-probnp", "nt probnp", "n-terminal pro-bnp"],
    "BNP":           ["bnp", "brain natriuretic peptide"],
    "Troponin":      ["troponin", "trop t", "troponin t", "troponin i", "high sensitivity troponin"],
    # Thyroid
    "TSH":           ["tsh", "thyroid stimulating hormone"],
    "T4":            ["free t4", "ft4", "thyroxine"],
    "T3":            ["free t3", "ft3", "triiodothyronine"],
    # Inflammation
    "CRP":           ["crp", "c-reactive protein", "c reactive protein"],
    "ESR":           ["esr", "erythrocyte sedimentation rate"],
    "Ferritin":      ["ferritin", "serum ferritin"],
    # Lipids
    "Total Cholesterol": ["total cholesterol", "cholesterol total"],
    "LDL":           ["ldl cholesterol", "ldl-c", "ldl"],
    "HDL":           ["hdl cholesterol", "hdl-c", "hdl"],
    "Triglycerides": ["triglycerides", "trig"],
    # Cardiac function (often quoted in cardiology letters)
    "LVEF":          ["lvef", "left ventricular ejection fraction", "ejection fraction"],
}


# Pre-compiled flat list of (synonym, canonical) for efficient scanning
_SYNONYM_TO_CANONICAL: list[tuple[str, str]] = sorted(
    [(syn, canonical) for canonical, syns in _LAB_TESTS.items() for syn in syns],
    key=lambda pair: -len(pair[0]),  # longest synonym first
)


# ---------------------------------------------------------------------------
# Value + unit regex patterns
# ---------------------------------------------------------------------------
#
# After matching a test name, look forward up to ~40 chars for:
#   (optional separator) (value) (optional unit)
#
# Value patterns supported:
#   "32", "12.4", "<0.1", ">100", "7.8%", "0.5-1.0" (range — take first)
#
# Unit examples:
#   mL/min/1.73m2, mmol/L, g/dL, %, U/L, mg/L, ng/mL, pg/mL, IU/L

_VALUE_PATTERN = (
    r"(?:[:=]\s*|\s+)"                # separator: colon, equals, or whitespace
    r"(?P<value>[<>]?\s*\d+(?:\.\d+)?)"  # number, optionally prefixed with </>
    r"\s*"
    r"(?P<unit>(?:%|mL/min(?:/1\.73m2)?|mmol/L|g/dL|g/L|mg/dL|mg/L|"
    r"ng/mL|pg/mL|U/L|IU/L|mIU/L|mU/L|fL|10\^9/L|10\^12/L|"
    r"x10\^9/L|x10\^12/L|/L|/mm3))?"
)


def parse_labs(
    text: str,
    document_id: str,
    document_date: date | None = None,
) -> list[dict]:
    """
    Extract lab observations from cleaned clinical text.

    Args:
        text: cleaned document text (output of text_cleaner.clean()).
        document_id: source document ID, attached to every observation.
        document_date: fallback observation_date if not found in text.

    Returns:
        list of observation dicts matching CORE.observation columns.
        Empty list if no labs found.
    """
    if not text:
        return []

    observations: list[dict] = []
    text_lower = text.lower()
    # Track ranges we've already consumed to prevent double-extraction
    consumed_spans: list[tuple[int, int]] = []

    for synonym, canonical in _SYNONYM_TO_CANONICAL:
        for match in re.finditer(
            r"\b" + re.escape(synonym) + r"\b",
            text_lower,
        ):
            start = match.start()
            end = match.end()

            # Skip if we've already matched this region for a different (longer) synonym
            if any(s <= start < e for s, e in consumed_spans):
                continue

            # Look forward up to 40 chars for value + optional unit
            window = text[end:end + 40]
            value_match = re.match(_VALUE_PATTERN, window)
            if not value_match:
                continue

            value = value_match.group("value").replace(" ", "").strip()
            unit = value_match.group("unit")

            # Normalise some unit variations
            if unit:
                unit = unit.strip()

            observations.append({
                "test": canonical,
                "value": value,
                "unit": unit if unit else None,
                "observation_date": document_date,
                "source_document_id": document_id,
            })

            # Mark this region as consumed
            consumed_spans.append((start, end + value_match.end()))

    log.info(
        "lab_parser: found %d observations in document %s",
        len(observations), document_id,
    )
    return observations


# ---------------------------------------------------------------------------
# CLI for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sample = """
    Bloods on admission:
        Hb 12.4 g/dL
        WCC 8.2 x10^9/L
        Platelets 245 x10^9/L
        Creatinine: 142 micromol/L
        eGFR 32 mL/min/1.73m2
        Sodium 138 mmol/L
        Potassium 4.5 mmol/L
        HbA1c 7.8 %
        CRP <5 mg/L
        Troponin T 12 ng/mL
        LVEF 35%
    """
    obs = parse_labs(sample, document_id="doc_test", document_date=date(2024, 5, 1))
    print(json.dumps(obs, indent=2, default=str))