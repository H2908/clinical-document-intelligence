"""Step 4: Fill clinical_subject deterministically in the rule layer.

Two related fixes in agents/flag_agent.py:

1. Remove duplicate-key placeholders. Step 3 added "clinical_subject": ""
   between "category" and "description" in each rule's flag dict. But the
   real values were already present at the bottom of each dict (after
   "source_document_id"). Python silently kept the second occurrence, so
   the empty "" was dead code. Remove it for source cleanliness.

2. Fix Rule 1 (ALLERGY_CONFLICT). The existing value
   f"{allergy_term} allergy" conflates the allergy and the drug. Spec
   sec 7 mandates ALLERGY_CONFLICT's clinical_subject is the DRUG
   entity involved, not the allergy phrase. This is the case that
   anchors must-stay-distinct test 2:
       ALLERGY_CONFLICT + clinical_subject="penicillin"
       DRUG_INTERACTION + clinical_subject="penicillin"
   Both have the same clinical_subject ("penicillin"); the matcher
   keeps them distinct via category. With the current "penicillin
   allergy" string, the spec test fails.

   Replacement: drug.get("normalised_value") or drug["text"].strip()
   - prefer the NER's normalised form (dose-stripped, lowercased)
   - fall back to raw text for entities without normalised_value

Rule 2 (POSSIBLE_DUPLICATE_MEDICATION) and Rule 3 (OVERDUE_FOLLOWUP)
are already correct: drug_name and condition respectively.
"""
from pathlib import Path

p = Path("agents/flag_agent.py")
src = p.read_text(encoding="utf-8")


# ============================================================================
# 1. Remove the three empty "clinical_subject": "" placeholders from Step 3
# ============================================================================

# Rule 1 placeholder
old_r1_placeholder = '''                    flags.append({
                        "severity": "HIGH",
                        "category": "ALLERGY_CONFLICT",
                        "clinical_subject": "",
                        "description": ('''
new_r1_placeholder = '''                    flags.append({
                        "severity": "HIGH",
                        "category": "ALLERGY_CONFLICT",
                        "description": ('''

# Rule 2 placeholder
old_r2_placeholder = '''            flags.append({
                "severity": "MEDIUM",
                "category": "POSSIBLE_DUPLICATE_MEDICATION",
                "clinical_subject": "",
                "description": ('''
new_r2_placeholder = '''            flags.append({
                "severity": "MEDIUM",
                "category": "POSSIBLE_DUPLICATE_MEDICATION",
                "description": ('''

# Rule 3 placeholder
old_r3_placeholder = '''            flags.append({
                "severity": "MEDIUM",
                "category": "OVERDUE_FOLLOWUP",
                "clinical_subject": "",
                "description": ('''
new_r3_placeholder = '''            flags.append({
                "severity": "MEDIUM",
                "category": "OVERDUE_FOLLOWUP",
                "description": ('''

placeholder_edits = [
    ("Rule 1", old_r1_placeholder, new_r1_placeholder),
    ("Rule 2", old_r2_placeholder, new_r2_placeholder),
    ("Rule 3", old_r3_placeholder, new_r3_placeholder),
]

for label, old, new in placeholder_edits:
    if old not in src:
        if new in src and '"clinical_subject": ""' not in src.split(new)[0].split('"category": "')[-1] if new in src else False:
            print(f"[SKIP] {label} placeholder already removed")
            continue
        print(f"[FAIL] {label} placeholder anchor not found")
        raise SystemExit(1)
    src = src.replace(old, new, 1)
    print(f"[OK] {label}: empty clinical_subject placeholder removed")


# ============================================================================
# 2. Fix Rule 1: clinical_subject should be the drug, not the allergy phrase
# ============================================================================

old_r1_value = '''                        "source_document_id": drug["document_id"],
                        "clinical_subject": f"{allergy_term} allergy",
                    })'''
new_r1_value = '''                        "source_document_id": drug["document_id"],
                        "clinical_subject": (
                            drug.get("normalised_value")
                            or drug.get("text", "").strip().lower()
                        ),
                    })'''

if 'drug.get("normalised_value")' in src and 'or drug.get("text", "").strip().lower()' in src:
    print("[SKIP] Rule 1 clinical_subject already corrected to drug")
elif old_r1_value not in src:
    print("[FAIL] Rule 1 value anchor not found")
    print("       Looking for the line: 'clinical_subject': f'{allergy_term} allergy'")
    raise SystemExit(1)
else:
    src = src.replace(old_r1_value, new_r1_value, 1)
    print("[OK] Rule 1: clinical_subject now = drug normalised_value (per spec sec 7)")


p.write_text(src, encoding="utf-8", newline="\n")
print()
print("=== Summary ===")
print("agents/flag_agent.py:")
print("  - 3 empty 'clinical_subject': '' placeholders removed")
print("  - Rule 1 (ALLERGY_CONFLICT): clinical_subject is now the drug, not the allergy")
print("  - Rule 2, Rule 3: already correct (drug_name, condition)")
print()
print("Guardrail: v1.3 grounding instrument untouched.")
print()
print("Next: smoke-test that rule output now carries clinical_subject end-to-end.")