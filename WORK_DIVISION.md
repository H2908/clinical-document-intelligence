# Work Division — Clinical Document Intelligence

**Project duration:** 4 weeks
**Team:** 2 members
**Member A:** Data Engineer (DE)
**Member B:** ML Engineer (ML)

---

## 🎯 High-level ownership

| Area | Owner | Why |
|------|-------|-----|
| Snowflake setup, schemas, views | **A (DE)** | SQL + database expertise |
| S3 bucket, Snowpipe, ingestion | **A (DE)** | Cloud infra |
| Data loading, ETL | **A (DE)** | Data pipelines |
| Stored procedures, query optimization | **A (DE)** | Performance |
| PDF parsing, OCR | **B (ML)** | Python + ML libs |
| NLP (NER, ICD-10, BNF mapping) | **B (ML)** | spaCy, scispaCy |
| LLM agents (LangGraph) | **B (ML)** | Claude API, prompting |
| FastAPI backend | **B (ML)** | Python web frameworks |
| Frontend (Next.js) | **B (ML)** or shared | React/TS |
| Worker / background jobs | **B (ML)** | Async Python |
| Testing | **Shared** | Both write tests for their code |
| Docker, deployment | **Shared** | Together |

---

## 📅 WEEK 1: Foundation

### Member A (DE) — Snowflake + S3 setup

#### Day 1 (Monday)
**Goal:** Snowflake account ready, schemas created

**Tasks:**
- [ ] Signup Snowflake free trial: https://signup.snowflake.com
  - Region: AWS eu-west-2 (London)
  - Edition: Standard
- [ ] Create AWS account (if not exists)
- [ ] Create IAM user with S3 permissions
- [ ] Create S3 bucket: `clinical-di-raw-{your-initials}`
- [ ] Install `snowsql` CLI on local machine
- [ ] Create `.env` file with Snowflake + AWS credentials
- [ ] Run `database/snowflake_connection.sql` (warehouse, database, role)

**Deliverable:** 
- ✅ Snowflake account active
- ✅ `SELECT CURRENT_VERSION()` works
- ✅ S3 bucket exists and accessible

**Files created:**
```
database/snowflake_connection.sql
.env
```

---

#### Day 2 (Tuesday)
**Goal:** All core tables created and tested

**Tasks:**
- [ ] Write `database/schemas/01_raw.sql` (raw_documents table)
- [ ] Write `database/schemas/03_core.sql` (patient, document, entity, flag, contradiction, summary)
- [ ] Run all schemas in Snowflake
- [ ] Verify: `SHOW TABLES IN SCHEMA CORE`
- [ ] Insert 1 test row in each table manually
- [ ] Document any issues in GitHub Issues

**Deliverable:**
- ✅ All 7 tables created
- ✅ Manual INSERT works for each
- ✅ Foreign keys verified

**Files created:**
```
database/schemas/01_raw.sql
database/schemas/03_core.sql
```

---

#### Day 3 (Wednesday)
**Goal:** Load NHS synthetic data into Snowflake

**Tasks:**
- [ ] Download NHS dataset ZIP (from earlier delivery)
- [ ] Extract to `data/synthetic/nhs_data/`
- [ ] Create internal stage: `CREATE STAGE nhs_data_stage`
- [ ] Upload CSVs: `PUT file://data/synthetic/nhs_data/*.csv @nhs_data_stage`
- [ ] Follow `COLUMN_MAPPING.md` to run INSERT statements
- [ ] Verify counts:
  ```sql
  SELECT 'patient' AS t, COUNT(*) FROM patient
  UNION ALL SELECT 'entity', COUNT(*) FROM entity
  UNION ALL SELECT 'flag', COUNT(*) FROM flag;
  ```
  Expected: patient=50, entity=~840, flag=53

**Deliverable:**
- ✅ All 50 patients in Snowflake
- ✅ ~840 entities loaded
- ✅ Sample query works: `SELECT * FROM patient WHERE patient_id='p001'`

**Files created:**
```
database/load_seed_data.sql
```

---

#### Day 4 (Thursday)
**Goal:** Build all 7 views (for frontend)

