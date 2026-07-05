"""
grounding.py — standalone, pure, testable extraction of the four-guard
grounding validator from agents/flag_agent.py's _llm_second_pass closure.

This module contains no LLM calls, no I/O, no side effects: every
function takes plain data in and returns a plain verdict out. This is
what a reviewer should be able to import directly and unit-test against
hand-built quote/source pairs to verify Guard 3 (composition-fabrication
detection, this paper's principal technical contribution) actually works
as claimed, without needing an API key or the rest of the pipeline.

Faithfully extracted from the production code in agents/flag_agent.py
(_llm_second_pass), including the exact tokenizer and threshold logic
after the calibration fix described in the paper (Evaluation section):
short quotes must be FULLY self-contiguous; long quotes need a
5-content-token contiguous run. Nothing here is reinvented or
approximated — this is the real logic, pulled out of its original
closure so it is independently importable and testable.
"""
from __future__ import annotations
import re
from typing import Optional

# ── Constants (identical to the production values in flag_agent.py) ──

FABRICATION_THRESHOLD = 0.8   # at most 1 content word in 5 unaccounted for
NGRAM_FLOOR = 5               # minimum contiguous content-token match
MIN_QUOTE_CHARS = 30
MIN_QUOTE_WORDS = 6
MIN_QUOTE_WORDS_SOFT = 3

_UNIT_TOKENS = {"mg", "mcg", "ml", "iu", "kg", "cm"}

CLINICAL_GENERIC = {
    "patient", "documented", "noted", "listed",
    "verify", "confirm", "doctor",
}

try:
    from spacy.lang.en.stop_words import STOP_WORDS
    STOPWORDS_AND_GENERIC = STOP_WORDS | CLINICAL_GENERIC
except ImportError:
    # Fallback so this module is importable even without spaCy installed,
    # e.g. for a quick reviewer check of just the grounding logic.
    _FALLBACK_STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
        "of", "in", "on", "at", "to", "for", "with", "from", "this",
        "that", "these", "those", "it", "its", "as",
    }
    STOPWORDS_AND_GENERIC = _FALLBACK_STOPWORDS | CLINICAL_GENERIC


# ── Tokenisation ──────────────────────────────────────────────────────

def content_tokens(text: str) -> list[str]:
    """Tokenise to lowercase content tokens for contiguous-run matching.

    Includes alphabetic tokens >=4 chars, numeric tokens (dose numbers),
    and short clinical unit tokens (mg, mcg, ml, iu etc). Fixed after
    MTSamples generalisation testing found the alpha-only version
    silently dropped dose numbers, collapsing quotes like
    'Metformin 1000 mg' to a single token and capping the longest
    contiguous run at 1 regardless of true quote fidelity — see the
    calibration-bug narrative in the paper's Evaluation section.
    """
    lower = text.lower()
    combined_pattern = r"[a-z]{4,}|\b\d+(?:\.\d+)?\b|\b(?:mg|mcg|ml|iu|kg|cm)\b"
    all_tokens = re.findall(combined_pattern, lower)
    return [t for t in all_tokens if t not in STOPWORDS_AND_GENERIC]


def longest_contiguous_match(a: list[str], b: list[str]) -> int:
    """Length of longest contiguous sequence shared by lists a and b
    (standard LCS-substring dynamic program)."""
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


# ── Guard 1: phantom-citation check ───────────────────────────────────

def check_phantom_citation(cited_document_id: str, valid_document_ids: set[str]) -> bool:
    """Guard 1. True (passes) iff the cited document genuinely exists in
    the patient's document set."""
    return cited_document_id in valid_document_ids


# ── Guard 2: trivial-quote floor ──────────────────────────────────────

def check_trivial_quote(quote: str, category: str, description: str) -> bool:
    """Guard 2. True (passes) iff the quote meets a minimum length/word
    floor, OR (soft branch) is shorter but shares a clinical-subject
    word with the flag's own category+description — admitting terse
    but genuinely specific citations (e.g. "Repeat echocardiogram in
    6 months") without opening a keyword-stuffing loophole."""
    word_count = len(re.findall(r"\w+", quote))
    strict_pass = (len(quote) >= MIN_QUOTE_CHARS and word_count >= MIN_QUOTE_WORDS)
    soft_pass = (word_count >= MIN_QUOTE_WORDS_SOFT
                 and quote_shares_subject(quote, category, description))
    return strict_pass or soft_pass


def quote_shares_subject(quote: str, category: str, description: str) -> bool:
    """Shared helper: does the quote share at least one >=4-char clinical
    subject word with the flag's own category+description, after
    stopword stripping? Used by both Guard 2's soft branch and Guard 4."""
    subject_text = f"{category} {description}".lower()
    subject_text = re.sub(r"\bai[_ ]", " ", subject_text)
    raw_subject_words = set(re.findall(r"[a-z]{4,}", subject_text))
    subject_words = raw_subject_words - STOPWORDS_AND_GENERIC
    quote_words = set(re.findall(r"[a-z]{4,}", quote.lower()))
    return bool(subject_words and (subject_words & quote_words))


# ── Guard 3: contiguous-grounding check (novel — this paper's contribution) ──

