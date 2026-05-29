"""
Text cleaning — normalises whitespace and encoding from PyMuPDF output.

Sits between pdf_parser and the NLP layer. Job: tidy the text WITHOUT
changing the medical content. Specifically:

  - normalise unicode (NFKC) so 'β' and similar survive consistently
  - replace non-breaking spaces / weird whitespace with regular spaces
  - collapse runs of spaces and tabs, but preserve paragraph breaks
  - strip trailing whitespace from each line
  - drop fully-blank duplicate lines

NOT done here (deliberately):
  - lowercasing — NER cares about case
  - stripping punctuation — dose strings like '2.5 mg' need the dot
  - removing numbers — they're often clinically critical
"""

import re
import unicodedata


# Whitespace characters that aren't a regular space — replace with " ".
# Includes non-breaking space (U+00A0), various unicode spaces, zero-width chars.
_WEIRD_WS = re.compile(r"[\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]")

# Runs of spaces/tabs (but NOT newlines).
_RUN_OF_SPACES = re.compile(r"[ \t]+")

# Three or more newlines collapse to two (= a paragraph break).
_MANY_NEWLINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """
    Normalise text from PyMuPDF for downstream NLP.

    Idempotent: clean_text(clean_text(x)) == clean_text(x).
    """
    if not text:
        return ""

    # 1. Unicode normalise — NFKC folds compatibility characters
    #    (e.g. ligatures, full-width digits) into their canonical forms,
    #    while keeping medical Greek letters like β intact.
    text = unicodedata.normalize("NFKC", text)

    # 2. Replace exotic whitespace with regular space.
    text = _WEIRD_WS.sub(" ", text)

    # 3. Normalise line endings: CRLF / CR -> LF.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 4. Strip trailing whitespace from each line.
    lines = [line.rstrip() for line in text.split("\n")]

    # 5. Collapse runs of spaces/tabs within each line.
    lines = [_RUN_OF_SPACES.sub(" ", line) for line in lines]

    # 6. Rejoin, then collapse 3+ newlines to 2 (paragraph break).
    text = "\n".join(lines)
    text = _MANY_NEWLINES.sub("\n\n", text)

    # 7. Strip leading/trailing blank lines from the whole thing.
    return text.strip()