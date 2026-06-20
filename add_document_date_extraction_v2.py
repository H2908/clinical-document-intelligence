"""v2: Bug 3 fix with corrected anchors.

V1 reported [OK] on the helper insertion but the helper isn't actually
in the file - probably because the import-replace anchor was wrong.
V2 uses a different, exact anchor: the last import line of the file.

Then process_document override uses the correct block that includes
detect_negation (which v1 missed).
"""
from pathlib import Path

p = Path("worker/document_processor.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# 1. Helper at module scope after last import
# ============================================================================
helper_block = '''from nlp.date_normaliser import normalise_dates


# ---------------------------------------------------------------------------
# Document date extraction
# ---------------------------------------------------------------------------

import re as _re
from datetime import date as _date, datetime as _datetime

# Patterns for labelled dates at the top of clinical documents. Ordered
# specific-to-general. The first match wins.
_DATE_LABEL_PATTERNS = [
    # "Date: 12 Jan 2024" or "Date: 12 January 2024"
    _re.compile(r"(?im)^\\s*Date\\s*[:\\-]\\s*(?P<d>\\d{1,2}\\s+\\w+\\s+\\d{4})\\s*$"),
    # "Date: 2024-01-12" or "Date: 12/01/2024"
    _re.compile(r"(?im)^\\s*Date\\s*[:\\-]\\s*(?P<d>\\d{1,4}[-/]\\d{1,2}[-/]\\d{1,4})\\s*$"),
    # "Date of letter: 12 Jan 2024"
    _re.compile(r"(?im)^\\s*Date\\s+of\\s+(?:letter|report|admission|discharge)\\s*[:\\-]\\s*(?P<d>[\\w\\s\\-/]+?)\\s*$"),
]

_DATE_FORMATS = [
    "%d %b %Y", "%d %B %Y",
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
]


def _extract_document_date(text: str) -> _date | None:
    """Scan the top of the document text for a labelled date.

    Returns the parsed date if extraction succeeds, None otherwise.
    Looks at first 500 chars. Tries each labelled pattern; first match
    wins. Tries each strptime format; first parse wins. Rejects pre-1900
    (OCR noise) and dates more than 30 days in the future (typos).
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
            today = _date.today()
            if parsed.year < 1900:
                continue
            if (parsed - today).days > 30:
                continue
            return parsed
    return None
'''

anchor_1 = "from nlp.date_normaliser import normalise_dates"

if "_extract_document_date" in src:
    print("[SKIP] _extract_document_date already defined")
else:
    if anchor_1 not in src:
        print(f"[FAIL] anchor '{anchor_1}' not found")
        raise SystemExit(1)
    # Replace the single import line with the import + helper block
    src = src.replace(anchor_1, helper_block, 1)
    print("[OK] _extract_document_date helper added at module scope")


# ============================================================================
# 2. Override document_date inside process_document
# ============================================================================
old_block = '''        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        entities = extract_entities(cleaned)
        detect_negation(cleaned, entities)
        normalise_dates(entities, document_date)'''

new_block = '''        raw_text = parse_pdf(file_path)
        cleaned = clean_text(raw_text)
        payload["document"]["extracted_text"] = cleaned

        # Bug 3 fix: extract document_date from the PDF text instead of
        # trusting the user-supplied form field (which often defaults to
        # today). Falls back to user-supplied if extraction fails.
        # RAW.raw_documents retains user-supplied (audit); CORE.document
        # gets the extracted value (truth).
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
        detect_negation(cleaned, entities)
        normalise_dates(entities, document_date)'''

if "document_date_extracted" in src:
    print("[SKIP] process_document already extracts date")
elif old_block not in src:
    print("[FAIL] process_document anchor not matching")
    raise SystemExit(1)
else:
    src = src.replace(old_block, new_block, 1)
    print("[OK] process_document overrides document_date with extracted value")

p.write_text(src, encoding="utf-8", newline="\n")

print()
print("=== Summary ===")
print("Helper at module scope + process_document override")
print()
print("Verify before re-process:")
print("  python -c \"from worker.document_processor import _extract_document_date; print(_extract_document_date('Date: 12 Jan 2024'))\"")
print("  Expected: 2024-01-12")