**Tasks:**
- [ ] Write `database/views/v_patient_list.sql`
- [ ] Write `database/views/v_patient_overview.sql`
- [ ] Write `database/views/v_timeline.sql`
- [ ] Write `database/views/v_active_flags.sql`
- [ ] Write `database/views/v_active_conditions.sql`
- [ ] Write `database/views/v_current_medications.sql`
- [ ] Write `database/views/v_contradictions.sql`
- [ ] Test each view: `SELECT * FROM v_patient_list LIMIT 5`

**Deliverable:**
- ✅ All views return data
- ✅ `SELECT * FROM v_patient_list` shows 50 patients with counts

**Files created:**
```
database/views/*.sql (7 files)
```

---

#### Day 5 (Friday)
**Goal:** S3 + Snowpipe auto-ingest setup

**Tasks:**
- [ ] Write `ingestion/s3_external_stage.sql` (external stage to S3)
- [ ] Write `ingestion/snowpipe_setup.sql` (auto-ingest pipe)
- [ ] Configure S3 event notification → SQS → Snowpipe
- [ ] Test: upload a test file to S3 → should appear in `raw_documents` within 1 min
- [ ] Document SQS ARN and access keys in `.env.example`

**Deliverable:**
- ✅ File uploaded to S3 → automatically appears in `raw_documents` table
- ✅ Demo this to Member B

**Files created:**
```
ingestion/s3_external_stage.sql
ingestion/snowpipe_setup.sql
ingestion/s3_uploader.py  (Python helper for Member B to use)
```

---

### Member B (ML) — Data prep + Parsers + NLP

#### Day 1 (Monday)
**Goal:** Environment setup, sample PDFs ready

**Tasks:**
- [ ] Install Python 3.10+, create venv
- [ ] Install dependencies:
  ```bash
  pip install fastapi uvicorn pymupdf pytesseract pillow
  pip install scispacy spacy anthropic langgraph
  pip install pandas pydantic python-multipart boto3
  pip install snowflake-connector-python
  ```
- [ ] Install Tesseract OS-level:
  - Mac: `brew install tesseract`
  - Linux: `apt-get install tesseract-ocr`
  - Windows: download installer
- [ ] Download scispaCy model:
  ```bash
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz
  ```
- [ ] Extract NHS dataset ZIP
- [ ] Confirm: 17 sample PDFs are readable

**Deliverable:**
- ✅ All packages installed
- ✅ `python -c "import scispacy; print('ok')"` works
- ✅ Can open sample PDF in Python

**Files created:**
```
requirements.txt
.env (filled in)
```

---

#### Day 2 (Tuesday)
**Goal:** PDF parser working

**Tasks:**
- [ ] Write `parsers/file_router.py`:
  - Detect file type from extension/magic bytes
  - Route to correct parser
- [ ] Write `parsers/pdf_parser.py`:
  - Use PyMuPDF (fitz) to extract text
  - Return text + page metadata
  - Handle multi-page PDFs
- [ ] Write `parsers/ocr_engine.py`:
  - Tesseract for scanned PDFs
  - Image preprocessing (OpenCV optional)
- [ ] Test on all 17 sample PDFs
- [ ] Output: text strings ready for NLP

**Deliverable:**
- ✅ `python parsers/pdf_parser.py path/to/sample.pdf` extracts text
- ✅ Output: `{"text": "...", "pages": 2, "method": "pymupdf"}`

**Files created:**
```
parsers/__init__.py
parsers/file_router.py
parsers/pdf_parser.py
parsers/ocr_engine.py
parsers/text_cleaner.py
```

---

#### Day 3 (Wednesday)
**Goal:** NLP NER pipeline

**Tasks:**
- [ ] Write `nlp/medical_ner.py`:
  - Use scispaCy `en_core_sci_md`
  - Extract: diseases, drugs, observations, dates
  - Return entities with offsets
- [ ] Write `nlp/negation_detector.py`:
  - Use medspaCy NegEx
  - Mark "no allergy" as negated=True
- [ ] Write `nlp/date_normaliser.py`:
  - Convert "28 Feb 2024", "28/02/2024", "Feb 28, 2024" → "2024-02-28"
