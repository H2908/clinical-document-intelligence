"""Inspect raw MTSamples text for allergy mentions and potential
duplicate-medication patterns, to determine whether rules_only=0
reflects 'nothing to flag' or 'rules not firing on real formatting'.
"""
import csv

with open("data/mtsamples/mtsamples.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

TARGETS = {
    "pneumonia_copd_discharge": " Pneumonia & COPD - Discharge Summary ",
    "afib_consult": " Atrial Fibrillation - Consult ",
}

for key, name in TARGETS.items():
    row = next(r for r in rows if r.get("sample_name") == name)
    text = row["transcription"]
    print(f"\n{'='*70}")
    print(f"{key}")
    print(f"{'='*70}")

    # Check for allergy mentions
    lower = text.lower()
    if "allerg" in lower:
        idx = lower.find("allerg")
        print(f"ALLERGY MENTION FOUND at char {idx}:")
        print(f"  ...{text[max(0,idx-80):idx+150]}...")
    else:
        print("No 'allerg' substring found anywhere in text.")

    # Print full medication-related lines for manual duplicate check
    print("\nAll lines containing 'mg' (dose indicators):")
    for line in text.replace(",", "\n").split("\n"):
        if "mg" in line.lower() or "medication" in line.lower():
            print(f"  {line.strip()!r}")