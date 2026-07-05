from extraction import extract_from_pdf

result = extract_from_pdf("../data/mtsamples/pdfs/pneumonia_copd_discharge.pdf")
print(f"Extracted text length: {len(result['extracted_text'])}")
print(f"Entities found: {len(result['entities'])}")
for e in result["entities"][:10]:
    print(f"  [{e['entity_type']}] {e['text']!r} negated={e['negated']}")