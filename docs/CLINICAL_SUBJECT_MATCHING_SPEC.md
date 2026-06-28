# Clinical Subject Matching Specification
**Version:** 1.0  
**Date:** 2026-06-28  
**Status:** Canonical — gates flag-identity fix (Steps 1–10)  
**Author:** H2908  

---

## 1. Purpose

This spec defines `clinical_subject`: the field that, together with `category`, uniquely
identifies a flag for the purposes of deduplication, reproducibility measurement, and
evaluation matching.

A flag's identity is the pair **(category, clinical_subject)**. Two flags with the same
identity are the same clinical concern and may be merged in evaluation. Two flags with
different identities are different clinical concerns and must stay distinct regardless of
surface-word overlap.

---

## 2. Definition

**clinical_subject** is a normalised noun phrase naming the specific clinical entity —
drug, investigation, condition, measurement, or care gap — that the flag is *about*.

It is NOT:
- The condition that provides context ("heart failure" is context; "ACEi" is the subject
  when the flag is about a missing ACEi in a heart failure patient)
- The clinical concern or verb phrase ("eGFR declining" is a concern; "eGFR" is the subject)
- A severity descriptor ("dangerously low eGFR" → subject is "eGFR")
- A category restatement ("drug interaction" is a category, not a subject)

**Rule:** strip the concern, strip the context, strip the severity — what entity remains?
That entity is the clinical_subject.

---

## 3. Identity Rule

Two flags have the same identity if and only if ALL THREE hold:

```
flag_A.category          == flag_B.category          (exact string match)
flag_A.clinical_subject  == flag_B.clinical_subject  (normalised exact match, see §5)
```

Severity is explicitly excluded from identity. Two flags with the same category and
clinical_subject but different severity are the SAME clinical concern at different
urgency levels. In evaluation, the higher-severity flag takes precedence.

---

## 4. The Four Must-Stay-Distinct Cases

These cases define where the matcher must NOT merge. They are the primary correctness
constraints on the spec.

### Case 1 — Same condition, different clinical subject

| Field | Flag A | Flag B |
|-------|--------|--------|
| category | TREATMENT_GAP | TREATMENT_GAP |
| clinical_subject | **ACEi** | **echocardiogram** |
| context | heart failure patient | heart failure patient |
| concern | no ACEi prescribed | echocardiogram overdue |

**Why distinct:** the clinical subject differs. Medication gap and investigation gap are
different problems requiring different actions. A matcher that merges on condition context
alone ("heart failure") fails here.

**Spec constraint:** clinical_subject must identify the entity the flag acts on, not the
condition that provides clinical context.

### Case 2 — Same subject, different category

| Field | Flag A | Flag B |
|-------|--------|--------|
| category | ALLERGY_CONFLICT | DRUG_INTERACTION |
| clinical_subject | **penicillin** | **penicillin** |
| concern | allergy undocumented | beta-lactam prescribed |

**Why distinct:** the category differs. Same drug, same patient, but these are genuinely
different clinical problems requiring different actions (documentation vs. prescribing
change). The identity rule requires both category AND clinical_subject to match.

**Spec constraint:** category is load-bearing in the identity pair. Subject-only matching
is insufficient.

### Case 3 — Same category and subject, different severity

| Field | Flag A | Flag B |
|-------|--------|--------|
| category | MONITORING_GAP | MONITORING_GAP |
| clinical_subject | **HbA1c** | **HbA1c** |
| severity | HIGH | MEDIUM |
| concern | last seen 18mo ago, HbA1c 11.2% | last seen 8mo ago, HbA1c 8.4% |

**Why distinct:** these ARE the same clinical concern (HbA1c monitoring overdue in
diabetes). They must stay distinct in evaluation because severity reflects different gold
tiers. A HIGH flag must match a HIGH gold flag; a MEDIUM flag must match a MEDIUM gold
flag. Cross-severity matching inflates precision on tier-1 flags.

**Spec constraint:** severity is NOT part of the identity pair. But the evaluation matcher
must track severity separately and enforce tier-level matching. Two flags with the same
(category, clinical_subject) but different severity are the same identity; the
higher-severity instance is the canonical one for deduplication but evaluation reports
per-tier.

