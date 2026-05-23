# Clinical Document Intelligence

> Transforming unstructured NHS clinical documents into structured, queryable, and actionable patient intelligence.

---

## The Problem

80% of hospital data is unstructured — trapped in GP letters, discharge summaries, clinic notes, and radiology reports. Clinicians re-order tests already done, miss documented allergies, and lose patients between referrals — not because the information doesn't exist, but because it's buried in language no machine has ever read.

---

## What This System Does

Ingests raw clinical documents → extracts structured medical entities → detects contradictions across documents → flags risks → surfaces a clean, traceable patient record to clinicians — all without making clinical decisions.

```
PDF / DOCX / Scan
       ↓
   OCR + Parse
       ↓
  Medical NER  (scispaCy · ICD-10 · BNF · NegEx)
       ↓
  5-Agent Pipeline  (LangGraph · Claude API)
  ├── A1 Timeline builder
  ├── A2 Contradiction detector  ← most novel
  ├── A3 Risk flag engine
  ├── A4 Pre-appointment briefer
  └── A5 Audit + provenance tracker
       ↓
  Snowflake  (RAW → CORE → MART → FHIR)
       ↓
  FastAPI → Next.js Dashboard
```

---

## Key Features

| Feature | What it does |
|---|---|
| Cross-document contradiction detection | Finds allergy conflicts, dose changes, and inconsistencies across all documents for a patient |
| Risk flags | Surfaces overdue referrals, drug-eGFR interactions, missing screenings |
| Pre-appointment briefing | One-page structured summary generated before a consultation |
| Full audit trail | Every extracted fact links back to source document and exact sentence |
| FHIR R4 output | Structured patient data consumable by any hospital system |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js · TypeScript · Tailwind · shadcn/ui |
| API | FastAPI · Pydantic · Python 3.11 |
| NLP | scispaCy · QuickUMLS · NegEx · ICD-10 UK |
| Agents | LangGraph · Claude API (Sonnet) |
| Data | Snowflake · AWS S3 · Snowpipe |
| Infrastructure | Docker · docker-compose |

---

## Project Structure

```
clinical-document-intelligence/
├── frontend/        # Next.js doctor dashboard
├── api/             # FastAPI REST layer
├── parsers/         # PDF · DOCX · OCR extraction
├── nlp/             # Medical NER pipeline
├── agents/          # LangGraph multi-agent system
├── worker/          # Background document processor
├── fhir/            # FHIR R4 conversion
├── database/        # Snowflake schemas · views · procedures
├── ingestion/       # S3 + Snowpipe config
├── config/          # Settings + logging
└── tests/           # Unit · integration · benchmarks
```

---

## Benchmark Results

> MIMIC-III access pending — results will be published here and in the blog series.

| Entity type | F1 score |
|---|---|
| DATE | pending |
| DRUG | pending |
| DIAGNOSIS | pending |
| NEGATION | pending |

---

## Regulatory Positioning

This system is a **clinical document structuring and administrative intelligence platform**. It does not provide diagnoses, treatment recommendations, or clinical decisions. All outputs are presented to a qualified clinician for review.

This positions the system on the administrative side of the UK Medical Device Regulation bright line — no UKCA marking required.

---

## Data & Privacy

- Development uses **Synthea synthetic patients** and **MIMIC-III de-identified notes** only
- No real patient data is processed without a signed Data Processing Agreement and ethics approval
- All processing in **AWS eu-west-2 (London)** — NHS data residency compliant
- GDPR right-to-erasure implemented via `database/procedures/delete_patient.sql`

---

## Quick Start

```bash
cp .env.example .env
# fill in SNOWFLAKE_*, ANTHROPIC_API_KEY, AWS_*

docker-compose up
```

API: `http://localhost:8000`
Dashboard: `http://localhost:3000`
API docs: `http://localhost:8000/docs`

---

## Doctor-Facing Endpoints

```
GET  /api/v1/patients/{id}/timeline        # Full chronological history
GET  /api/v1/patients/{id}/flags           # Active risk flags
GET  /api/v1/patients/{id}/contradictions  # Cross-document conflicts
GET  /api/v1/patients/{id}/briefing        # Pre-appointment summary
POST /api/v1/documents                     # Upload a document
GET  /fhir/R4/Patient/{id}                 # FHIR R4 bundle
```

---

## Blog Series — Building in the Open

12 posts documenting every stage of this build.

| # | Title | Status |
|---|---|---|
| 01 | Why 80% of hospital data has never been read by a computer | coming |
| 02 | I spent a week reading clinical letters. Here's what I found. | coming |
| 03 | How I built an OCR pipeline that handles handwritten GP notes | coming |
| 04 | Teaching a model to read like a doctor: medical NER from scratch | coming |
| 05 | The hardest problem: detecting contradictions across clinical documents | coming |
| 06 | I showed my system to a doctor for the first time | coming |
| 07 | Measuring what matters: benchmarking a clinical AI tool | coming |
| 08 | Navigating healthcare AI regulation as a solo builder | coming |
| 09 | What building this taught me about the NHS | coming |
| 10 | 6 months of building in public: what I got wrong | coming |
| 11 | The open-source clinical NLP toolkit I'm releasing | coming |
| 12 | What happens when every hospital document can be read by a machine | coming |

---

## Team

Built by two members as part of a Global Talent Visa (Tech Nation) portfolio project.

- **ML / Backend** — Python · NLP · LangGraph · FastAPI · LLM systems
- **Data Engineering** — Snowflake · SQL · S3 · data modelling

---

## Status

🔨 Active development — started May 2025  
📋 MIMIC-III access: pending  
🏥 Clinical pilot: targeting July 2025  
📝 GTV application: targeting December 2025

---

## Disclaimer

All outputs are for administrative use only and must be reviewed by a qualified clinician. This system does not provide clinical advice, diagnoses, or treatment recommendations.
