"""Add a SYMPTOM_TERMS whitelist to nlp/medical_ner.py's positive-signal
gate so clinically meaningful symptoms aren't dropped.

Per user 2026-06-18 decision B: orthopnoea, ankle swelling, etc. carry
signal even though they are not, strictly, diagnoses. The 4-type schema
(Diagnosis | Drug | Date | Conflict) doesn't model symptoms, so we
absorb them as Diagnosis. Honest tradeoff: schematically loose, but
preserves signal the LLM second-pass and the matcher can use.

Atomic anchored insert.
"""
from pathlib import Path

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

if "SYMPTOM_TERMS" in src:
    print("[SKIP] SYMPTOM_TERMS already present")
    raise SystemExit(0)

# Insert SYMPTOM_TERMS just after CONDITION_TERMS definition
old_anchor = '''def _looks_like_condition(lower: str) -> bool:'''

new_block = '''SYMPTOM_TERMS = {
    # Cardiovascular / respiratory symptoms
    "orthopnoea", "orthopnea", "dyspnoea", "dyspnea", "breathlessness",
    "palpitations", "syncope", "presyncope", "chest pain", "chest tightness",
    "wheeze", "wheezing", "cough", "haemoptysis", "hemoptysis",
    # Peripheral / fluid signs
    "ankle swelling", "leg swelling", "peripheral oedema", "peripheral edema",
    "oedema", "edema", "pitting oedema", "ascites",
    # General / neurological
    "fatigue", "weakness", "dizziness", "vertigo", "headache", "nausea",
    "vomiting", "diarrhoea", "diarrhea", "constipation",
    # Mental / sleep
    "insomnia", "anhedonia", "low mood", "suicidal ideation",
    # Genitourinary
    "polyuria", "nocturia", "haematuria", "hematuria", "dysuria",
    # MSK
    "joint pain", "myalgia", "arthralgia",
    # Other common
    "fever", "rash", "pruritus", "weight loss", "weight gain",
    "night sweats",
}


def _looks_like_condition(lower: str) -> bool:'''

if old_anchor not in src:
    print("[FAIL] _looks_like_condition anchor not found")
    raise SystemExit(1)
src = src.replace(old_anchor, new_block, 1)

# Now extend the function body to check SYMPTOM_TERMS as well
old_fn_body = '''def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Either contains a known condition root suffix (disease, failure,
    itis, ...) OR matches a known clinical condition term/family.
    Returns True iff yes.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Contains a known condition term as a substring
    for term in CONDITION_TERMS:
        if term in lower:
            return True
    # Contains a known condition root suffix
    for root in CONDITION_ROOTS:
        if root in lower:
            return True
    return False'''

new_fn_body = '''def _looks_like_condition(lower: str) -> bool:
    """Positive-signal gate: does this span look like a clinical condition?

    Accepts if ANY of:
      - Direct match on a known condition term (CONDITION_TERMS)
      - Contains a known condition term as a substring
      - Contains a known condition root suffix (CONDITION_ROOTS)
      - Direct match on a known symptom term (SYMPTOM_TERMS)
      - Contains a known symptom term as a substring

    Symptoms are absorbed as "Diagnosis" because the 4-type entity schema
    does not model them separately. Signal preserved at the cost of
    schematic looseness.
    """
    # Direct match on a known condition term
    if lower in CONDITION_TERMS:
        return True
    # Contains a known condition term as a substring
    for term in CONDITION_TERMS:
        if term in lower:
            return True
    # Direct match on a symptom term
    if lower in SYMPTOM_TERMS:
        return True
    # Contains a symptom term as a substring
    for term in SYMPTOM_TERMS:
        if term in lower:
            return True
    # Contains a known condition root suffix
    for root in CONDITION_ROOTS:
        if root in lower:
            return True
    return False'''

if old_fn_body not in src:
    print("[FAIL] _looks_like_condition body anchor not found")
    raise SystemExit(1)
src = src.replace(old_fn_body, new_fn_body)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK SYMPTOM_TERMS added; gate extended")
print(f"File now {len(p.read_text(encoding='utf-8').splitlines())} lines")