- [ ] Test on extracted PDF text

**Deliverable:**
- ✅ Input: text → Output: entities list (CONTRACT.md format)
- ✅ "Patient has no diabetes" → diabetes entity with negated=True

**Files created:**
```
nlp/__init__.py
nlp/medical_ner.py
nlp/negation_detector.py
nlp/date_normaliser.py
```

---

#### Day 4 (Thursday)
**Goal:** Code mapping (ICD-10 + BNF)

**Tasks:**
- [ ] Download ICD-10 UK codes CSV → `data/ontologies/icd10_uk.csv`
- [ ] Download BNF codes CSV → `data/ontologies/bnf_codes.csv`
- [ ] Write `nlp/icd10_mapper.py`:
  - Input: "Type 2 diabetes" → Output: "E11.9"
  - Use fuzzy matching (rapidfuzz library)
- [ ] Write `nlp/bnf_mapper.py`:
  - Input: "Metformin 500mg" → Output: "06.01.02.02"
- [ ] Test: 80%+ accuracy on sample conditions

**Deliverable:**
- ✅ Mapper achieves reasonable accuracy
- ✅ Falls back to None if no match found

**Files created:**
```
nlp/icd10_mapper.py
nlp/bnf_mapper.py
data/ontologies/icd10_uk.csv
data/ontologies/bnf_codes.csv
```

---

#### Day 5 (Friday)
**Goal:** End-to-end: PDF → JSON

**Tasks:**
- [ ] Write `worker/document_processor.py`:
  - Input: PDF path
  - Pipeline: parser → NLP → code mapping → negation
  - Output: JSON matching CONTRACT.md Section 2
- [ ] Test on 5 sample PDFs
- [ ] Save outputs to `worker/output/{doc_id}.json`
- [ ] **Demo to Member A:** Show 1 PDF → JSON working

**Deliverable:**
- ✅ `python worker/document_processor.py sample.pdf` produces valid JSON
- ✅ JSON has entities, flags, summary
- ✅ Format exactly matches CONTRACT.md

**Files created:**
```
worker/__init__.py
worker/document_processor.py
worker/output/*.json (samples)
```

---

### Week 1 Integration (Friday afternoon)

**Both members together (2 hours):**

- [ ] Member A: Show all tables populated + views working
- [ ] Member B: Show PDF → JSON pipeline
- [ ] Member B: Write JSON to Snowflake using Member A's tables
- [ ] **End-to-end demo:** Upload PDF → extract → save to Snowflake → query view

**Week 1 success criteria:**
- ✅ Snowflake has 50 patients + 840 entities + views
- ✅ Member B can convert PDF → valid JSON
- ✅ JSON can be inserted into Member A's tables

---

## 📅 WEEK 2: API + Agents

### Member A (DE) — Procedures + Optimization

#### Day 6 (Monday)
**Goal:** Stored procedures for Python to call

**Tasks:**
- [ ] Write `database/procedures/write_entities.sql`:
  - Input: JSON from worker
  - Parses entities array
  - Bulk inserts into `entity` table
- [ ] Write `database/procedures/write_flags.sql`
- [ ] Write `database/procedures/write_contradictions.sql`
- [ ] Test by calling: `CALL write_entities(?, ?)`

**Deliverable:**
- ✅ Member B can call procedures from Python
- ✅ One call handles 100+ entities

**Files created:**
```
database/procedures/write_entities.sql
database/procedures/write_flags.sql
database/procedures/write_contradictions.sql
```

---

#### Day 7 (Tuesday)
**Goal:** Python connector + GDPR cascade

**Tasks:**
- [ ] Write `database/snowflake_writer.py`:
  - Connection pool
  - Helper functions: `insert_entities(doc_id, entities)`
  - Used by Member B's worker
- [ ] Write `database/procedures/delete_patient.sql` (GDPR cascade delete)
- [ ] Test GDPR: deleting patient cascades to all related tables

**Deliverable:**
- ✅ Member B uses `from database.snowflake_writer import insert_entities`
- ✅ GDPR delete works

**Files created:**
```
database/snowflake_writer.py
database/procedures/delete_patient.sql
```

