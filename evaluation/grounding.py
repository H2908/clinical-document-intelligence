"""
v1.3 Guard 3 grounding grader — analysis-layer twin.

This module mirrors the Guard 3 logic in agents/flag_agent.py byte-for-byte.
It exists so the analysis layer can grade flags from ALL conditions on the
same grounded population, without touching the frozen validator code at
agents/flag_agent.py (tagged paper-instrument-v1-3).

CRITICAL: any divergence between this file and agents/flag_agent.py's
Guard 3 is a bug. The mirror test in evaluation/test_grounding_mirror.py
asserts they produce identical verdicts on the 6-case graded test set.
Re-run that test after ANY change to either implementation.

Verdicts (Tier 0/1/2 of Guard 3 v1.3):
    "verbatim"                — content present + exact substring match
    "paraphrase"              — content present + long contiguous run, but
                                not exact substring (smoothed wording)
    "fabrication"             — token-overlap with cited doc < 0.8 and no
                                other doc rescues
    "composition-fabrication" — token-overlap >= 0.8 but longest contiguous
                                run below n-gram floor
    "misattributed"           — overlap with cited doc < 0.8 but overlap
                                with some other doc >= 0.8
    "empty-content-quote"     — no content tokens after stopword strip
                                (rejected, not grounded)
"""
import re
from spacy.lang.en.stop_words import STOP_WORDS


# ---------------------------------------------------------------------------
# Constants — must match agents/flag_agent.py Guard 3 v1.3 exactly
# ---------------------------------------------------------------------------
FABRICATION_THRESHOLD = 0.8   # at most 1 content word in 5 unaccounted for
NGRAM_FLOOR = 5               # minimum contiguous content-token match

CLINICAL_GENERIC = frozenset({
    "patient", "documented", "noted", "listed",
    "verify", "confirm", "doctor",
})

STOPWORDS_AND_GENERIC = STOP_WORDS | CLINICAL_GENERIC


GROUNDED_VERDICTS = frozenset({"verbatim", "paraphrase"})


# ---------------------------------------------------------------------------
# Helpers (mirror flag_agent.py's local helpers)
# ---------------------------------------------------------------------------
def _content_tokens(text: str) -> list[str]:
    """Tokenise to lowercase content tokens for contiguous-run matching.

    Includes: alphabetic tokens >=4 chars (content words, not stopwords),
    numeric tokens (dose numbers - clinically load-bearing, e.g. the
    '1000' in 'Metformin 1000 mg'), and short clinical unit tokens
    (mg, mcg, ml, iu etc - under 4 chars but clinically meaningful).

    Fixed after MTSamples spot-check found the alpha-only, >=4-char
    version silently dropped dose numbers, collapsing quotes like
    'Metformin 1000 mg' to a single token and making genuine contiguous
    matches structurally undetectable (longest-run capped at 1
    regardless of true quote fidelity).
    """
    UNIT_TOKENS = {"mg", "mcg", "ml", "iu", "kg", "cm"}
    lower = text.lower()
    alpha_tokens = re.findall(r"[a-z]{4,}", lower)
    numeric_tokens = re.findall(r"\b\d+(?:\.\d+)?\b", lower)
    unit_tokens = [t for t in re.findall(r"[a-z]+", lower) if t in UNIT_TOKENS]
    # Reconstruct in original order using a single combined regex pass
    # so contiguity is preserved (critical for the n-gram-run check).
    combined_pattern = r"[a-z]{4,}|\b\d+(?:\.\d+)?\b|\b(?:mg|mcg|ml|iu|kg|cm)\b"
    all_tokens = re.findall(combined_pattern, lower)
    return [t for t in all_tokens if t not in STOPWORDS_AND_GENERIC]


