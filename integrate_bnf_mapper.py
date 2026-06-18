"""Integrate ontology.bnf_mapper into nlp/medical_ner.py.

Drug entities get a bnf_code field populated via the curated BNF mapper.
The drug's canonical lowercase name continues to live in normalised_value
(unchanged behaviour). Diagnoses' icd10_code path is untouched.

Atomic anchored replacement.
"""
from pathlib import Path

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

if "from ontology.bnf_mapper import" in src:
    print("[SKIP] bnf_mapper already imported")
    raise SystemExit(0)

# 1. Add the bnf_mapper import right after the icd10_mapper import
old_import = "from ontology.icd10_mapper import lookup as _icd10_mapper_lookup"
new_import = (
    "from ontology.icd10_mapper import lookup as _icd10_mapper_lookup\n"
    "from ontology.bnf_mapper import lookup as _bnf_mapper_lookup"
)
if old_import not in src:
    print("[FAIL] icd10 import anchor not found - did the ICD-10 integration land?")
    raise SystemExit(1)
src = src.replace(old_import, new_import)

# 2. Extend the Entity TypedDict to include bnf_code
old_typed = '''class Entity(TypedDict):
    entity_type: EntityType
    text: str
    start_offset: int
    end_offset: int
    negated: bool
    icd10_code: str | None
    normalised_value: str | None'''

new_typed = '''class Entity(TypedDict):
    entity_type: EntityType
    text: str
    start_offset: int
    end_offset: int
    negated: bool
    icd10_code: str | None
    bnf_code: str | None
    normalised_value: str | None'''

if old_typed not in src:
    print("[FAIL] Entity TypedDict anchor not found")
    raise SystemExit(1)
src = src.replace(old_typed, new_typed)

# 3. Add a helper that resolves BNF code for a Drug span
old_icd10_helper_end = '''    result = _icd10_mapper_lookup(text)
    return result["code"] if result is not None else None'''

new_icd10_helper_end = '''    result = _icd10_mapper_lookup(text)
    return result["code"] if result is not None else None


def _bnf_for_drug(text: str) -> str | None:
    """Resolve BNF code for a drug span via the curated mapper.

    Mapper handles dose-stripping internally. Returns None for unknown
    drugs. Pure additive: doesn't change drug classification, only
    annotates the entity with a code when one is available.
    """
    if not text:
        return None
    result = _bnf_mapper_lookup(text)
    return result["bnf_code"] if result is not None else None'''

# This anchor must appear EXACTLY ONCE in the file. The first occurrence
# is at the end of _icd10_for_span (the one we want to append after). If
# _icd10_confidence_for_span ALSO has this exact return shape we have a
# conflict. Look at _icd10_confidence_for_span's last line:
#   return f"mapper-{result['confidence']}"
# Different return, different shape. We're safe.
count = src.count(old_icd10_helper_end)
if count != 1:
    print(f"[FAIL] icd10 helper end anchor matched {count} times (expected 1)")
    raise SystemExit(1)
src = src.replace(old_icd10_helper_end, new_icd10_helper_end)

# 4. Wire bnf_code into the Pass 1 scispaCy entity construction (Diagnosis/Drug)
old_pass1 = '''        entities.append(Entity(
            entity_type=etype,
            text=ent.text,
            start_offset=ent.start_char,
            end_offset=ent.end_char,
            negated=False,
            icd10_code=(
                _icd10_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis" else None
            ),
            normalised_value=(
                ent.text.lower().split()[0] if etype == "Drug"
                else _icd10_confidence_for_span(ent.text, text, ent.start_char, ent.end_char)
                if etype == "Diagnosis"
                else None
            ),
        ))'''

new_pass1 = '''        entities.append(Entity(
            entity_type=etype,
            text=ent.text,
            start_offset=ent.start_char,
            end_offset=ent.end_char,
            negated=False,
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
            ),
        ))'''

if old_pass1 not in src:
    print("[FAIL] Pass 1 Entity construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_pass1, new_pass1)

# 5. Pass 2 dictionary-drug entity construction needs bnf_code too
old_pass2 = '''            found.append(Entity(
                entity_type="Drug",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                normalised_value=drug,
            ))
    return found

def _find_conflicts_by_dictionary'''

new_pass2 = '''            found.append(Entity(
                entity_type="Drug",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=_bnf_for_drug(text[start:end]),
                normalised_value=drug,
            ))
    return found

def _find_conflicts_by_dictionary'''

if old_pass2 not in src:
    print("[FAIL] Pass 2 drug-dict construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_pass2, new_pass2)

# 6. Pass 2.5 conflicts and Pass 3 dates Entity constructions also need
# the bnf_code field for TypedDict consistency (always None for non-Drug)
old_conflict = '''            found.append(Entity(
                entity_type="Conflict",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,'''
new_conflict = '''            found.append(Entity(
                entity_type="Conflict",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=None,'''
if old_conflict not in src:
    print("[FAIL] Conflict construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_conflict, new_conflict)

old_date = '''            found.append(Entity(
                entity_type="Date",
                text=match.group(0),
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                normalised_value=None,
            ))'''
new_date = '''            found.append(Entity(
                entity_type="Date",
                text=match.group(0),
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=None,
            ))'''
if old_date not in src:
    print("[FAIL] Date construction anchor not found")
    raise SystemExit(1)
src = src.replace(old_date, new_date)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK BNF mapper integrated into medical_ner")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")