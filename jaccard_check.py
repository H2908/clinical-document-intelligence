"""Pairwise content-token Jaccard for patient_001's 3 documents.

Spec requires pairwise Jaccard < 0.5 (genuinely distinct documents,
not the near-duplicate degenerate input of pat_test_01).
"""
import re
from pathlib import Path
from parsers.pdf_parser import parse_pdf

docs = sorted(Path("data/synthetic/documents/patient_001").glob("*.pdf"))
texts = [parse_pdf(str(d)) for d in docs]

def toks(t: str) -> set[str]:
    return set(re.findall(r"[a-z]+", t.lower()))

tokens = [toks(t) for t in texts]

print(f"{'Doc A':<35} {'Doc B':<35} {'Jaccard':>8}  {'Verdict':>7}")
print("-" * 88)
all_pass = True
for i in range(len(tokens)):
    for j in range(i + 1, len(tokens)):
        inter = len(tokens[i] & tokens[j])
        union = len(tokens[i] | tokens[j])
        j_idx = inter / union if union else 0.0
        verdict = "PASS" if j_idx < 0.5 else "FAIL"
        if verdict == "FAIL":
            all_pass = False
        print(f"{docs[i].name[:35]:<35} {docs[j].name[:35]:<35} {j_idx:>8.3f}  {verdict:>7}")

print()
print("OVERALL:", "PASS" if all_pass else "FAIL")