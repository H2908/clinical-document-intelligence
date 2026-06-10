"""Test whether 30 char / 6 word floor kills any legitimate clinical quote."""
import re

MIN_QUOTE_CHARS = 30
MIN_QUOTE_WORDS = 6


def fails_floor(quote):
    chars = len(quote)
    words = len(re.findall(r"\w+", quote))
    return chars < MIN_QUOTE_CHARS or words < MIN_QUOTE_WORDS


def report(quote):
    chars = len(quote)
    words = len(re.findall(r"\w+", quote))
    status = "FAIL" if fails_floor(quote) else "PASS"
    print(f"  [{status}] chars={chars:3d} words={words:2d}  {quote[:70]!r}")


dev_quotes = [
    "LVEF measured at 32%. Patient reports symptoms consistent with NYHA class II.",
    "Routine bloods including U&E; eGFR in 4 weeks",
    "Refer to heart failure nurse for medication titration within 2 weeks",
    "CARDIOLOGY CLINIC LETTER\nPatient: Sarah Evans\nDOB: 1987-03-23 (age 39)\nNHS Number: 101 226 9166",
    "Patient reports penicillin allergy \u2014 rash on exposure in 2019. Avoid \u03b2-lactams.",
]

naive_quotes = [
    "Current Cardiac Medications: Atorvastatin 40 mg \u2014 40 mg ON; Aspirin 75 mg \u2014 75 mg OD",
    "Echocardiogram confirms ischaemic heart disease (ICD-10: I25.9). LVEF measured at 32%.",
    "Routine bloods including U&E, eGFR in 4 weeks",
    "Repeat echocardiogram in 6 months",
    "Refer to heart failure nurse for medication titration within 2 weeks",
    "Patient reports penicillin allergy \u2014 rash on exposure in 2019. Avoid \u03b2-lactams.",
    "Date: 22 May 2026 ... Patient: Sarah Evans ... Dr. James Mitchell, Consultant Cardiologist",
    "Atorvastatin 40 mg \u2014 40 mg ON",
]


print(f"\n=== thoughtful run quotes ({len(dev_quotes)}) ===")
for q in dev_quotes:
    report(q)

print(f"\n=== naive run quotes ({len(naive_quotes)}) ===")
for q in naive_quotes:
    report(q)

n_fail_thoughtful = sum(1 for q in dev_quotes if fails_floor(q))
n_fail_naive = sum(1 for q in naive_quotes if fails_floor(q))

print(f"\n=== verdict ===")
print(f"  thoughtful: {n_fail_thoughtful} of {len(dev_quotes)} would fail the floor")
print(f"  naive:      {n_fail_naive} of {len(naive_quotes)} would fail the floor")
print(f"  threshold:  {MIN_QUOTE_CHARS} chars AND {MIN_QUOTE_WORDS} words")