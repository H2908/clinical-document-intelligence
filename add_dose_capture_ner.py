"""Capture dose information in Drug entity spans.

Two changes:
  1. nlp/medical_ner.py: add a _extend_drug_span_with_dose() helper that
     looks ahead from a Drug entity's end_offset and extends it to
     consume a dose+frequency suffix if one is present. Wire it into
     both scispaCy Drug entities and dictionary-pass Drug entities.

  2. agents/briefing_agent.py: in _extract_medications, parse the dose
     out of the entity text (whatever remains after stripping the
     normalised drug name from the front) and include it in the dict.

Dose regex (tight to avoid false positives):
  \d+(\.\d+)?\s*(mg|mcg|g|ml|units?|iu)\b(\s+(OD|BD|TDS|QDS|PRN|nocte|mane|once daily|twice daily))?

No schema change. dose lives in entity.text, propagated through briefing
agent into MART.patient_summary.summary.current_medications[].dose, then
through the shaper to the frontend.
"""
from pathlib import Path

# ============================================================================
# 1. nlp/medical_ner.py - add dose-extension helper + wire it in
# ============================================================================
p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# 1a. Add the helper. Position: after _bnf_for_drug definition.
if "_extend_drug_span_with_dose" in src:
    print("[SKIP] medical_ner.py already has dose-extension helper")
else:
    helper_block = '''


# Dose suffix regex - tight to avoid false positives. Matches:
#   "5 mg", "2.5 mg", "100 mcg", "1 g", "0.5 ml"
#   "5mg" (no space) also OK
#   Optional frequency: "5 mg OD", "2.5 mg BD", "10 mg nocte"
_DOSE_RE = re.compile(
    r"\\s*"                                              # optional ws after drug
    r"(\\d+(?:\\.\\d+)?\\s*(?:mg|mcg|g|ml|units?|iu))"   # number + unit
    r"(\\s+(?:OD|BD|TDS|QDS|PRN|nocte|mane|"             # optional frequency
    r"once\\s+daily|twice\\s+daily|three\\s+times\\s+daily))?",
    flags=re.IGNORECASE,
)


def _extend_drug_span_with_dose(text: str, start: int, end: int) -> int:
    """If a dose pattern starts within 5 chars after `end`, return the
    extended end_offset that includes it. Otherwise return `end` unchanged.

    The look-ahead is intentionally short - dose should be adjacent to the
    drug name in clinical text. We don't want to glue distant dose strings
    onto the wrong drug.
    """
    if end >= len(text):
        return end
    # Look at the next ~30 chars
    tail = text[end:end + 30]
    m = _DOSE_RE.match(tail)
    if m is None:
        return end
    # Found a dose. Extend the entity's end to include it.
    return end + m.end()
'''

    old_anchor = '''def _icd10_confidence_for_span(text: str, full_text: str, start: int, end: int) -> str | None:'''
    if old_anchor not in src:
        print("[FAIL] anchor for inserting dose helper not found")
        raise SystemExit(1)
    src = src.replace(old_anchor, helper_block.lstrip() + "\n\n" + old_anchor, 1)
    print("[OK] medical_ner.py: dose-extension helper added")

# 1b. Wire it into the scispaCy Drug entity construction loop.
# Pattern: when ent is a Drug, we want to extend ent.end_char before
# storing it. Simpler approach: compute extended end before the dict.
old_scispacy_loop = '''    for ent in doc.ents:
        etype = _classify_span(ent.text)
        if etype is None:
            continue
        entities.append(Entity(
            entity_type=etype,
            text=ent.text,
            start_offset=ent.start_char,
            end_offset=ent.end_char,'''

new_scispacy_loop = '''    for ent in doc.ents:
        etype = _classify_span(ent.text)
        if etype is None:
            continue
        # For Drug entities, extend the span forward to capture any dose
        # suffix (e.g. "Ramipril 5 mg" instead of just "Ramipril").
        if etype == "Drug":
            extended_end = _extend_drug_span_with_dose(text, ent.start_char, ent.end_char)
            span_text = text[ent.start_char:extended_end]
            span_end = extended_end
        else:
            span_text = ent.text
            span_end = ent.end_char
        entities.append(Entity(
            entity_type=etype,
            text=span_text,
            start_offset=ent.start_char,
            end_offset=span_end,'''

if "extended_end = _extend_drug_span_with_dose" in src:
    print("[SKIP] scispaCy loop already wired")