---

#### Day 8 (Wednesday)
**Goal:** Query optimization + indexes

**Tasks:**
- [ ] Add clustering keys on high-traffic tables:
  ```sql
  ALTER TABLE entity CLUSTER BY (patient_id);
  ALTER TABLE flag CLUSTER BY (patient_id, status);
  ```
- [ ] Run EXPLAIN on slow views
- [ ] Optimize view queries (avoid SELECT *)
- [ ] Add result caching for common queries

**Deliverable:**
- ✅ All view queries < 500ms
- ✅ Performance baseline documented

**Files created:**
```
database/optimization.sql
docs/performance_baseline.md
```

---

#### Day 9 (Thursday)
**Goal:** FHIR layer + audit

**Tasks:**
- [ ] Write `database/schemas/05_fhir.sql`:
  - Tables with VARIANT columns for FHIR JSON
- [ ] Create FHIR conversion view:
  - `v_fhir_patient`, `v_fhir_observation`
- [ ] Add audit log table for compliance

**Deliverable:**
- ✅ `SELECT * FROM v_fhir_patient` returns valid FHIR JSON

**Files created:**
```
database/schemas/05_fhir.sql
database/views/v_fhir_patient.sql
database/audit_log.sql
```

---

#### Day 10 (Friday)
**Goal:** Help Member B with API queries

**Tasks:**
- [ ] Review Member B's SQL in API endpoints
- [ ] Optimize problematic queries
- [ ] Document query patterns in `database/QUERY_GUIDE.md`
- [ ] Support testing

**Deliverable:**
- ✅ All API endpoints have < 200ms response time
- ✅ Member B confident with Snowflake

---

### Member B (ML) — Worker + LLM agents + API

#### Day 6 (Monday)
**Goal:** Worker queue system

**Tasks:**
- [ ] Write `worker/main.py`:
  - Entry point for background processing
  - Polls for new documents
- [ ] Write `worker/queue_handler.py`:
  - Option A: Simple Python BackgroundTasks
  - Option B: Redis Queue (RQ)
- [ ] Wire up to Member A's `snowflake_writer`
- [ ] **End-to-end test:** PDF in `/uploads` → entities in Snowflake

**Deliverable:**
- ✅ Drop PDF → automatic processing → Snowflake populated

**Files created:**
```
worker/main.py
worker/queue_handler.py
```

---

#### Day 7-8 (Tuesday-Wednesday)
**Goal:** LLM agents (3 of 5)

**Tasks:**
- [ ] Write `agents/prompts.py`:
  - All Claude prompts in one place
  - Use system + user message format
- [ ] Write `agents/timeline_agent.py`:
  - Input: patient_id
  - Output: chronological events (already in DB via entities)
  - Simple: just queries the data
- [ ] Write `agents/contradiction_agent.py`:
  - Compare entities across patient's documents
  - Detect: same fact, different values
  - Use Claude to generate `ai_recommendation`
- [ ] Write `agents/risk_flag_agent.py`:
  - Rules-based + LLM hybrid
  - Examples: overdue referrals, drug-eGFR safety

**Deliverable:**
- ✅ 3 agents working
- ✅ Each outputs JSON matching CONTRACT.md flags/contradictions format

**Files created:**
```
agents/__init__.py
agents/prompts.py
agents/timeline_agent.py
agents/contradiction_agent.py
agents/risk_flag_agent.py
```

---

#### Day 9 (Thursday)
**Goal:** Remaining 2 agents + orchestrator

**Tasks:**
- [ ] Write `agents/briefing_agent.py`:
  - Input: patient data
  - Output: pre-appointment summary (LLM)
- [ ] Write `agents/audit_agent.py`:
  - Provenance tracking
  - Which doc → which entity
- [ ] Write `agents/orchestrator.py`:
  - LangGraph state machine
  - Runs all 5 agents in order
  - Handles failures gracefully

**Deliverable:**
- ✅ All 5 agents working
- ✅ Orchestrator runs end-to-end for 1 patient

**Files created:**
```
agents/briefing_agent.py
agents/audit_agent.py
agents/orchestrator.py
```

---

