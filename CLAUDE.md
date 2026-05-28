# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository State

This repo is a **scaffolded project, not a working one**. Directory tree and contract docs are in place, but almost every source file in `agents/`, `api/`, `nlp/`, `parsers/`, `ingestion/`, `worker/`, `fhir/`, `database/`, `frontend/`, and `tests/` is **empty (0 lines)**. The substantive files today are `requirements.txt`, `verify_env.py`, `check_setup.py`, `CONTRACT.md`, `WORK_DIVISION.md`, `COLUMN_MAPPING.md`, `README.md`, and the Windows setup scripts.

Implication: when asked to "look at" or "change" code, first check whether the file exists with content. Most tasks here will be **implementing into empty scaffolds** against the contracts below, not modifying existing logic.

## Authoritative documents (read before changing anything)

- **`CONTRACT.md`** — single source of truth for Snowflake schemas, the worker→DB JSON output format, and every API endpoint signature. Any change to a schema, the JSON contract, or an API shape requires updating CONTRACT.md in the same PR. Two teammates depend on it; don't drift unilaterally.
- **`COLUMN_MAPPING.md`** — exact mapping from NHS synthetic CSV columns to the `patient` / `entity` / `flag` / `contradiction` / `document` tables. Use this verbatim when writing seed-load SQL.
- **`WORK_DIVISION.md`** — who owns what (Member A = Data Engineer / Snowflake / S3; Member B = ML Engineer / NLP / API / Frontend) and the week-by-week plan.

## Common commands

Setup is Windows-first (PowerShell / `cmd`). The host shell here is PowerShell.

```powershell
# One-time environment setup (creates venv, installs deps, downloads scispaCy model)
.\setup-env.ps1          # PowerShell
setup.bat                # cmd equivalent if PowerShell errors

# Activate venv (every session)
.\venv\Scripts\Activate.ps1

# Verify environment (Python version, deps, scispaCy model, Tesseract, sample PDFs)
python verify_env.py

# Quick file-presence check
python check_setup.py
```

`requirements.txt` does **not** include the scispaCy model. Install it separately:
```
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
```

Tesseract is an **OS-level** dependency (not pip). Windows installer: https://github.com/UB-Mannheim/tesseract/wiki — default install path `C:\Program Files\Tesseract-OCR`.

There is no working `docker-compose up`, no test runner config, and no FastAPI entrypoint yet — those files exist but are empty. The README and SETUP docs describe the *target* setup, not the current state.

## Architecture (target)

End-to-end flow:

```
upload → parsers/ → nlp/ → agents/ (5-agent LangGraph) → database/ (Snowflake) → api/ → frontend/
                                                              ↑
                                                  worker/ orchestrates the pipeline
```

Two parallel pipelines that both members work on concurrently:

1. **ML / extraction path** (Member B): `parsers/` extracts text from PDFs/scans (PyMuPDF + Tesseract). `nlp/` runs scispaCy NER, NegEx negation detection, ICD-10 and BNF code mapping, date normalisation. `agents/` runs five LangGraph agents over the extracted entities (timeline builder, contradiction detector, risk flag engine, pre-appointment briefer, audit/provenance). `worker/` drives the pipeline end-to-end per document.
2. **Data path** (Member A): `ingestion/` (S3 + Snowpipe) auto-loads `raw_documents`. `database/schemas/` defines `raw → core → mart → fhir` layers. `database/views/` exposes flattened reads for the frontend. `database/procedures/` provides bulk-insert procs that the worker calls (`write_entities`, `write_flags`, `write_contradictions`) and a GDPR `delete_patient` cascade.

Two key boundary contracts:

- **Worker → DB JSON** (CONTRACT.md §2) — what the worker writes. Required fields: `doc_id`, `patient_id`, `entities[]` (with `entity_type` ∈ {diagnosis, medication, observation, allergy, referral}, `negated`, `confidence`), `flags[]`, `contradictions_detected[]`, `errors[]`. ICD-10 codes required for diagnoses, BNF codes for medications.
- **API ↔ Frontend** (CONTRACT.md §3) — base URL `http://localhost:8000/api/v1`, `X-API-Key` header required on all routes except `/health`. Endpoint shapes are pinned per-screen (1–7). Don't change response shapes without updating CONTRACT.md.

Naming inconsistency to be aware of: `parsers/` and `ingestion/` both currently contain `file_router.py`, `pdf_parser.py`, `ocr_engine.py` (all empty). WORK_DIVISION.md and the README suggest `parsers/` is the ML-side extraction layer; `ingestion/` is the data-side S3/Snowpipe layer (with `lab_parser.py`, `s3_uploader.py`, `*.sql`). Treat them that way unless the user says otherwise — don't auto-consolidate.

## Mock-first rule (from CONTRACT.md §7)

To avoid one member blocking the other:
- **Worker without Snowflake**: write JSON to `worker/output/{doc_id}.json` instead of calling Snowflake. The format must match the CONTRACT.md §2 JSON exactly so the writer can swap in later.
- **DB views without real NLP output**: load the NHS synthetic CSVs directly into `entity` per COLUMN_MAPPING.md (hardcode `negated=FALSE`, `confidence=1.0`, `doc_id=NULL` for seed rows).

When implementing a stub, mirror the real contract — don't shortcut the JSON shape.

## Coding standards (CONTRACT.md §6)

- Python: `black` (line length 100), `ruff`, type hints on public functions, Google-style docstrings.
- SQL: **lowercase keywords** (`select`, not `SELECT`), 4-space indent, one column per line in `SELECT`, always name columns in `INSERT`.
- Commits: `<type>(<scope>): <subject>` — e.g. `feat(api): add patient timeline endpoint`.

## Regulatory positioning (don't violate)

The system is positioned as **administrative document structuring**, not clinical decision support — that's what keeps it on the non-medical-device side of UK MDR. When writing agent prompts, API descriptions, or UI copy, do not phrase outputs as diagnoses, treatment recommendations, or clinical advice. Outputs surface information for a clinician to review.

## Data

- Dev data only: Synthea synthetic patients and (when access lands) MIMIC-III de-identified notes.
- 17 sample PDFs ship at `data/synthetic/nhs_data/pdfs/` (GP referrals, cardiology letters, DM review) — these are the canonical fixtures for parser/NER work.
- Expected seed counts after CSV load: `patient`=50, `entity`≈840, `document`=180, `flag`=53, `contradiction`=15 (per COLUMN_MAPPING.md).
