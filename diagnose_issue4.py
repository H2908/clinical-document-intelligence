"""Diagnose Issue 4 - why DIAGNOSIS_NOUNS_RE exclusion isn't firing."""
import re
import sys
if "nlp.medical_ner" in sys.modules:
    del sys.modules["nlp.medical_ner"]
import nlp.medical_ner as ner

# Check the function source directly
import inspect
src = inspect.getsource(ner._find_conflicts_by_dictionary)
print("=== Current function source ===")
print(src[:1500])
print()

# Test the regex in isolation
DIAGNOSIS_NOUNS_RE = re.compile(
    r"\ballerg\w*\s+(?:rhinitis|conjunctivitis|asthma|dermatitis"
    r"|eczema|urticaria|bronchitis|sinusitis)\b",
    re.IGNORECASE,
)
text = "Past Medical History: seasonal allergic rhinitis. Allergies: NKDA."
pat = r"\ballerg\w+"
for match in re.finditer(pat, text, flags=re.IGNORECASE):
    start, end = match.start(), match.end()
    span_text = text[start:end]
    context = text[max(0, start - 5):min(len(text), end + 30)]
    hit = DIAGNOSIS_NOUNS_RE.search(context)
    print(f"Match: {span_text!r} context: {context!r} hit: {hit}")