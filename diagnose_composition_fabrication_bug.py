"""Check whether the composition-fabrication verdicts on MTSamples
quotes like 'Metformin 1000 mg' are correct (genuinely non-contiguous)
or a guard bug (quote IS contiguous in the actual extracted text, but
the n-gram-run check is miscounting).
"""
from worker.document_processor import process_document
from pathlib import Path
from datetime import date

result = process_document(
    file_path=Path("data/mtsamples/pdfs/pneumonia_copd_discharge.pdf"),
    document_id="diag_test",
    patient_id="diag",
    document_date=date.today(),
    doc_type="discharge_summary",
)
text = result["document"]["extracted_text"]

quote = "Metformin 1000 mg"
idx = text.find(quote)
print(f"Exact substring found at index: {idx}")
if idx >= 0:
    print(f"Context: ...{text[max(0,idx-40):idx+60]!r}...")
else:
    print("NOT found as exact substring. Searching case-insensitive / whitespace-normalised...")
    import re
    normalised = re.sub(r"\s+", " ", text)
    idx2 = normalised.find(quote)
    print(f"Whitespace-normalised search: index {idx2}")
    if idx2 >= 0:
        print(f"Context: ...{normalised[max(0,idx2-40):idx2+60]!r}...")