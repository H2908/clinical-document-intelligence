"""Trace where 'seasonal allergic rhinitis' Conflict comes from."""
import sys
if "nlp.medical_ner" in sys.modules:
    del sys.modules["nlp.medical_ner"]
import nlp.medical_ner as ner
import spacy

nlp = spacy.load("en_core_sci_sm")
text = "Past Medical History: seasonal allergic rhinitis. Allergies: NKDA."

doc = nlp(text)
print("scispaCy entities:")
for ent in doc.ents:
    print(f"  {ent.text!r} label={ent.label_}")

print()
print("_classify_span results:")
for ent in doc.ents:
    result = ner._classify_span(text, ent.text, ent.start_char, ent.end_char)
    print(f"  {ent.text!r} -> {result}")