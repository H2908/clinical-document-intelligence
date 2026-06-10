"""
Verification: re-run Guard 4 logic against the 13 dev quotes using
spaCy's STOP_WORDS plus the 7-word clinical-generic set.

Each entry below is a (description, category, quote) triple capturing
what the LLM produced on pat_test_01. We check whether Guard 4 would
silently kill any legitimately grounded flag because spaCy stripped
its real clinical subject word.
"""
import re
from spacy.lang.en.stop_words import STOP_WORDS

CLINICAL_GENERIC = {
    "patient", "documented", "noted", "listed",
    "verify", "confirm", "doctor",
}
STOPWORDS_AND_GENERIC = STOP_WORDS | CLINICAL_GENERIC

# Real (description, category, quote) tuples from yesterday's runs on pat_test_01
flags = [
    # llm_thoughtful run
    (
        "LVEF 32% with ischaemic heart disease documented, but no ACE inhibitor, beta-blocker, or MRA listed in current medications.",
        "POSSIBLE_TREATMENT_GAP",
        "LVEF measured at 32%. Patient reports symptoms consistent with NYHA class II.",
    ),
    (
        "Routine bloods including U&E and eGFR were ordered; no results documented in any record.",
        "INVESTIGATION_NO_RESULT",
        "Routine bloods including U&E; eGFR in 4 weeks",
    ),
    (
        "Referral to heart failure nurse for medication titration within 2 weeks was planned.",
        "FOLLOW_UP_STATUS_UNKNOWN",
        "Refer to heart failure nurse for medication titration within 2 weeks",
    ),
    (
        "Four identical clinic letters exist in the record.",
        "DUPLICATE_DOCUMENTS",
        "CARDIOLOGY CLINIC LETTER\nPatient: Sarah Evans\nDOB: 1987-03-23 (age 39)\nNHS Number: 101 226 9166",
    ),
    (
        "Penicillin allergy (rash 2019) and instruction to avoid beta-lactams is documented.",
        "ALLERGY_DOCUMENTED",
        "Patient reports penicillin allergy \u2014 rash on exposure in 2019. Avoid \u03b2-lactams.",
    ),
    # llm_naive run
    (
        "Patient has LVEF 32% (HFrEF) but is not recorded as being on an ACE inhibitor/ARB/ARNI, beta-blocker, or MRA.",
        "missing_medication",
        "Current Cardiac Medications: Atorvastatin 40 mg \u2014 40 mg ON; Aspirin 75 mg \u2014 75 mg OD",
    ),
    (
        "No antiplatelet or anticoagulation therapy beyond aspirin is documented for ischaemic heart disease.",
        "missing_medication",
        "Echocardiogram confirms ischaemic heart disease (ICD-10: I25.9). LVEF measured at 32%.",
    ),
    (
        "Routine bloods including U&E and eGFR were ordered 4 weeks from 22 May 2026.",
        "investigation_not_followed_up",
        "Routine bloods including U&E, eGFR in 4 weeks",
    ),
    (
        "Repeat echocardiogram was planned at 6 months from 22 May 2026.",
        "investigation_not_followed_up",
        "Repeat echocardiogram in 6 months",
    ),
    (
        "Referral to heart failure nurse for medication titration was planned within 2 weeks of 22 May 2026.",
        "referral_not_confirmed",
        "Refer to heart failure nurse for medication titration within 2 weeks",
    ),
    (
        "Penicillin allergy (rash 2019) is noted with instruction to avoid all beta-lactams.",
        "allergy_documentation",
        "Patient reports penicillin allergy \u2014 rash on exposure in 2019. Avoid \u03b2-lactams.",
    ),
    (
        "The same cardiology clinic letter dated 22 May 2026 appears four times in the chart.",
        "duplicate_documents",
        "Date: 22 May 2026 ... Patient: Sarah Evans ... Dr. James Mitchell, Consultant Cardiologist",
    ),
    (
        "Atorvastatin is prescribed at 40 mg rather than the guideline-recommended high-intensity dose of 80 mg.",
        "statin_dose_review",
        "Atorvastatin 40 mg \u2014 40 mg ON",
    ),
]


def compute_subject_words(description: str, category: str) -> tuple[set, set, set]:
    """Mirror the Guard 4 logic. Return (raw_words, stripped_words, removed_by_stopwords)."""
    subject_text = f"{category} {description}".lower()
    subject_text = re.sub(r"\bai[_ ]", " ", subject_text)
    raw = set(re.findall(r"[a-z]{4,}", subject_text))
    stripped = raw - STOPWORDS_AND_GENERIC
    removed = raw & STOPWORDS_AND_GENERIC
    return raw, stripped, removed


def quote_words(quote: str) -> set:
    return set(re.findall(r"[a-z]{4,}", quote.lower()))


print(f"Stopword pool: spaCy STOP_WORDS ({len(STOP_WORDS)}) + clinical-generic ({len(CLINICAL_GENERIC)}) = {len(STOPWORDS_AND_GENERIC)}\n")

any_concerns = False
for i, (desc, cat, quote) in enumerate(flags, 1):
    raw, stripped, removed = compute_subject_words(desc, cat)
    qw = quote_words(quote)
    passes = bool(stripped and (stripped & qw))

    print(f"--- Flag {i}: {cat} ---")
    print(f"  raw subject words ({len(raw)}): {sorted(raw)[:10]}{'...' if len(raw) > 10 else ''}")
    print(f"  stripped by stopwords: {sorted(removed) if removed else '(none)'}")
    print(f"  remaining subject words: {sorted(stripped)[:10]}{'...' if len(stripped) > 10 else ''}")
    print(f"  shared with quote: {sorted(stripped & qw) if stripped & qw else '(NONE - WOULD FAIL GUARD 4)'}")
    print(f"  Guard 4 verdict: {'PASS' if passes else 'FAIL'}")

    # The risky case: a word got stripped that might have been the real subject
    if removed:
        # Was the removed word in the quote? If yes, stripping it cost us a real overlap.
        ate_real_subject = bool(removed & qw)
        if ate_real_subject:
            ate = removed & qw
            also_other_overlap = bool(stripped & qw)
            severity = "SAFE" if also_other_overlap else "CRITICAL"
            print(f"  >>> {severity}: stopword pool stripped {sorted(ate)}, which IS in the quote.")
            if not also_other_overlap:
                print(f"  >>> This is a Guard 4 silent failure — flag would fail without this overlap.")
                any_concerns = True
            else:
                print(f"  >>> But other words still overlap, so Guard 4 passes anyway. No-op risk.")
    print()

print(f"\n=== Verdict ===")
if any_concerns:
    print("CRITICAL: at least one quote would silently fail Guard 4 because spaCy stripped its real subject word.")
    print("DO NOT freeze the instrument until the un-strip exception is added.")
else:
    print("SAFE: no flag has its only subject overlap eaten by the stopword pool.")
    print("Cleared to freeze the instrument config.")