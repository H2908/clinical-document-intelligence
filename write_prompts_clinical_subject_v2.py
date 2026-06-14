"""Apply clinical_subject edits to agents/prompts.py - final attempt
with anchors taken from a verified decode of the live file.

Six replacements:
  1. Schema docblock
  2a. FLAG_SECOND_PASS_VERSION v1.2 -> v1.3 (only 1 occurrence)
  2b. Hybrid prompt schema list ("exactly these six fields")
  2c. Hybrid prompt example JSON
  3a. FLAG_LLM_THOUGHTFUL_VERSION v1.0 -> v1.1 (appears TWICE - bump both)
  3b. Thoughtful prompt schema list (followed by blank line + Output ONLY)
  3c. Thoughtful prompt example JSON
  4a. FLAG_LLM_NAIVE_VERSION v1.0 -> v1.1 (appears TWICE - bump both)
  4b. Naive prompt schema list (followed directly by Output ONLY, no blank)

Atomic: aborts if any anchor fails, file unchanged.
"""
from pathlib import Path

p = Path("agents/prompts.py")
src = p.read_text(encoding="utf-8")
txt = src

def apply(label, old, new, expected_count=1):
    global txt
    n = txt.count(old)
    if n != expected_count:
        print(f"[FAIL] {label}: matched {n}, expected {expected_count}")
        raise SystemExit(1)
    txt = txt.replace(old, new)
    print(f"[OK]   {label} ({expected_count})")

# 1. Schema docblock
apply("1. schema docblock",
'''#   "cited_document_id": str,    # must appear in the patient's documents
#   "source_quote":      str,    # verbatim sentence from the cited document
#   "grounding_status":  None    # agent leaves blank; metric module fills
#                                # one of: "grounded" | "misattributed"
#                                # | "fabricated"
# }''',
'''#   "cited_document_id": str,    # must appear in the patient's documents
#   "source_quote":      str,    # verbatim sentence from the cited document
#   "grounding_status":  None,   # agent leaves blank; metric module fills
#                                # one of: "grounded" | "misattributed"
#                                # | "fabricated"
#   "clinical_subject":  str     # canonical lower-case noun phrase the flag
#                                # is about (e.g. "atorvastatin",
#                                # "penicillin allergy", "heart failure",
#                                # "hba1c monitoring"). Used by the matcher
#                                # to deduplicate paraphrased restatements.
# }''')

# 2a. Hybrid version bump
apply("2a. hybrid version bump",
    'FLAG_SECOND_PASS_VERSION = "v1.2"',
    'FLAG_SECOND_PASS_VERSION = "v1.3"')

# 2b. Hybrid prompt schema list
apply("2b. hybrid schema list",
'''2. Each flag MUST have exactly these six fields:
   - "severity":          "HIGH" | "MEDIUM" | "LOW"
   - "category":          short snake-case code (e.g. "AI_ALLERGY_DRUG_CONFLICT")
   - "description":       natural language for the doctor, under 30 words
   - "cited_document_id": the document_id that supports the flag
   - "source_quote":      see SOURCE_QUOTE REQUIREMENTS below
   - "grounding_status":  null  (leave blank - the system fills this later)''',
'''2. Each flag MUST have exactly these seven fields:
   - "severity":          "HIGH" | "MEDIUM" | "LOW"
   - "category":          short snake-case code (e.g. "AI_ALLERGY_DRUG_CONFLICT")
   - "description":       natural language for the doctor, under 30 words
   - "clinical_subject":  canonical lower-case noun phrase the flag is about
                          (e.g. "atorvastatin", "penicillin allergy",
                          "heart failure", "hba1c monitoring"). Not a sentence.
                          One subject per flag. Used by downstream matching
                          to merge paraphrased restatements of the same risk.
   - "cited_document_id": the document_id that supports the flag
   - "source_quote":      see SOURCE_QUOTE REQUIREMENTS below
   - "grounding_status":  null  (leave blank - the system fills this later)''')

# 2c. Hybrid prompt example
apply("2c. hybrid example",
'''    "severity": "HIGH",
    "category": "AI_ALLERGY_DRUG_CONFLICT",
    "description": "Patient has documented penicillin allergy; verify no beta-lactam prescribed.",
    "cited_document_id": "doc_abc12345",
    "source_quote": "Patient reports penicillin allergy - rash on exposure 2019. Avoid beta-lactams.",
    "grounding_status": null''',
'''    "severity": "HIGH",
    "category": "AI_ALLERGY_DRUG_CONFLICT",
    "description": "Patient has documented penicillin allergy; verify no beta-lactam prescribed.",
    "clinical_subject": "penicillin allergy",
    "cited_document_id": "doc_abc12345",
    "source_quote": "Patient reports penicillin allergy - rash on exposure 2019. Avoid beta-lactams.",
    "grounding_status": null''')