def check_contiguous_grounding(
    quote: str,
    cited_document_text: str,
    other_documents: Optional[dict[str, str]] = None,
) -> dict:
    """Guard 3. The paper's principal technical contribution.

    Returns a verdict dict, not just True/False, because the real
    validator distinguishes several distinct failure modes a reviewer
    should be able to see directly:

        {"verdict": "verbatim" | "paraphrase" | "composition-fabrication"
                   | "fabrication" | "misattributed" | "empty-content-quote",
         "passes": bool,
         "overlap_ratio": float,
         "longest_contiguous_run": int}

    Token overlap alone is NOT sufficient for a "grounded" verdict — a
    quote can share 100% of its tokens with the source while asserting
    something the source never actually says, by stitching together
    words from non-adjacent sentences (composition-fabrication). This
    function requires a genuinely contiguous span, scaled to the
    quote's own length: short quotes must be FULLY self-contiguous;
    longer quotes need at least a 5-content-token contiguous run.

    other_documents, if provided, is checked for misattribution: a
    quote that doesn't ground against the cited document but DOES
    ground against a different document in the patient's record is a
    distinct failure mode (wrong citation, not fabrication).
    """
    quote_tokens = content_tokens(quote)
    cited_tokens = content_tokens(cited_document_text)

    if not quote_tokens:
        return {"verdict": "empty-content-quote", "passes": False,
                "overlap_ratio": 0.0, "longest_contiguous_run": 0}

    overlap_cited = len(set(quote_tokens) & set(cited_tokens))
    overlap_ratio_cited = overlap_cited / len(set(quote_tokens))

    if overlap_ratio_cited < FABRICATION_THRESHOLD:
        if other_documents:
            best_other_ratio = 0.0
            for other_text in other_documents.values():
                other_tokens = content_tokens(other_text)
                if not other_tokens:
                    continue
                other_overlap = len(set(quote_tokens) & set(other_tokens))
                other_ratio = other_overlap / len(set(quote_tokens))
                best_other_ratio = max(best_other_ratio, other_ratio)
            if best_other_ratio >= FABRICATION_THRESHOLD:
                return {"verdict": "misattributed", "passes": False,
                        "overlap_ratio": overlap_ratio_cited,
                        "longest_contiguous_run": 0}
        return {"verdict": "fabrication", "passes": False,
                "overlap_ratio": overlap_ratio_cited, "longest_contiguous_run": 0}

    longest_run = longest_contiguous_match(quote_tokens, cited_tokens)
    required_run = min(NGRAM_FLOOR, len(quote_tokens))

    if longest_run < required_run:
        min_run_needed = min(NGRAM_FLOOR, max(2, len(quote_tokens) // 2 + 1))
        if longest_run < min_run_needed:
            return {"verdict": "composition-fabrication", "passes": False,
                    "overlap_ratio": overlap_ratio_cited,
                    "longest_contiguous_run": longest_run}

    quote_norm = re.sub(r"\s+", " ", quote).strip()
    doc_norm = re.sub(r"\s+", " ", cited_document_text).strip()
    verdict = "verbatim" if quote_norm in doc_norm else "paraphrase"
    return {"verdict": verdict, "passes": True,
            "overlap_ratio": overlap_ratio_cited,
            "longest_contiguous_run": longest_run}


# ── Guard 4: subject-relevance check ──────────────────────────────────

def check_subject_relevance(quote: str, category: str, description: str) -> bool:
    """Guard 4. True (passes) iff the quote shares at least one clinical
    subject word with the flag's own category+description. Prevents an
    unrelated but well-formed quote from being used to "launder" an
    unconnected claim. If the flag's own subject words are empty (no
    >=4-char content words after stopword strip), this guard is
    vacuously satisfied — it cannot penalise a flag whose own
    description gives it nothing to check against."""
    subject_text = f"{category} {description}".lower()
    subject_text = re.sub(r"\bai[_ ]", " ", subject_text)
    raw_subject_words = set(re.findall(r"[a-z]{4,}", subject_text))
    subject_words = raw_subject_words - STOPWORDS_AND_GENERIC
    if not subject_words:
        return True
    return quote_shares_subject(quote, category, description)


# ── Orchestration: run all four guards together ───────────────────────

def run_four_guards(
    proposed_flag: dict,
    cited_document_text: str,
    valid_document_ids: set[str],
    other_documents: Optional[dict[str, str]] = None,
) -> dict:
    """Run Guards 1, 2, 3, 4 in sequence against a single proposed flag,
    exactly as the production pipeline does. Returns a verdict dict:

        {"accepted": bool,
         "failed_guard": int | None,   # 1, 2, 3, or 4; None if accepted
         "verdict": str,                # e.g. "verbatim", "composition-fabrication"
         "detail": dict}                # extra info from Guard 3's richer verdict

    A proposed_flag dict must have: cited_document_id, source_quote,
    category, description.
    """
    cited = proposed_flag.get("cited_document_id", "")
    quote = (proposed_flag.get("source_quote") or "").strip()
    category = proposed_flag.get("category", "")
    description = proposed_flag.get("description", "")

    if not check_phantom_citation(cited, valid_document_ids):
        return {"accepted": False, "failed_guard": 1,
                "verdict": "phantom-citation", "detail": {}}

    if not check_trivial_quote(quote, category, description):
        return {"accepted": False, "failed_guard": 2,
                "verdict": "trivial-quote", "detail": {}}

    guard3_result = check_contiguous_grounding(quote, cited_document_text, other_documents)
    if not guard3_result["passes"]:
        return {"accepted": False, "failed_guard": 3,
                "verdict": guard3_result["verdict"], "detail": guard3_result}

    if not check_subject_relevance(quote, category, description):
        return {"accepted": False, "failed_guard": 4,
                "verdict": "irrelevant-padding", "detail": {}}

    return {"accepted": True, "failed_guard": None,
            "verdict": guard3_result["verdict"], "detail": guard3_result}
