"""Check what scispaCy extracts from the asthma severity sentence."""
from nlp.medical_ner import extract_entities

text = (
    "Assessment: Symptom pattern, ACT score, PEFR variability, and spirometry are "
    "consistent with moderate persistent asthma (GINA classification, step 3). "
    "Patient previously on reliever-only therapy which is inadequate given current control. "
    "Requires initiation of inhaled corticosteroid as preventer."
)

entities = extract_entities(text)
print("Entities extracted:")
for e in entities:
    print(f"  [{e['entity_type']}] {e['text']!r}")