### Case 4 — Paraphrase that crosses clinical meaning

| Field | Flag A | Flag B |
|-------|--------|--------|
| category | MONITORING_GAP | CLINICAL_DETERIORATION |
| clinical_subject | **eGFR** | **eGFR** |
| concern | eGFR not checked in 6 months | eGFR declining — renal deterioration |

**Why distinct:** category differs (MONITORING_GAP vs. CLINICAL_DETERIORATION). Subject
is the same ("eGFR") but the clinical action is entirely different: book a blood test vs.
urgent nephrology review. The identity rule correctly keeps them distinct because category
is part of the pair.

**Spec constraint:** Case 4 is actually handled correctly by the base identity rule. It is
listed here to confirm that surface-word overlap in clinical_subject is not sufficient for
merging — the category must also match.

---

## 5. The Four Must-Merge Cases

These cases define where the matcher MUST merge to avoid false-positive distinct flags.

### Merge 1 — Capitalisation and whitespace variants

| Flag A clinical_subject | Flag B clinical_subject |
|-------------------------|-------------------------|
| `Metformin` | `metformin` |
| `ACE inhibitor` | `ace inhibitor` |

**Normalisation:** lowercase, strip leading/trailing whitespace, collapse internal
whitespace to single space.

### Merge 2 — Established abbreviation ↔ full-form pairs

| Flag A clinical_subject | Flag B clinical_subject |
|-------------------------|-------------------------|
| `ACEi` | `ACE inhibitor` |
| `eGFR` | `estimated glomerular filtration rate` |
| `HbA1c` | `glycated haemoglobin` |
| `LVEF` | `left ventricular ejection fraction` |

**Normalisation:** maintain a curated abbreviation table. Only listed pairs merge; unknown
abbreviations do NOT merge (conservative default).

### Merge 3 — Minor morphological variation, same referent

| Flag A clinical_subject | Flag B clinical_subject |
|-------------------------|-------------------------|
| `Furosemide` | `furosemide 80mg` |
| `Spironolactone` | `spironolactone 25 mg OD` |

**Normalisation:** strip dose suffix from drug names (regex `\s+\d+[\d.]*\s*(mg|mcg|g|ml
|units?|iu)\b.*$`). The normalised form is the bare drug name.

**Constraint:** dose stripping applies only to Drug-type subjects. Do NOT strip numeric
suffixes from measurement subjects (eGFR 32, LVEF 28% — the number is clinically
meaningful context, not a dose).

### Merge 4 — Rule-layer and LLM-layer emit the same subject

The rule layer fills clinical_subject deterministically from entity text. The LLM layer
emits clinical_subject via instruction. Both layers may produce the same subject for the
same flag. After abbreviation normalisation and dose stripping, they must merge.

**Example:**
- Rule layer: `clinical_subject = "Metformin"` (from DRUG_NAMES lookup)
- LLM layer: `clinical_subject = "metformin 500mg"` → normalised → `"metformin"` → merges

---

## 6. Normalisation Pipeline

Applied to clinical_subject before any comparison:

```
Step 1: lowercase
Step 2: strip leading/trailing whitespace
Step 3: collapse internal whitespace to single space
Step 4: apply abbreviation table (expand abbreviations to canonical full form OR
        map full form to canonical abbreviation — pick one direction and be consistent;
        this spec uses abbreviation as canonical: "ace inhibitor" → "acei")
Step 5: strip dose suffix from drug-type subjects only
        regex: \s+\d+[\d.]*\s*(mg|mcg|g|ml|units?|iu)\b.*$
Step 6: result is the normalised_subject used for comparison
```

Comparison is then exact string match on normalised_subject.

---

## 7. Filling clinical_subject

### Rule layer (deterministic, fills first)

| Flag category | clinical_subject source |
|---------------|------------------------|
| DRUG_INTERACTION | the Drug entity triggering the rule (normalised drug name) |
| ALLERGY_CONFLICT | the Drug entity involved in the conflict |
| TREATMENT_GAP | the Drug or investigation missing (from rule definition) |
| MONITORING_GAP | the measurement or investigation that is overdue |
| CLINICAL_DETERIORATION | the measurement or condition showing deterioration |
| DOSING_CONCERN | the Drug entity with the dosing issue |

