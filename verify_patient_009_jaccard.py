"""Pairwise content-token Jaccard check for patient_009 documents.

Spec requires pairwise Jaccard < 0.5 on content tokens (the three docs
must be substantively distinct, not paraphrases of each other).

Method: extract text via PyMuPDF, tokenise on word characters, lowercase,
drop common English stopwords, drop one-char tokens. Jaccard over the
resulting content-token sets.
"""
from pathlib import Path
import re
import fitz  # PyMuPDF

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "this", "that", "these",
    "those", "it", "its", "as", "but", "if", "then", "so", "no", "not",
    "patient", "doctor", "dr", "date", "name", "dob", "nhs", "address",
    "mr", "mrs", "ms", "year", "old", "age", "yours", "sincerely", "dear",
    "today", "yesterday", "review", "letter", "summary", "report",
    "active", "current", "history", "examination", "assessment", "plan",
    "investigations", "allergies", "medications", "diagnosis", "conditions",
}

def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def content_tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z]+", text.lower())
    return {t for t in toks if len(t) > 1 and t not in STOPWORDS}

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)

OUT_DIR = Path("data/synthetic/documents/patient_009")
pdfs = sorted(OUT_DIR.glob("*.pdf"))
print(f"PDFs: {[p.name for p in pdfs]}")
print()

tokens = {p.name: content_tokens(extract_text(p)) for p in pdfs}
for name, toks in tokens.items():
    print(f"  {name}: {len(toks)} content tokens")
print()

print(f"{'doc A':<48} {'doc B':<48} {'Jaccard':>8}")
print("-" * 110)
ok = True
for i, a in enumerate(pdfs):
    for b in pdfs[i+1:]:
        j = jaccard(tokens[a.name], tokens[b.name])
        status = "" if j < 0.5 else "  [FAIL >= 0.5]"
        if j >= 0.5:
            ok = False
        print(f"{a.name:<48} {b.name:<48} {j:>8.3f}{status}")

print()
print("Verdict:", "[OK] all pairwise Jaccard < 0.5" if ok else "[FAIL] some pair >= 0.5")
