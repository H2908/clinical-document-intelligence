"""Fix four NER issues found during synthetic patient ingestion inspection.

Issue 1: dapagliflozin missing from DRUG_NAMES — not extracted from plan
         sections even when explicitly named. Fix: add to DRUG_NAMES.

Issue 2: Asthma GINA severity classification not extracted — scispaCy
         en_core_sci_sm doesn't recognise 'moderate persistent asthma' as
         a named entity. Fix: add _find_conditions_by_pattern() function
         with regex patterns for disease-classification statements, called
         at Pass 2.5 alongside _find_conflicts_by_dictionary().

Issue 3: Paragraph-boundary bleeding in Conflict entities — 'NT-proBNP
         4200 pg/mL.\nAllergies' extracted as one Conflict span because
         the newline guard exists for Diagnosis entities but NOT for the
         dictionary Conflict pass. Fix: add newline guard to
         _find_conflicts_by_dictionary().

Issue 4: Allergic rhinitis misclassified as Conflict — '\ballerg\w+'
         matches 'allergic' in 'allergic rhinitis'. Fix: add a post-match
         check that excludes spans where 'allerg' is followed by a
         diagnosis noun (rhinitis, conjunctivitis, etc).

Guardrail: v1.3 grounding instrument untouched. These are NER fixes only.
"""
from pathlib import Path
import ast

