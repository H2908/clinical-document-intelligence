"""Fix icd10_mapper.lookup() substring tier to be direction-aware.

The bug: "longest matching term wins" treated 'query contains reference'
and 'reference contains query' symmetrically. Result: query 'chronic
heart failure' matched against the longer reference 'chronic heart
failure with preserved ejection fraction' and returned I50.32 (diastolic
HF) -- which adds clinical specificity the query did not justify.

Fix: substring tier now matches only in the direction 'reference is
contained in query'. A query is only assigned a specific code if its
text actually contains that specificity. Vague queries fall through
to vague codes.

Atomic anchored replacement on the substring block in lookup().
"""
from pathlib import Path

p = Path("ontology/icd10_mapper.py")
src = p.read_text(encoding="utf-8")

old = '''    # --- Tier 2: substring ---
    # Collect all (entry, matched_term) pairs where either direction holds,
    # then pick the longest matching term.
    candidates = []
    for entry in _ENTRIES:
        if entry["primary_canon"] in query or query in entry["primary_canon"]:
            candidates.append((entry, entry["primary_term"], len(entry["primary_canon"])))
        for syn_canon, syn_original in zip(entry["synonyms_canon"], _raw_synonyms(entry)):
            if not syn_canon:
                continue
            if syn_canon in query or query in syn_canon:
                candidates.append((entry, syn_original, len(syn_canon)))

    if candidates:
        # Longest match wins
        entry, matched, _ = max(candidates, key=lambda c: c[2])
        return _result(entry, "medium", "substring", matched)

    return None'''

new = '''    # --- Tier 2: substring (direction-aware) ---
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

if old not in src:
    print("[FAIL] anchor not found - aborting")
    raise SystemExit(1)
if src.count(old) > 1:
    print(f"[FAIL] anchor matched {src.count(old)} times - aborting")
    raise SystemExit(1)

p.write_text(src.replace(old, new), encoding="utf-8", newline="\n")
print("OK fix landed")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")