def _longest_contiguous_match(a: list[str], b: list[str]) -> int:
    """Length of longest contiguous sequence shared by lists a and b."""
    if not a or not b:
        return 0
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    best = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > best:
                    best = dp[i][j]
    return best


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def grade_flag(flag: dict, doc_text_by_id: dict[str, str]) -> dict:
    """Apply v1.3 Guard 3 to a single flag.

    Args:
        flag             — a flag dict that may have either cited_document_id
                           (v1.3 AI flags) or source_document_id (rule flags
                           and older outputs). The source_quote field is
                           required for grounding analysis. If absent, the
                           flag is treated as 'empty-content-quote'.
        doc_text_by_id   — full extracted_text per document_id for the patient.

    Returns:
        {
            "verdict": one of the six verdicts above,
            "overlap_cited": float in [0, 1],
            "longest_run": int,
            "best_other_doc": str | None,
            "best_other_overlap": float | None,
        }
    """
    quote = (flag.get("source_quote") or "").strip()
    cited = flag.get("cited_document_id") or flag.get("source_document_id")

    if not quote:
        return {
            "verdict": "empty-content-quote",
            "overlap_cited": 0.0,
            "longest_run": 0,
            "best_other_doc": None,
            "best_other_overlap": None,
        }

    doc_text = doc_text_by_id.get(cited, "") if cited else ""

    quote_tokens = _content_tokens(quote)
    cited_tokens = _content_tokens(doc_text)

    if not quote_tokens:
        return {
            "verdict": "empty-content-quote",
            "overlap_cited": 0.0,
            "longest_run": 0,
            "best_other_doc": None,
            "best_other_overlap": None,
        }

    # Overlap ratio against cited document (set-overlap on content tokens)
    overlap_cited = len(set(quote_tokens) & set(cited_tokens))
    overlap_ratio_cited = overlap_cited / len(set(quote_tokens))

    # Tier 0 — misattribution check
    if overlap_ratio_cited < FABRICATION_THRESHOLD:
        best_other_ratio = 0.0
        best_other_doc = None
        for other_id, other_text in doc_text_by_id.items():
            if other_id == cited:
                continue
            other_tokens = _content_tokens(other_text)
            if not other_tokens:
                continue
            other_overlap = len(set(quote_tokens) & set(other_tokens))
            other_ratio = other_overlap / len(set(quote_tokens))
            if other_ratio > best_other_ratio:
                best_other_ratio = other_ratio
                best_other_doc = other_id

        if best_other_ratio >= FABRICATION_THRESHOLD:
            return {
                "verdict": "misattributed",
                "overlap_cited": overlap_ratio_cited,
                "longest_run": _longest_contiguous_match(quote_tokens, cited_tokens),
                "best_other_doc": best_other_doc,
                "best_other_overlap": best_other_ratio,
            }

        # No other doc rescues -> fabrication
        return {
            "verdict": "fabrication",
            "overlap_cited": overlap_ratio_cited,
            "longest_run": _longest_contiguous_match(quote_tokens, cited_tokens),
            "best_other_doc": None,
            "best_other_overlap": None,
        }

    # Tier 1b — contiguous n-gram floor
    longest_run = _longest_contiguous_match(quote_tokens, cited_tokens)
    min_run_needed = min(NGRAM_FLOOR, max(2, len(quote_tokens) // 2 + 1))
    if longest_run < min_run_needed:
        return {
            "verdict": "composition-fabrication",
            "overlap_cited": overlap_ratio_cited,
            "longest_run": longest_run,
            "best_other_doc": None,
            "best_other_overlap": None,
        }

    # Tier 2 — grounded; classify surface fidelity
    quote_norm = re.sub(r"\s+", " ", quote).strip()
    doc_norm = re.sub(r"\s+", " ", doc_text).strip()
    if quote_norm in doc_norm:
        return {
            "verdict": "verbatim",
            "overlap_cited": overlap_ratio_cited,
            "longest_run": longest_run,
            "best_other_doc": None,
            "best_other_overlap": None,
        }
    return {
        "verdict": "paraphrase",
        "overlap_cited": overlap_ratio_cited,
        "longest_run": longest_run,
        "best_other_doc": None,
        "best_other_overlap": None,
    }


def is_grounded(verdict: str) -> bool:
    """True for Tier 2 accepts (verbatim/paraphrase), False otherwise."""
    return verdict in GROUNDED_VERDICTS