#### Day 10 (Friday)
**Goal:** FastAPI endpoints

**Tasks:**
- [ ] Write `api/main.py` (FastAPI app, CORS, routers)
- [ ] Write `api/auth.py` (API key middleware)
- [ ] Write `api/schemas.py` (Pydantic models from CONTRACT.md)
- [ ] Write `api/db.py` (Snowflake connection)
- [ ] Write 5 endpoint files:
  - [ ] `routes/patients.py` (list, overview, timeline)
  - [ ] `routes/documents.py` (upload, get, list)
  - [ ] `routes/flags.py` (list, resolve)
  - [ ] `routes/briefing.py` (get briefing)
  - [ ] `routes/fhir.py` (FHIR R4 patient)
- [ ] Test with Postman/curl

**Deliverable:**
- ✅ All endpoints from CONTRACT.md work
- ✅ `curl http://localhost:8000/api/v1/patients/p001` returns valid JSON

**Files created:**
```
api/main.py
api/auth.py
api/schemas.py
api/db.py
api/routes/*.py (5 files)
```

---

### Week 2 Integration

**Both together:**
- [ ] End-to-end demo: upload PDF → all 5 agents run → API returns enriched data
- [ ] Document any bugs in GitHub Issues
- [ ] Plan Week 3 frontend work

---

## 📅 WEEK 3: Frontend

### Member B (ML) — Primary frontend
### Member A (DE) — Support + optimization

#### Day 11 (Monday)
**Goal:** Next.js setup + patient list

**Tasks (Member B):**
- [ ] Setup Next.js project: `npx create-next-app@latest frontend`
- [ ] Install: tailwindcss, lucide-react, axios
- [ ] Write `lib/api.ts` (API client)
- [ ] Write `app/page.tsx` (patient list — Screen 1)
- [ ] Write `components/PatientCard.tsx`
- [ ] Connect to API: `GET /patients`

**Tasks (Member A):**
- [ ] Monitor Snowflake usage (credits)
- [ ] Tune slow queries based on frontend load
- [ ] Help with SQL questions

**Deliverable:**
- ✅ Browser shows 50 patient cards
- ✅ Search works

---

#### Day 12 (Tuesday)
**Goal:** Patient overview (Screen 2)

**Tasks (Member B):**
- [ ] Write `app/patients/[id]/page.tsx`
- [ ] Components: StatCard, ConditionBadge, MedicationsTable, FlagCard
- [ ] Connect to `GET /patients/{id}`

**Deliverable:**
- ✅ Click patient → see overview with all data

---

#### Day 13 (Wednesday)
**Goal:** Timeline (Screen 3) + Flags (Screen 4)

**Tasks (Member B):**
- [ ] Write `app/patients/[id]/timeline/page.tsx`
- [ ] Filter chips (All, Diagnoses, Medications, etc.)
- [ ] Color-coded events
- [ ] Write `app/patients/[id]/flags/page.tsx`
- [ ] "Mark resolved" button → PATCH endpoint

**Deliverable:**
- ✅ Timeline shows chronological events
- ✅ Flags can be resolved

---

#### Day 14 (Thursday)
**Goal:** Contradictions (Screen 5) + Briefing (Screen 6)

**Tasks (Member B):**
- [ ] Write `app/patients/[id]/contradictions/page.tsx`
- [ ] Side-by-side document comparison
- [ ] Write `app/patients/[id]/briefing/page.tsx`
- [ ] Print-friendly styling

**Deliverable:**
- ✅ Contradictions displayed clearly
- ✅ Briefing has Print button

---

#### Day 15 (Friday)
**Goal:** Documents (Screen 7) + Upload

**Tasks (Member B):**
- [ ] Write `app/patients/[id]/documents/page.tsx`
- [ ] Document list + entity-highlighted text
- [ ] Write `components/UploadDropzone.tsx`
- [ ] Connect to `POST /documents`

**Tasks (Member A):**
- [ ] Final query optimization
- [ ] Document Snowflake setup steps

**Deliverable:**
- ✅ All 7 screens working
- ✅ Upload flow works end-to-end

---

## 📅 WEEK 4: Polish + Demo