p = Path("nlp/medical_ner.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# Issue 1: Add dapagliflozin (and other common SGLT2i/GLP-1/respiratory
# drugs that appeared in synthetic patients) to DRUG_NAMES
# ============================================================================

old_drug_names = '''DRUG_NAMES: set[str] = {
    "amlodipine", "apixaban", "aspirin", "atorvastatin", "bisoprolol",
    "beclometasone", "furosemide", "gliclazide", "levothyroxine",
    "metformin", "omeprazole", "ramipril", "salbutamol", "sertraline",
    "spironolactone", "tiotropium", "alendronic acid", "adcal-d3",
}'''

new_drug_names = '''DRUG_NAMES: set[str] = {
    "amlodipine", "apixaban", "aspirin", "atorvastatin", "bisoprolol",
    "beclometasone", "furosemide", "gliclazide", "levothyroxine",
    "metformin", "omeprazole", "ramipril", "salbutamol", "sertraline",
    "spironolactone", "tiotropium", "alendronic acid", "adcal-d3",
    # SGLT2 inhibitors (added: found in synthetic patient_006 plan section)
    "dapagliflozin", "empagliflozin", "canagliflozin", "ertugliflozin",
    # GLP-1 receptor agonists
    "semaglutide", "liraglutide", "dulaglutide", "exenatide",
    # Respiratory
    "ipratropium", "tiotropium", "formoterol", "salmeterol",
    "budesonide", "fluticasone", "prednisolone",
    # Cardiology / HF
    "sacubitril", "valsartan", "eplerenone", "ivabradine",
    "dapagliflozin", "empagliflozin",
    # CKD / nephrology
    "cinacalcet", "sevelamer", "alfacalcidol",
}'''

if old_drug_names not in src:
    print("[FAIL] DRUG_NAMES anchor not found")
    raise SystemExit(1)
src = src.replace(old_drug_names, new_drug_names, 1)
print("[OK] Issue 1: dapagliflozin + other missing drugs added to DRUG_NAMES")


# ============================================================================
# Issue 2: Add _find_conditions_by_pattern() for disease-classification
# statements that scispaCy misses
# ============================================================================

new_condition_finder = '''
def _find_conditions_by_pattern(text: str) -> list[Entity]:
    """
    Pattern-based condition extraction for disease-classification statements
    that scispaCy en_core_sci_sm misses.

    Targets:
      - Asthma severity classifications (GINA: mild intermittent, moderate
        persistent, severe persistent)
      - CKD staging statements (stage 3a, stage 4, etc)
      - Heart failure classification (HFrEF, HFpEF, NYHA class)
      - COPD severity (GOLD stage)

    Returns Entity dicts with entity_type='Diagnosis'.
    Does NOT duplicate entities already found by scispaCy (deduplication
    happens in _deduplicate() at the end of extract_entities()).
    """
    CLASSIFICATION_PATTERNS = [
        # Asthma GINA severity
        re.compile(
            r"\b(mild\s+intermittent|mild\s+persistent|moderate\s+persistent"
            r"|severe\s+persistent)\s+asthma\b",
            re.IGNORECASE,
        ),
        # Standalone GINA classification statements
        re.compile(
            r"\basthma\b.{0,40}\b(mild\s+intermittent|mild\s+persistent"
            r"|moderate\s+persistent|severe\s+persistent)\b",
            re.IGNORECASE,
        ),
        # CKD staging
        re.compile(
            r"\bCKD\s+stage\s+[1-5][ab]?\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bchronic\s+kidney\s+disease\s+stage\s+[1-5][ab]?\b",
            re.IGNORECASE,
        ),
        # Heart failure classification
        re.compile(
            r"\bHF(?:rEF|pEF|mrEF)\b",
        ),
        re.compile(
            r"\bNYHA\s+class\s+[IViv]+\b",
            re.IGNORECASE,
        ),
        # GOLD staging for COPD
        re.compile(
            r"\bGOLD\s+(?:stage\s+)?[1-4]\b",
            re.IGNORECASE,
        ),
    ]

    found: list[Entity] = []
    for pat in CLASSIFICATION_PATTERNS:
        for match in pat.finditer(text):
            span_text = match.group(0)
            # Skip if contains newline (paragraph boundary noise)
            if "\\n" in span_text or "\\r" in span_text:
                continue
            found.append(Entity(
                entity_type="Diagnosis",
                text=span_text,
                start_offset=match.start(),
                end_offset=match.end(),
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=span_text.lower().strip(),
            ))
    return found

'''

# Insert before _find_conflicts_by_dictionary
anchor = "def _find_conflicts_by_dictionary(text: str) -> list[Entity]:"
if anchor not in src:
    print("[FAIL] _find_conflicts_by_dictionary anchor not found")
    raise SystemExit(1)
if "_find_conditions_by_pattern" in src:
    print("[SKIP] _find_conditions_by_pattern already defined")
else:
    src = src.replace(anchor, new_condition_finder + anchor, 1)
    print("[OK] Issue 2: _find_conditions_by_pattern() added for GINA/CKD/HF/GOLD classifications")


# ============================================================================
# Issue 3: Add newline guard to _find_conflicts_by_dictionary
# ============================================================================

old_conflict_append = '''            found.append(Entity(
                entity_type="Conflict",
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=None,
            ))'''

new_conflict_append = '''            span_text = text[start:end]
            # Issue 3: skip spans containing newlines (paragraph boundary bleed)
            if "\\n" in span_text or "\\r" in span_text:
                continue
            found.append(Entity(
                entity_type="Conflict",
                text=span_text,
                start_offset=start,
                end_offset=end,
                negated=False,
                icd10_code=None,
                bnf_code=None,
                normalised_value=None,
            ))'''

if old_conflict_append not in src:
    print("[FAIL] Conflict append anchor not found")
    raise SystemExit(1)
src = src.replace(old_conflict_append, new_conflict_append, 1)
print("[OK] Issue 3: newline guard added to _find_conflicts_by_dictionary")


# ============================================================================
# Issue 4: Exclude 'allergic' when followed by a diagnosis noun
# ============================================================================

# Find the CONFLICT_PHRASES list and add a post-match exclusion note,
# then add filtering after the match loop

old_conflict_loop = '''    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()'''

new_conflict_loop = '''    # Issue 4: diagnosis nouns that follow 'allerg*' — these are diagnoses,
    # not allergy-conflict markers (e.g. 'allergic rhinitis', 'allergic asthma')
    _DIAGNOSIS_NOUNS = re.compile(
        r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
        r"|eczema|urticaria|bronchitis|sinusitis)\b",
        re.IGNORECASE,
    )

    for pat in CONFLICT_PHRASES:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            # Issue 4: check if this match is part of a diagnosis compound
            context = text[max(0, start - 5):min(len(text), end + 30)]
            if _DIAGNOSIS_NOUNS.search(context):
                continue'''

if old_conflict_loop not in src:
    print("[FAIL] Conflict loop anchor not found")
    raise SystemExit(1)
src = src.replace(old_conflict_loop, new_conflict_loop, 1)
print("[OK] Issue 4: allergic rhinitis / diagnosis-noun exclusion added")


# ============================================================================
# Wire _find_conditions_by_pattern into extract_entities Pass 2.5
# ============================================================================

old_pass25 = '''    # Pass 2.5: dictionary-based conflict/allergy detection
    entities.extend(_find_conflicts_by_dictionary(text))'''

new_pass25 = '''    # Pass 2.5: pattern-based condition classification + conflict/allergy detection
    entities.extend(_find_conditions_by_pattern(text))
    entities.extend(_find_conflicts_by_dictionary(text))'''

if old_pass25 not in src:
    print("[FAIL] Pass 2.5 anchor not found")
    raise SystemExit(1)
src = src.replace(old_pass25, new_pass25, 1)
print("[OK] _find_conditions_by_pattern wired into Pass 2.5")


# ============================================================================
# Write and verify
# ============================================================================
p.write_text(src, encoding="utf-8", newline="\n")

try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    raise SystemExit(1)

print()
print("=== Summary ===")
print("Issue 1: dapagliflozin + 15 other drugs added to DRUG_NAMES")
print("Issue 2: _find_conditions_by_pattern() added — GINA/CKD/HF/GOLD classifications")
print("Issue 3: newline guard added to _find_conflicts_by_dictionary")
print("Issue 4: allergic rhinitis exclusion added to conflict loop")
print("Guardrail: v1.3 grounding instrument untouched — NER fixes only")
