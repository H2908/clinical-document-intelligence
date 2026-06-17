"""Test set for agents.audit_agent.hash_flag.

Seven cases proving the tamper-evident hash behaves correctly:
  1. Determinism                  - identical (flag, context) -> identical hash
  2. Key order invariance         - dict insertion order doesn't matter
  3. Missing fields stable        - flag missing optional fields hashes cleanly
  4. None vs ''                   - normalised to same hash
  5. Tampered description detected - description edit -> different hash
  6. Tampered source_quote detected - quote edit -> different hash
  7. Tampered context detected     - model edit -> different hash

Tampering detection is the load-bearing property. If 5/6/7 don't fail
loudly, the hash function is not actually tamper-evident.
"""
from agents.audit_agent import hash_flag


CONTEXT = {
    "model": "claude-sonnet-4-6",
    "prompt_version": "v1.3",
    "temperature": 0.7,
}

# Representative LLM-emitted flag with all fields populated
LLM_FLAG = {
    "severity": "HIGH",
    "category": "AI_ALLERGY_DRUG_CONFLICT",
    "clinical_subject": "penicillin allergy",
    "description": "Documented penicillin allergy (rash, 2018). Avoid beta-lactams.",
    "source_quote": "Patient reports penicillin allergy (rash, 2018). Avoid beta-lactams.",
    "cited_document_id": "doc_375bbc8a",
}

# Representative rule-emitted flag (no source_quote, no cited_document_id)
RULE_FLAG = {
    "severity": "MEDIUM",
    "category": "POSSIBLE_DUPLICATE_MEDICATION",
    "clinical_subject": "atorvastatin",
    "description": "Atorvastatin mentioned across 6 documents.",
    "source_document_id": "doc_bf78e73c",
}


def case_1_determinism():
    """Identical inputs -> identical hash."""
    h1 = hash_flag(LLM_FLAG, CONTEXT)
    h2 = hash_flag(LLM_FLAG, CONTEXT)
    return h1 == h2, f"h1={h1}, h2={h2}"


def case_2_key_order_invariance():
    """Dict insertion order doesn't matter (canonical sorted keys)."""
    reordered = {
        "description": LLM_FLAG["description"],
        "cited_document_id": LLM_FLAG["cited_document_id"],
        "severity": LLM_FLAG["severity"],
        "source_quote": LLM_FLAG["source_quote"],
        "category": LLM_FLAG["category"],
        "clinical_subject": LLM_FLAG["clinical_subject"],
    }
    h_normal = hash_flag(LLM_FLAG, CONTEXT)
    h_reordered = hash_flag(reordered, CONTEXT)
    return h_normal == h_reordered, f"normal={h_normal}, reordered={h_reordered}"


def case_3_missing_fields_stable():
    """Rule flag (missing source_quote, cited_document_id) hashes cleanly."""
    h = hash_flag(RULE_FLAG, CONTEXT)
    return len(h) == 64 and all(c in "0123456789abcdef" for c in h), f"hash={h}"


def case_4_none_vs_empty_string():
    """flag with None for a field equals flag with '' for that field."""
    with_none = dict(RULE_FLAG, source_quote=None, cited_document_id=None)
    with_empty = dict(RULE_FLAG, source_quote="", cited_document_id="")
    return hash_flag(with_none, CONTEXT) == hash_flag(with_empty, CONTEXT), \
        f"none={hash_flag(with_none, CONTEXT)}, empty={hash_flag(with_empty, CONTEXT)}"


def case_5_tampered_description():
    """Editing description after generation must produce a different hash."""
    original = hash_flag(LLM_FLAG, CONTEXT)
    tampered = dict(LLM_FLAG, description="No allergy concerns.")  # benign-looking edit
    tampered_hash = hash_flag(tampered, CONTEXT)
    return original != tampered_hash, \
        f"original={original}, tampered={tampered_hash}"


def case_6_tampered_source_quote():
    """Editing source_quote must produce a different hash."""
    original = hash_flag(LLM_FLAG, CONTEXT)
    tampered = dict(LLM_FLAG, source_quote="Patient has no known allergies.")
    tampered_hash = hash_flag(tampered, CONTEXT)
    return original != tampered_hash, \
        f"original={original}, tampered={tampered_hash}"


def case_7_tampered_context():
    """Changing the model/prompt_version/temperature context must change hash."""
    original = hash_flag(LLM_FLAG, CONTEXT)
    bad_context = dict(CONTEXT, model="gpt-4")
    tampered = hash_flag(LLM_FLAG, bad_context)
    return original != tampered, \
        f"original={original}, with-different-model={tampered}"


CASES = [
    ("1_determinism", case_1_determinism),
    ("2_key_order_invariance", case_2_key_order_invariance),
    ("3_missing_fields_stable", case_3_missing_fields_stable),
    ("4_none_vs_empty_string", case_4_none_vs_empty_string),
    ("5_tampered_description_detected", case_5_tampered_description),
    ("6_tampered_source_quote_detected", case_6_tampered_source_quote),
    ("7_tampered_context_detected", case_7_tampered_context),
]


def main() -> int:
    print("Running 7-case audit hash test set\n")
    passes = 0
    for case_id, fn in CASES:
        ok, detail = fn()
        if ok:
            print(f"  [OK]   {case_id}")
            passes += 1
        else:
            print(f"  [FAIL] {case_id}")
            print(f"         {detail}")
    print(f"\n{passes}/{len(CASES)} passed")
    return 0 if passes == len(CASES) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())