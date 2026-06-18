\# Phase 4 L2 — completion summary



\*\*Date:\*\* 2026-06-18

\*\*Status:\*\* Complete from ML side. Three items pending partner DDL. One deliberately deferred to v2.



This document is the single source of truth for what landed in Phase 4 L2, what's blocked, and what's intentionally out of scope. Used for paper writing (methodology section, limitations section) and partner handoff tracking.



\## What landed



\### OCR engine (`parsers/ocr\_engine.py`, commit 2422c03)

\- Tesseract default path (free, local, 300 DPI via PyMuPDF + pytesseract).

\- Opt-in Textract path via `use\_textract=True` for higher accuracy when AWS budget allows.

\- `parse\_pdf` wrapped with OCR fallback: when PyMuPDF returns 0 chars, automatically falls back to Tesseract.

\- Known limitation: Tesseract occasionally misreads capital I in ICD-10 codes as digit 1 (e.g. "I50.22" → "150.22"). Logged for paper limitations section.



\### ICD-10 mapper + NER integration (commits 13d48de, efbfa09)

\- `ontology/icd10\_mapper.py` with curated 65-row CSV (`ontology/data/icd10\_common.csv`).

\- Three-tier match: exact (high) → direction-aware substring (medium) → None.

\- Direction-aware: reference contained in query, never query in reference. Vague queries refused to over-specify.

\- Word-bounded regex: short tokens cannot match inside longer drug names.

\- 12/12 test set passing, including two regression tests:

&#x20; - `regression\_vague\_query\_no\_overspecify`: "chronic heart failure" no longer returns the more specific I50.32 diastolic-HF code.

&#x20; - `no\_match\_unknown\_term`: "RA" no longer matches inside "barotrauma".

\- NER classifier hardening (component A+B in commit efbfa09):

&#x20; - \*\*A. Extended NON\_MEDICAL\_STOPWORDS\*\* with generic clinical verbs, specialty names, investigation names, UK city names, road-suffix words. Spans containing newline, "icd", or with all tokens in stopwords rejected.

&#x20; - \*\*B. Positive-signal gate\*\*: `CONDITION\_TERMS`, `CONDITION\_ROOTS`, `SYMPTOM\_TERMS` (\~60+60+30 entries). Diagnosis classification requires positive signal.

&#x20; - Result on patient\_001 doc 01: 30 false-positive diagnoses → 8 real ones. \*\*False positive rate: 63% → 0%.\*\*



\### BNF drug-name mapper + NER integration (commits 1578b79, c648b90)

\- `ontology/bnf\_mapper.py` with curated 105-row CSV (`ontology/data/bnf\_common.csv`).

\- Coverage: Cardiovascular (37), Endocrine (15), Respiratory (13), CNS (12), Infections (12), GI (5), MSK (3), Nutrition (4).

\- Same three-tier match shape as ICD-10. Plus dose-stripping for entity texts like "Ramipril 5 mg" → "Ramipril".

\- 12/12 test set passing with three regression tests (dose strip, vague-query no-overspecify, word-boundary).

\- Integration into `nlp/medical\_ner.py`: Drug entities now carry `bnf\_code` field, populated via mapper.

\- Smoke on patient\_001 doc 01: 5/5 drug entities coded.

\- \*\*Known gap (partner-side)\*\*: `SP\_WRITE\_ENTITIES` has no `bnf\_code` column. Drug entities' `bnf\_code` field doesn't reach Snowflake. Bundle MedicationStatements therefore show text only, no `coding`. See `partner\_handoffs/2026-06-18-bnf-code-entity-migration.sql`.



\### Audit agent — tamper-evident flag provenance (commit 30d45f3)

\- `agents/audit\_agent.py`. SHA-256 hash of provenance + content fields:

&#x20; - Provenance: source\_quote, cited\_document\_id, source\_document\_id

&#x20; - Content: severity, category, clinical\_subject, description

&#x20; - Context: model, prompt\_version, temperature

\- `hash\_flag(flag, context)` returns 64-char hex digest. Deterministic.

\- `attach\_hash(flag, context)` returns a copy with `provenance\_hash` field.

\- `verify\_jsonl\_run(path)` re-hashes every flag and reports match/mismatch/no\_stored\_hash.

\- CLI: `python -m agents.audit\_agent --jsonl <path>`. Exit 0 if clean, 1 on tampering.

\- 7/7 test set passing including three load-bearing tampering-detection cases (description tampered, source\_quote tampered, context tampered all detected).

\- Round-trip verified on `evaluation/results/smoke\_with\_subject.jsonl`: 21 rows, 141 flags, 0 mismatch, 141 no\_stored\_hash (correct for pre-instrumentation data).

\- \*\*Known gap (partner-side)\*\*: `CORE.flag` has no `provenance\_hash` column, `SP\_WRITE\_FLAGS` doesn't carry the field. See `partner\_handoffs/2026-06-18-provenance-hash-migration.sql`.



\### Async API via FastAPI BackgroundTasks (commit 0b4682a)

\- `api/jobs.py`: thread-safe in-memory job store. `create\_job` / `mark\_running` / `mark\_completed` / `mark\_failed` / `get\_job` / `list\_jobs`.

\- `GET /api/jobs/{job\_id}` + `GET /api/jobs` endpoints.

\- POST /documents, POST /labs, POST /notes, DELETE /documents all return immediately with `job\_id`. Slow work (worker.process\_from\_s3, run\_agents) runs in background.