# 3a. Thoughtful version bump - appears TWICE (template region + stray block)
apply("3a. thoughtful version bump",
    'FLAG_LLM_THOUGHTFUL_VERSION = "v1.0"',
    'FLAG_LLM_THOUGHTFUL_VERSION = "v1.1"',
    expected_count=1)
# Stray reassignment near bottom has different whitespace (extra spaces)
apply("3a-bis. thoughtful version stray bump",
    'FLAG_LLM_THOUGHTFUL_VERSION  = "v1.0"',
    'FLAG_LLM_THOUGHTFUL_VERSION  = "v1.1"',
    expected_count=1)

# 3b. Thoughtful schema list - the version WITH "exactly these six fields"
apply("3b. thoughtful schema list",
'''2. Each flag MUST have exactly these six fields:
   - "severity":          "HIGH" | "MEDIUM" | "LOW"
   - "category":          short snake-case code (e.g. "ALLERGY_CONFLICT")
   - "description":       natural language for the doctor, under 30 words
   - "cited_document_id": the document_id that supports the flag
   - "source_quote":      verbatim sentence from the cited document
   - "grounding_status":  null''',
'''2. Each flag MUST have exactly these seven fields:
   - "severity":          "HIGH" | "MEDIUM" | "LOW"
   - "category":          short snake-case code (e.g. "ALLERGY_CONFLICT")
   - "description":       natural language for the doctor, under 30 words
   - "clinical_subject":  canonical lower-case noun phrase the flag is about
                          (e.g. "atorvastatin", "penicillin allergy",
                          "heart failure", "hba1c monitoring"). Not a sentence.
                          One subject per flag.
   - "cited_document_id": the document_id that supports the flag
   - "source_quote":      verbatim sentence from the cited document
   - "grounding_status":  null''')

# 3c. Thoughtful example JSON
apply("3c. thoughtful example",
'''    "severity": "HIGH",
    "category": "ALLERGY_CONFLICT",
    "description": "Patient has documented penicillin allergy; verify no beta-lactam prescribed.",
    "cited_document_id": "doc_abc12345",
    "source_quote": "Patient reports penicillin allergy - rash on exposure 2019.",
    "grounding_status": null''',
'''    "severity": "HIGH",
    "category": "ALLERGY_CONFLICT",
    "description": "Patient has documented penicillin allergy; verify no beta-lactam prescribed.",
    "clinical_subject": "penicillin allergy",
    "cited_document_id": "doc_abc12345",
    "source_quote": "Patient reports penicillin allergy - rash on exposure 2019.",
    "grounding_status": null''')

# 4a. Naive version bump - appears TWICE
apply("4a. naive version bump",
    'FLAG_LLM_NAIVE_VERSION = "v1.0"',
    'FLAG_LLM_NAIVE_VERSION = "v1.1"')
apply("4a-bis. naive version stray bump",
    'FLAG_LLM_NAIVE_VERSION       = "v1.0"',
    'FLAG_LLM_NAIVE_VERSION       = "v1.1"')

# 4b. Naive prompt schema list - simpler "Each flag should include" structure
apply("4b. naive schema list",
'''Return a JSON array of risk flags. Each flag should include:
  - "severity":          "HIGH" | "MEDIUM" | "LOW"
  - "category":          short snake-case code
  - "description":       short clinical description for the doctor
  - "cited_document_id": which document supports this flag
  - "source_quote":      a sentence from the document showing why
  - "grounding_status":  null''',
'''Return a JSON array of risk flags. Each flag should include:
  - "severity":          "HIGH" | "MEDIUM" | "LOW"
  - "category":          short snake-case code
  - "description":       short clinical description for the doctor
  - "clinical_subject":  canonical lower-case noun phrase the flag is about
                         (e.g. "atorvastatin", "penicillin allergy",
                         "heart failure", "hba1c monitoring"). Not a sentence.
                         One subject per flag.
  - "cited_document_id": which document supports this flag
  - "source_quote":      a sentence from the document showing why
  - "grounding_status":  null''')

p.write_text(txt, encoding="utf-8", newline="\n")
print(f"\nWrote {p}")
print(f"Lines now: {len(txt.splitlines())}")
print(f"clinical_subject occurrences: {txt.count('clinical_subject')}")