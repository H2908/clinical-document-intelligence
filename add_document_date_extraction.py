"""Bug 3 fix: extract document_date from PDF text instead of trusting
the user-supplied form field.

The upload form pre-fills with today's date; users often submit without
changing it, resulting in PDFs from 2024 being stored with document_date
= today. CORE.document is the timeline's source of truth, so this
corrupts the patient timeline silently.

Production-safe pattern:
  1. After parse_pdf + clean_text, scan the top 500 chars for a labelled
     date pattern (e.g. 'Date: 12 Jan 2024').
  2. If found and parses to a real date, use that.
  3. Otherwise keep the user-supplied date.

Two changes in worker/document_processor.py:
  - Add _extract_document_date(text) helper using regex + dateutil.parser
  - In process_document, override document_date if extraction succeeds

RAW.raw_documents stores the user's claim at submit time (audit
preserved). CORE.document stores the extracted date (truth for the
timeline). The two can differ; that's by design.
"""
from pathlib import Path

p = Path("worker/document_processor.py")
src = p.read_text(encoding="utf-8")

# 1. Add the helper near the top, after imports
helper = '''

# ---------------------------------------------------------------------------
# Document date extraction
# ---------------------------------------------------------------------------

import re as _re
from datetime import date as _date, datetime as _datetime

# Patterns for labelled dates at the top of clinical documents. Ordered
# specific-to-general. The first match wins. Each must use a named group
# 'd' for the date string, which we then parse with multiple strptime
# format attempts.
_DATE_LABEL_PATTERNS = [
    # "Date: 12 Jan 2024" or "Date: 12 January 2024"
    _re.compile(r"(?im)^\\s*Date\\s*[:\\-]\\s*(?P<d>\\d{1,2}\\s+\\w+\\s+\\d{4})\\s*$"),
    # "Date: 2024-01-12" or "Date: 12/01/2024"
    _re.compile(r"(?im)^\\s*Date\\s*[:\\-]\\s*(?P<d>\\d{1,4}[-/]\\d{1,2}[-/]\\d{1,4})\\s*$"),
    # "Date of letter: 12 Jan 2024"
    _re.compile(r"(?im)^\\s*Date\\s+of\\s+(?:letter|report|admission|discharge)\\s*[:\\-]\\s*(?P<d>[\\w\\s\\-/]+?)\\s*$"),
]

_DATE_FORMATS = [
    "%d %b %Y",        # 12 Jan 2024
    "%d %B %Y",        # 12 January 2024
    "%Y-%m-%d",        # 2024-01-12
    "%d/%m/%Y",        # 12/01/2024
    "%d-%m-%Y",        # 12-01-2024
    "%Y/%m/%d",        # 2024/01/12
]


def _extract_document_date(text: str) -> _date | None:
    """Scan the top of the document text for a labelled date.

    Returns the parsed date if extraction succeeds, None otherwise.

    Strategy:
      - Look only at the first 500 chars (top of letter convention).
      - Try each labelled-date regex; first match wins.
      - Try each strptime format; first parse wins.
      - Reject dates obviously out of clinical range (before 1900, after
        today+30 days) - guards against typos and OCR noise.
    """
    if not text:
        return None
    head = text[:500]
    for pattern in _DATE_LABEL_PATTERNS:
        m = pattern.search(head)
        if not m:
            continue
        date_str = m.group("d").strip()
        for fmt in _DATE_FORMATS:
            try:
                parsed = _datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
            # Sanity bounds: pre-1900 is OCR noise; future-dated > 30 days
            # is a typo (clinical letters aren't post-dated by years).
            today = _date.today()
            if parsed.year < 1900:
                continue
            if (parsed - today).days > 30:
                continue
            return parsed
    return None


'''

if "_extract_document_date" in src:
    print("[SKIP] _extract_document_date helper already present")
else:
    # Insert helper after the imports block and before the first function def
    anchor = "from nlp.negation_detector import detect_negation"
    if anchor not in src:
        print("[FAIL] import anchor not found")
        raise SystemExit(1)
    src = src.replace(anchor, anchor + helper, 1)
    print("[OK] _extract_document_date helper added")


# 2. Override document_date in process_document after parse + clean
old_block = '''        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        entities = extract_entities(cleaned)
        normalise_dates(entities, document_date)'''

new_block = '''        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        # Try to extract the document's own date from its top text. If
        # extraction succeeds, override the user-supplied document_date
        # (which is often left as today's date by users). RAW.raw_documents
        # retains the user-supplied date for audit; CORE.document gets the
        # extracted date as the timeline source of truth.
        extracted_date = _extract_document_date(cleaned)
        if extracted_date is not None and extracted_date != document_date:
            log.info(
                "document_date extracted from text: %s (user supplied: %s)",
                extracted_date, document_date,
            )
            document_date = extracted_date
            payload["document"]["document_date_extracted"] = True
        else:
            payload["document"]["document_date_extracted"] = False

        entities = extract_entities(cleaned)
        normalise_dates(entities, document_date)'''

if "document_date_extracted" in src:
    print("[SKIP] process_document already extracts date")
elif old_block not in src:
    print("[FAIL] process_document anchor not found")
    raise SystemExit(1)
else:
    src = src.replace(old_block, new_block, 1)
    print("[OK] process_document now extracts and overrides document_date")


p.write_text(src, encoding="utf-8", newline="\n")
print()
print("=== Summary ===")
print("worker/document_processor.py:")
print("  - _extract_document_date(text) helper added")
print("  - process_document overrides document_date with extracted value")
print()
print("Next steps:")
print("  1. Smoke test: parse one of Margaret's PDFs, check date extraction works")
print("  2. Re-process pat_fa9fb06f's 3 docs to refresh CORE.document with extracted dates")
print("  3. Verify timeline now shows 2024 dates, not 2026")