### Both members — Testing + Documentation

#### Day 16 (Monday) — Testing
**Member A:**
- [ ] `tests/test_views.sql` — SQL unit tests
- [ ] Performance load tests

**Member B:**
- [ ] `tests/test_negation.py` — CRITICAL (patient safety)
- [ ] `tests/test_ner.py` — NER F1 score
- [ ] `tests/test_agents.py` — agent outputs
- [ ] `tests/test_api.py` — all endpoints

---

#### Day 17 (Tuesday) — Bug fixes
- [ ] Triage all GitHub Issues
- [ ] Fix critical bugs
- [ ] Re-run all tests

---

#### Day 18 (Wednesday) — Docker
**Together:**
- [ ] Write `docker/Dockerfile.api`
- [ ] Write `docker/Dockerfile.worker`
- [ ] Write `docker/Dockerfile.frontend`
- [ ] Write `docker-compose.yml`
- [ ] Test: `docker-compose up` brings up everything

---

#### Day 19 (Thursday) — Documentation
**Member A:**
- [ ] Update CONTRACT.md if anything changed
- [ ] Document Snowflake setup in `docs/database_setup.md`

**Member B:**
- [ ] Update README.md with screenshots
- [ ] Architecture diagram
- [ ] API documentation (auto-generated from FastAPI)

---

#### Day 20 (Friday) — Demo prep
**Together:**
- [ ] Record demo video (5 min)
- [ ] Prepare slides
- [ ] Practice presentation
- [ ] **DEMO DAY** 🎉

---

## 🔄 Daily routine

### Every morning (9:30 AM, 15 min)
**Both members on call:**
1. What did I do yesterday?
2. What will I do today?
3. Any blockers?

### Every Friday evening (1 hour)
- Demo what's working
- Review week's progress
- Plan next week
- Update CONTRACT.md if needed

---

## 🚦 Communication rules

| Situation | Action |
|-----------|--------|
| Quick question | WhatsApp |
| Blocker (can't proceed) | Tag in WhatsApp + GitHub Issue |
| Change to CONTRACT.md | PR with both approvals |
| Bug found | GitHub Issue with label `bug` |
| Decision needed | Schedule 30-min call |

---

## 🎯 Parallel work rules

To never block each other:

### If Member B needs Snowflake but Member A isn't done:
- Use **mock data** — write JSON to disk
- Use **SQLite** locally with same schema
- Move on, integrate later

### If Member A needs NLP output but Member B isn't done:
- Use **CSV data** directly (already loaded as entities)
- Build views with existing data
- Member B's real output will replace seed data later

### Mock-first development = no blocking

---

## 📊 Progress tracking

Create a GitHub Project board with columns:
- **Backlog** — all tasks from this document
- **This Week** — current week's tasks
- **In Progress** — currently working on
- **Done** — completed

Update daily.

---

## 🏁 Definition of "task complete"

A task is done when:
1. ✅ Code merged to `main`
2. ✅ Tests written and passing
3. ✅ Other member can run it without help
4. ✅ Documentation updated
5. ✅ No `TODO` comments left

---

## 🚨 Critical path

These tasks block others — do them on time:

| Task | Who | Day | Blocks |
|------|-----|-----|--------|
| Snowflake tables created | A | Day 2 | All of B's DB work |
| NHS data loaded | A | Day 3 | All views and API |
| PDF parser working | B | Day 2 | All NLP work |
| Worker pipeline | B | Day 6 | Real entity population |
| API endpoints | B | Day 10 | All frontend |
| All views | A | Day 4 | All API queries |

**If any of these slip, escalate immediately.**

---

## 🎓 Skills you'll gain

### Member A (DE):
- Snowflake (production-grade)
- S3 + Snowpipe
- ETL pipelines
- SQL optimization
- FHIR data modeling

### Member B (ML):
- spaCy + scispaCy
- LangGraph multi-agent
- FastAPI
- Next.js / React
- LLM prompt engineering

Both: Docker, testing, Git workflow, healthcare data

---

**Good luck team! 🚀**

> Remember: It's a marathon, not a sprint. Pace yourselves, communicate daily, and trust the contract.