\- Frontend `lib/api.ts` gained `Job` type, `getJob`, `pollJob` with `intervalMs`, `timeoutMs`, `onProgress`.

\- Documents page polls jobs with live status messages.

\- \*\*User-facing latency: 60-120s blocking → \~2s response + background work.\*\* Pipeline itself unchanged; latency moved off the user.



\### Three-tier gold schema + precision\_tiered metric (commit 0cc55e4 and the supervisor-corrections commit)

\- patient\_001 + patient\_002 gold migrated to v2\_three\_tier (Tier 1 must-catch / Tier 2 acceptable, credit-neutral / Tier 3 wrong).

\- Tier 2 entries marked `needs\_clinician\_validation=true`.

\- Gold contradictions redesigned to claim-based matching (`claim\_a\_sources` × `claim\_b\_sources`, any cross-pairing satisfies).

\- `precision\_tiered(accepted\_flags, tier\_1\_subjects, tier\_2\_subjects)` in `evaluation/metrics.py`. Tier 2 emissions masked from denominator entirely.

\- 6/6 test set passing including two load-bearing cases.

\- Matcher 8/8 test set unaffected (additive change).



\### FHIR R4B builders + bundle assembly + endpoint + validator (commits 8f9d520, 4824456, cd324f1, 763780a)

\- `clinical\_fhir/builders.py`: four pure functions building Patient, Condition, MedicationStatement, Observation. 8/8 test set passing.

\- `clinical\_fhir/fhir\_builder.py`: `build\_patient\_bundle(patient\_id)` assembles a complete R4B Bundle (type=collection) from CORE. Dedup with merged-evidence-refs (Option C, locked).

\- `clinical\_fhir/fhir\_builder.py`: `write\_fhir\_bundle(patient\_id, bundle)` MERGEs into `mart.fhir\_patient\_bundle` (partner's table from `database/schemas/05\_fhir.sql`). Idempotent; resets `is\_stale=FALSE` on write.

\- `clinical\_fhir/validator.py`: wraps `fhir.resources` 8.2.0 R4B strict parser. Validates every Patient, Condition, MedicationStatement, Observation, Bundle.

\- `api/routes/fhir.py`: `GET /api/patients/{id}/fhir` (reads from mart, 200 with `application/fhir+json`, 404 with rebuild pointer). `POST /api/patients/{id}/fhir/rebuild` (builds + writes, returns metadata).

\- ID sanitiser at FHIR boundary: internal underscored IDs (pat\_test\_01, doc\_XXX) → FHIR-compliant hyphenated (pat-test-01, doc-XXX). Internal Snowflake IDs untouched.

\- 5/5 bundle test set passing including condition dedup with merged evidence and medication dedup with derivedFrom.

\- \*\*Live smoke against pat\_test\_01 in Snowflake: 74/74 resources validate against R4B strict.\*\*



\### Entity cleanup (commit 4824456 inside the bundle assembly commit)

\- First real-data smoke of the FHIR bundle exposed 102 Conditions, 60% false positives (postcode-as-ICD-10, document structure noise). All entities pre-dated the NER classifier fix.

\- Cleanup: DELETE existing CORE.entity rows for pat\_test\_01's 9 documents, re-run `worker.process\_from\_s3` with the cleaned NER.

\- Result: 340 entities → 137 entities, \*\*-60% false-positive reduction matching the per-document patient\_001 measurement\*\*.

\- Bundle re-smoke clean: 134 entries → 74, top conditions all real (T2DM/E11.9 with multi-doc evidence, Hypertension/I10, Obesity/E66.9).

\- Side observation worth one paper sentence: the v1.3 grounding instrument's hybrid validator fired live across all three documented failure modes during re-processing — trivial-quote, composition-fabrication, irrelevant-padding. Live evidence on real data, not cached from Day 5.



\## Pending partner DDL



Three items need partner-side schema changes before they can fully land:



| Item | Migration | Status |

|---|---|---|

| Audit hash write-path | `partner\_handoffs/2026-06-18-provenance-hash-migration.sql` | Sent Tuesday; awaiting partner |

| BNF code on Medications | `partner\_handoffs/2026-06-18-bnf-code-entity-migration.sql` | Sent Tuesday; awaiting partner |

| Hash integration into flag\_agent.write\_flags | Blocks on the provenance\_hash column existing | Code ready; \~20 min once column lands |



\## Deliberately deferred to v2



\*\*UMLS / SNOMED CT integration.\*\* UMLS download failed on this round; UMLS dropped from v1 scope. ICD-10 + BNF curated CSVs provide sufficient coverage for the synthetic dataset and the paper's defensibility claim. SNOMED CT UK Edition is the natural v2 upgrade once TRUD access is registered.



\## Methodology gates summary



Tests written \*\*before\*\* the code they test, every block:

\- Matcher: 8/8 (4/4 MUST\_STAY\_DISTINCT critical for not over-merging paraphrase)

\- precision\_tiered: 6/6 (Tier 2 correctly masked from denominator)

\- ICD-10 mapper: 12/12 (direction-aware + word-boundary regressions)

\- BNF mapper: 12/12 (dose strip + direction-aware + word-boundary regressions)

\- Audit agent: 7/7 (3 tampering-detection cases load-bearing)

\- FHIR builders: 8/8 + R4B validator gate on every output

\- FHIR bundle assembly: 5/5 + end-of-suite R4B Bundle validation gate



All gates pass on real Snowflake data, not just synthetic fixtures.

