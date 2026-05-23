function t { param($f) New-Item -ItemType File -Force -Path $f | Out-Null }

New-Item -ItemType Directory -Force -Path `
  "frontend/app/upload",
  "frontend/app/patients/[id]/flags",
  "frontend/app/patients/[id]/briefing",
  "frontend/components",
  "api/routes",
  "ingestion","parsers","nlp","agents","worker","fhir","config",
  "database/schemas","database/views","database/procedures",
  "tests/fixtures",
  "data/synthetic","data/mimic","data/ontologies",
  "docker" | Out-Null

t "frontend/app/page.tsx"
t "frontend/app/upload/page.tsx"
t "frontend/app/patients/[id]/page.tsx"
t "frontend/app/patients/[id]/flags/page.tsx"
t "frontend/app/patients/[id]/briefing/page.tsx"
t "frontend/components/Timeline.tsx"
t "frontend/components/FlagCard.tsx"
t "frontend/components/DocumentViewer.tsx"
t "frontend/components/BriefingPanel.tsx"
t "frontend/components/UploadDropzone.tsx"
t "api/main.py"; t "api/auth.py"; t "api/schemas.py"; t "api/db.py"
t "api/routes/documents.py"; t "api/routes/patients.py"
t "api/routes/flags.py"; t "api/routes/briefing.py"; t "api/routes/fhir.py"
t "ingestion/s3_uploader.py"
t "ingestion/snowpipe_setup.sql"
t "ingestion/s3_external_stage.sql"
t "parsers/file_router.py"; t "parsers/pdf_parser.py"
t "parsers/ocr_engine.py"; t "parsers/text_cleaner.py"
t "nlp/medical_ner.py"; t "nlp/negation_detector.py"
t "nlp/icd10_mapper.py"; t "nlp/bnf_mapper.py"; t "nlp/date_normaliser.py"
t "agents/orchestrator.py"; t "agents/prompts.py"
t "agents/timeline_agent.py"; t "agents/contradiction_agent.py"
t "agents/risk_flag_agent.py"; t "agents/briefing_agent.py"
t "agents/audit_agent.py"
t "worker/main.py"; t "worker/document_processor.py"; t "worker/queue_handler.py"
t "fhir/fhir_builder.py"; t "fhir/fhir_validator.py"
t "database/schemas/01_raw.sql"; t "database/schemas/02_staging.sql"
t "database/schemas/03_core.sql"; t "database/schemas/04_mart.sql"
t "database/schemas/05_fhir.sql"
t "database/views/patient_360.sql"; t "database/views/active_flags.sql"
t "database/views/contradiction_log.sql"
t "database/views/overdue_referrals.sql"
t "database/views/medication_reconciliation.sql"
t "database/procedures/write_entities.sql"
t "database/procedures/write_contradictions.sql"
t "database/procedures/write_flags.sql"
t "database/procedures/delete_patient.sql"
t "database/snowflake_writer.py"
t "database/snowflake_connection.sql"
t "config/settings.py"; t "config/logging.py"
t "tests/test_ner.py"; t "tests/test_negation.py"
t "tests/test_agents.py"; t "tests/test_api.py"
t "tests/test_parsers.py"; t "tests/test_views.sql"
t "data/ontologies/icd10_uk.csv"; t "data/ontologies/bnf_codes.csv"
t "docker/Dockerfile.api"; t "docker/Dockerfile.worker"; t "docker/Dockerfile.frontend"
t ".env.example"; t "docker-compose.yml"; t "requirements.txt"; t "README.md"

Write-Host "Done." -ForegroundColor Green
Get-ChildItem -Recurse | Select-Object FullName