Rule-layer subjects are taken from the NER entity's `normalised_value` field (the dose-
stripped, lowercased form already computed by the NER pipeline).

### LLM layer (fills on LLM-produced flags)

The prompt instructs the LLM to emit clinical_subject as a short noun phrase (1–4 words)
naming the specific drug, investigation, or measurement the flag concerns. The LLM must
NOT include the condition context, the severity, or the concern verb.

Good: `"Metformin"`, `"eGFR"`, `"echocardiogram"`, `"ACEi"`
Bad: `"Metformin in CKD3b"`, `"declining eGFR"`, `"overdue echocardiogram"`, `"heart failure medication"`

The prompt instruction is added to all three modes (naive, thoughtful, hybrid). See Step 5
of the flag-identity fix for the exact prompt text.

---

## 8. Matcher Algorithm

```python
def flags_have_same_identity(flag_a: dict, flag_b: dict) -> bool:
    """
    Returns True if flag_a and flag_b represent the same clinical concern.
    Uses (category, normalised_clinical_subject) as the identity pair.
    Severity is NOT part of identity.
    """
    if flag_a.get("category") != flag_b.get("category"):
        return False
    norm_a = normalise_subject(flag_a.get("clinical_subject", ""))
    norm_b = normalise_subject(flag_b.get("clinical_subject", ""))
    if not norm_a or not norm_b:
        return False   # missing subject → cannot merge (conservative)
    return norm_a == norm_b


def normalise_subject(subject: str) -> str:
    """Normalise clinical_subject for comparison. See §6."""
    s = subject.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = ABBREVIATION_TABLE.get(s, s)   # expand or contract via table
    s = re.sub(r"\s+\d+[\d.]*\s*(mg|mcg|g|ml|units?|iu)\b.*$", "", s).strip()
    return s


# Canonical abbreviation table (abbreviation is canonical form)
ABBREVIATION_TABLE = {
    "ace inhibitor": "acei",
    "ace inhibitors": "acei",
    "estimated glomerular filtration rate": "egfr",
    "glycated haemoglobin": "hba1c",
    "glycated hemoglobin": "hba1c",
    "left ventricular ejection fraction": "lvef",
    "b-type natriuretic peptide": "bnp",
    "n-terminal pro-bnp": "nt-probnp",
    # add as needed; conservative — unlisted pairs do NOT merge
}
```

---

## 9. Schema Addition

`clinical_subject` is added to the produced-flag schema as a required string field.

```python
# In agents/flag_agent.py — flag TypedDict or dict shape:
{
    "flag_id":             str,        # uuid
    "patient_id":          str,
    "severity":            str,        # HIGH | MEDIUM | LOW
    "category":            str,        # e.g. DRUG_INTERACTION
    "description":         str,        # human-readable
    "clinical_subject":    str,        # NEW — required, non-empty
    "source_document_id":  str,
    "cited_document_id":   str | None,
    "source_quote":        str | None,
    "status":              str,        # open | resolved
}
```

`clinical_subject` must be non-empty for a flag to be written to CORE. Flags without it
are rejected at the write layer with a logged warning.

---

## 10. Guardrails

1. **v1.3 grounding instrument is untouched.** The addition of clinical_subject is a
   schema extension, not a prompt redesign. The grounding verdicts, severity rubric, and
   validation logic are unchanged.

2. **Coverage guardrail (Step 9).** After all changes, re-run the coverage smoke against
   pat_test_01. Flag counts must not change by more than ±1 (rounding from dedup). If
   coverage drops materially, the normalisation pipeline over-merges and must be tightened.

3. **Must-stay-distinct guardrail.** All four must-stay-distinct cases must pass as
   explicit unit tests before any downstream steps proceed.

---

## 11. Out of scope for v1

- Semantic similarity matching (embeddings, cosine distance) — too loose, violates Case 4
- Cross-category merging — explicitly excluded by identity rule
- Automatic abbreviation discovery — curated table only
- clinical_subject on contradiction rows — contradictions use (doc_a_id, doc_b_id, subject)
  which is a different identity model; out of scope here

---

*End of spec. Commit this file, then proceed to Step 2: build the 8-case test set by hand.*
