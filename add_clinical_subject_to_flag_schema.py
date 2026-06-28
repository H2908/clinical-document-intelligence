"""Step 3: Add clinical_subject to the produced-flag schema.

Path C scope (Python-side + JSONL only, no Snowflake column). Two
classes of edits in agents/flag_agent.py:

  A) Three rule constructors gain clinical_subject="" as a placeholder
     field. Step 4 will fill this deterministically from the triggering
     entity. For now empty string preserves the dict shape so the
     matcher and validator see a consistent schema.

  B) Three required_fields tuples (one per LLM mode: hybrid, naive,
     thoughtful) gain "clinical_subject". LLM-produced flags missing
     this key are rejected. Step 5 will add the emission instruction
     to the prompts so the LLM populates it.

audit_agent.py is unchanged - clinical_subject already in HASHED_FIELDS.
evaluation/runner.py is unchanged - it writes accepted_flags (full dicts)
to JSONL, so clinical_subject flows automatically once present in the
dict.

Guardrail: v1.3 grounding instrument untouched. This is a schema
extension only - no grounding logic, prompt rubric, or validator
behaviour changes here.
"""
from pathlib import Path

p = Path("agents/flag_agent.py")
src = p.read_text(encoding="utf-8")

# ============================================================================
# A) Three rule constructors - add clinical_subject placeholder
# ============================================================================

# Rule 1 - Allergy vs drug conflicts
old_rule1 = '''                    flags.append({
                        "severity": "HIGH",
                        "category": "ALLERGY_CONFLICT",
                        "description": ('''
new_rule1 = '''                    flags.append({
                        "severity": "HIGH",
                        "category": "ALLERGY_CONFLICT",
                        "clinical_subject": "",
                        "description": ('''

# Rule 2 - Duplicate medications
old_rule2 = '''            flags.append({
                "severity": "MEDIUM",
                "category": "POSSIBLE_DUPLICATE_MEDICATION",
                "description": ('''
new_rule2 = '''            flags.append({
                "severity": "MEDIUM",
                "category": "POSSIBLE_DUPLICATE_MEDICATION",
                "clinical_subject": "",
                "description": ('''

# Rule 3 - Overdue follow-ups
old_rule3 = '''            flags.append({
                "severity": "MEDIUM",
                "category": "OVERDUE_FOLLOWUP",
                "description": ('''
new_rule3 = '''            flags.append({
                "severity": "MEDIUM",
                "category": "OVERDUE_FOLLOWUP",
                "clinical_subject": "",
                "description": ('''

rule_edits = [
    ("Rule 1 (ALLERGY_CONFLICT)",        old_rule1, new_rule1),
    ("Rule 2 (DUPLICATE_MEDICATION)",    old_rule2, new_rule2),
    ("Rule 3 (OVERDUE_FOLLOWUP)",        old_rule3, new_rule3),
]

for label, old, new in rule_edits:
    if '"clinical_subject"' in src and old.replace('"description": (', '"clinical_subject": "",\n                        "description": (') not in src:
        # already partly applied in some form - be defensive
        pass
    if old not in src:
        # Check if already patched (idempotent skip)
        already_marker = old.replace('"description": (',
            '"clinical_subject": "",\n' +
            ' ' * (len(old.split('\n')[-1]) - len('"description": (')) +
            '"description": (')
        # Simpler check: does the rule already have clinical_subject in its dict?
        if old.split('"category"')[0] in src:
            # find the rule's dict and check for clinical_subject between category and description
            print(f"[CHECK] {label}: anchor not found verbatim. Will inspect manually.")
        print(f"[FAIL] anchor for {label} not found")
        raise SystemExit(1)
    src = src.replace(old, new, 1)
    print(f"[OK] {label}: clinical_subject placeholder added to rule constructor")


# ============================================================================
# B) Three required_fields tuples - add clinical_subject
# ============================================================================
# All three tuples have identical content; we replace each occurrence in turn
# using a positional counter to be sure we touch all three.

old_required_block_form_1 = '''    required_fields = (
        "severity", "category", "description",
        "cited_document_id", "source_quote",
    )'''
new_required_block_form_1 = '''    required_fields = (
        "severity", "category", "clinical_subject", "description",
        "cited_document_id", "source_quote",
    )'''

old_required_block_form_2 = '''    required_fields = ("severity", "category", "description",
                       "cited_document_id", "source_quote")'''
new_required_block_form_2 = '''    required_fields = ("severity", "category", "clinical_subject", "description",
                       "cited_document_id", "source_quote")'''

count_form_1 = src.count(old_required_block_form_1)
count_form_2 = src.count(old_required_block_form_2)
print(f"Form-1 (multiline) required_fields tuples found: {count_form_1}")
print(f"Form-2 (compact)   required_fields tuples found: {count_form_2}")

if count_form_1 + count_form_2 == 0 and 'clinical_subject' in src.split('required_fields')[1][:200] if 'required_fields' in src else False:
    print("[SKIP] required_fields already updated")
elif count_form_1 + count_form_2 != 3:
    print(f"[FAIL] expected 3 required_fields tuples, found {count_form_1 + count_form_2}")
    raise SystemExit(1)
else:
    if count_form_1 > 0:
        src = src.replace(old_required_block_form_1, new_required_block_form_1)
        print(f"[OK] Form-1: {count_form_1} required_fields tuples updated")
    if count_form_2 > 0:
        src = src.replace(old_required_block_form_2, new_required_block_form_2)
        print(f"[OK] Form-2: {count_form_2} required_fields tuples updated")


p.write_text(src, encoding="utf-8", newline="\n")
print()
print("=== Summary ===")
print("agents/flag_agent.py:")
print("  - 3 rule constructors emit clinical_subject='' (Step 4 fills)")
print("  - 3 required_fields tuples include clinical_subject (LLM must emit)")
print()
print("audit_agent.py: unchanged (clinical_subject already in HASHED_FIELDS)")
print("evaluation/runner.py: unchanged (writes accepted_flags dicts to JSONL)")
print()
print("Guardrail: v1.3 grounding instrument untouched.")