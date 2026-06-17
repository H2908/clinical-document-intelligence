"""Smoke test BNF integration on real document. Print drug entities with codes."""
from parsers.pdf_parser import parse_pdf
from nlp.medical_ner import extract_entities

text = parse_pdf("data/synthetic/documents/patient_001/01_GP_Referral_Thompson_12Jan2024.pdf")
entities = extract_entities(text)

drugs = [e for e in entities if e["entity_type"] == "Drug"]
print(f"Drug entities in patient_001 doc 01: {len(drugs)}")
print()
for d in drugs:
    print(f"  text={d['text']!r:<35} norm={d['normalised_value']!r:<25} bnf={d['bnf_code']!r}")

with_bnf = [d for d in drugs if d["bnf_code"]]
print(f"\nWith BNF code: {len(with_bnf)} / {len(drugs)}")