else:
    if old_scispacy_loop not in src:
        print("[FAIL] scispaCy loop anchor not found")
        raise SystemExit(1)
    src = src.replace(old_scispacy_loop, new_scispacy_loop)
    print("[OK] medical_ner.py: scispaCy Drug entities now extend for dose")

    # The body inside Entity() that uses ent.text and ent.end_char also
    # needs to use the new span_text and span_end. Specifically:
    # bnf_code uses ent.text, normalised_value's Drug branch uses ent.text.
    # Replace those references inside this block.
    old_inside_drug = '''            negated=False,
            icd10_code=(
                _icd10_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis" else None
            ),
            bnf_code=(_bnf_for_drug(ent.text) if etype == "Drug" else None),
            normalised_value=(
                ent.text.lower().split()[0] if etype == "Drug"
                else _icd10_confidence_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis"
                else None
            ),'''
    new_inside_drug = '''            negated=False,
            icd10_code=(
                _icd10_for_span(span_text, text, ent.start_char, span_end)
                if etype == "Diagnosis" else None
            ),
            bnf_code=(_bnf_for_drug(span_text) if etype == "Drug" else None),
            normalised_value=(
                span_text.lower().split()[0] if etype == "Drug"
                else _icd10_confidence_for_span(span_text, text, ent.start_char, span_end)
                if etype == "Diagnosis"
                else None
            ),'''
    if old_inside_drug in src:
        src = src.replace(old_inside_drug, new_inside_drug)
        print("[OK] medical_ner.py: Entity() body uses span_text/span_end")
    else:
        print("[WARN] inside-Drug Entity() block didn't match; check by hand")

# 1c. Dictionary pass: same span-extension treatment
old_dict_loop = '''    for drug in DRUG_NAMES:
        pattern = re.compile(rf"\\b{re.escape(drug)}\\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            found.append(Entity(
                entity_type="Drug",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=_bnf_for_drug(text[start:end]),
                normalised_value=drug,
            ))'''

new_dict_loop = '''    for drug in DRUG_NAMES:
        pattern = re.compile(rf"\\b{re.escape(drug)}\\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            extended_end = _extend_drug_span_with_dose(text, start, end)
            span_text = text[start:extended_end]
            found.append(Entity(
                entity_type="Drug",
                text=span_text,
                start_offset=start,
                end_offset=extended_end,
                negated=False,
                icd10_code=None,
                bnf_code=_bnf_for_drug(span_text),
                normalised_value=drug,
            ))'''

if "extended_end = _extend_drug_span_with_dose(text, start, end)" in src:
    print("[SKIP] dictionary loop already wired")
else:
    if old_dict_loop not in src:
        print("[FAIL] dictionary loop anchor not found")
        raise SystemExit(1)
    src = src.replace(old_dict_loop, new_dict_loop)
    print("[OK] medical_ner.py: dictionary Drug entities now extend for dose")

p.write_text(src, encoding="utf-8", newline="\n")

# ============================================================================
# 2. agents/briefing_agent.py - parse dose out of entity text in _extract_medications
# ============================================================================
p2 = Path("agents/briefing_agent.py")
src2 = p2.read_text(encoding="utf-8")

old_med_dict = '''        seen[key] = {
            "drug": text,
            "normalised": e.get("normalised_value"),
            "source_document_id": e["document_id"],
        }'''

new_med_dict = '''        # Parse dose out of text: anything after the drug-name root word
        # is treated as dose+frequency (NER span extension captures it).
        dose_part = text[len(key):].strip() if text.lower().startswith(key) else ""
        seen[key] = {
            "drug": text.split()[0] if text.split() else text,
            "normalised": e.get("normalised_value"),
            "dose": dose_part if dose_part else None,
            "source_document_id": e["document_id"],
        }'''

if '"dose": dose_part' in src2:
    print("[SKIP] briefing_agent already extracts dose")
else:
    if old_med_dict not in src2:
        print("[FAIL] briefing_agent medications dict anchor not found")
        raise SystemExit(1)
    src2 = src2.replace(old_med_dict, new_med_dict)
    print("[OK] briefing_agent.py: medications now include dose field")

p2.write_text(src2, encoding="utf-8", newline="\n")

print()
print("=== Summary ===")
print("nlp/medical_ner.py: dose-extension helper + applied to scispaCy + dictionary passes")
print("agents/briefing_agent.py: _extract_medications parses dose out of text")
print()
print("Next steps:")
print("  1. Re-process pat_test_01's 9 docs to repopulate entity.text with doses")
print("  2. Re-run briefing agent (happens automatically via process_from_s3)")
print("  3. Refresh browser - dose column should populate")