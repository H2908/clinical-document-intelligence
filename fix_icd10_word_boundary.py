"""Fix icd10_mapper substring tier to use word-boundary matching.

The bug: substring 'in' check matched 'RA' (rheumatoid arthritis synonym)
inside 'barotrauma' because the letters 'ra' appear sequentially in the
longer word. Two-letter clinical abbreviations like RA, OA, MI, CKD, UC
are clinically meaningful synonyms but their letter sequences appear
randomly inside unrelated words.

Fix: substring tier now requires the reference term to appear in the
query bounded by word boundaries (regex \\b). 'RA' matches 'RA flare'
or 'patient with RA' but does NOT match 'barotrauma'. Affects only the
substring tier; exact matches in Tier 1 are unchanged.

Atomic anchored replacement.
"""
from pathlib import Path

p = Path("ontology/icd10_mapper.py")
src = p.read_text(encoding="utf-8")

# --- 1. Add re import if not already present (it is, but defensive)
if "import re" not in src:
    src = src.replace("import csv", "import csv\nimport re", 1)

# --- 2. Add the _contains_word helper before _result
helper = '''def _contains_word(query: str, term: str) -> bool:
    """True iff term appears in query bounded by word boundaries.

    Uses regex \\b. 'RA' matches 'patient with RA' but not 'barotrauma'.
    Empty term returns False.
    """
    if not term:
        return False
    pattern = r"\\b" + re.escape(term) + r"\\b"
    return bool(re.search(pattern, query))


'''

if "_contains_word" not in src:
    # Insert helper just before _result function
    anchor = "def _result(entry: dict"
    if anchor not in src:
        print(f"[FAIL] could not find _result anchor")
        raise SystemExit(1)
    src = src.replace(anchor, helper + anchor, 1)

# --- 3. Replace the substring tier body to use _contains_word
old = '''    candidates = []
    for entry in _ENTRIES:
        if entry["primary_canon"] and entry["primary_canon"] in query:
            candidates.append((entry, entry["primary_term"], len(entry["primary_canon"])))
        for syn_canon, syn_original in zip(entry["synonyms_canon"], _raw_synonyms(entry)):
            if not syn_canon:
                continue
            if syn_canon in query:
                candidates.append((entry, syn_original, len(syn_canon)))

    if candidates:
        entry, matched, _ = max(candidates, key=lambda c: c[2])
        return _result(entry, "medium", "substring", matched)

    return None'''

new = '''    candidates = []
    for entry in _ENTRIES:
        if _contains_word(query, entry["primary_canon"]):
            candidates.append((entry, entry["primary_term"], len(entry["primary_canon"])))
        for syn_canon, syn_original in zip(entry["synonyms_canon"], _raw_synonyms(entry)):
            if _contains_word(query, syn_canon):
                candidates.append((entry, syn_original, len(syn_canon)))

    if candidates:
        entry, matched, _ = max(candidates, key=lambda c: c[2])
        return _result(entry, "medium", "substring", matched)

    return None'''

if old not in src:
    print("[FAIL] substring-tier anchor not found - aborting")
    raise SystemExit(1)

src = src.replace(old, new)
p.write_text(src, encoding="utf-8", newline="\n")
print("OK word-boundary matching landed")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")