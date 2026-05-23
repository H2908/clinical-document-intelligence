# Column Mapping Cheatsheet

Quick reference: NHS synthetic CSV columns → Snowflake table columns.

## patients.csv → `patient` table

| CSV column | Snowflake column | Type | Notes |
|------------|------------------|------|-------|
| `patient_id` | `patient_id` | STRING (PK) | direct copy |
| `nhs_number` | `nhs_number` | STRING | direct copy |
| `first_name` | `first_name` | STRING | direct copy |
| `last_name` | `last_name` | STRING | direct copy |
| `dob` | `dob` | DATE | cast `::DATE` |
| `sex` | `sex` | STRING(1) | direct copy |
| `address` | `address` | STRING | direct copy |
| `city` | `city` | STRING | direct copy |
| `postcode` | `postcode` | STRING | direct copy |
| `gp_practice` | `gp_practice` | STRING | direct copy |
| `registered_date` | `registered_date` | DATE | cast `::DATE` |

**Sample SQL:**
```sql
COPY INTO patient (patient_id, nhs_number, first_name, last_name, dob, 
                   sex, address, city, postcode, gp_practice, registered_date)
FROM (
  SELECT 
    $1, $2, $3, $4, $5::DATE, $7, $8, $9, $11, $13, $14::DATE
  FROM @stage/patients.csv
)
FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1);
```

## conditions.csv → `entity` table (entity_type='diagnosis')

| CSV column | Snowflake column | Notes |
|------------|------------------|-------|
| `condition_id` | `entity_id` | direct copy |
| `patient_id` | `patient_id` | direct copy |
| — | `entity_type` | hardcode `'diagnosis'` |
| `description` | `entity_value` | direct copy |
| `icd10_code` | `code` | direct copy |
| — | `code_system` | hardcode `'ICD10'` |
| `start_date` | `event_date` | cast `::DATE` |
| — | `negated` | hardcode `FALSE` |
| — | `confidence` | hardcode `1.0` (manual data) |

**Sample SQL:**
```sql
INSERT INTO entity (entity_id, patient_id, entity_type, entity_value, 
                    code, code_system, event_date, negated, confidence, doc_id)
SELECT 
    condition_id,
    patient_id,
    'diagnosis',
    description,
    icd10_code,
    'ICD10',
    start_date::DATE,
    FALSE,
    1.0,
    NULL  -- no source document for seed data
FROM @stage/conditions.csv;
```

## medications.csv → `entity` table (entity_type='medication')

| CSV column | Snowflake column | Notes |
|------------|------------------|-------|
| `medication_id` | `entity_id` | direct copy |
| `patient_id` | `patient_id` | direct copy |
| — | `entity_type` | hardcode `'medication'` |
| `drug_name` | `entity_value` | direct copy |
| `bnf_code` | `code` | direct copy |
| — | `code_system` | hardcode `'BNF'` |
| `dose` | `dose` | direct copy |
| `start_date` | `event_date` | cast `::DATE` |

## observations.csv → `entity` table (entity_type='observation')

| CSV column | Snowflake column |
|------------|------------------|
| `observation_id` | `entity_id` |
| `patient_id` | `patient_id` |
| — | `entity_type` = `'observation'` |
| `observation_name` | `entity_value` |
| `value` | `value` |
| `unit` | `unit` |
| `date` | `event_date` |

## flags.csv → `flag` table

| CSV column | Snowflake column | Notes |
|------------|------------------|-------|
| `flag_id` | `flag_id` | direct copy |
| `patient_id` | `patient_id` | direct copy |
| `severity` | `severity` | direct copy |
| `category` | `category` | direct copy |
| `description` | `description` | direct copy |
| `status` | `status` | direct copy |
| `created_at` | `created_at` | cast `::TIMESTAMP_NTZ` |

## contradictions.csv → `contradiction` table

| CSV column | Snowflake column |
|------------|------------------|
| `contradiction_id` | `contradiction_id` |
| `patient_id` | `patient_id` |
| `severity` | `severity` |
| `category` | `category` |
| `doc_a_id` | `doc_a_id` |
| `doc_a_statement` | `doc_a_statement` |
| `doc_b_id` | `doc_b_id` |
| `doc_b_statement` | `doc_b_statement` |
| `ai_recommendation` | `ai_recommendation` |
| `status` | `status` |

## documents.csv → `document` table

| CSV column | Snowflake column | Notes |
|------------|------------------|-------|
| `doc_id` | `doc_id` | direct copy |
| `patient_id` | `patient_id` | direct copy |
| `filename` | `filename` | direct copy |
| `doc_type` | `doc_type` | direct copy |
| — | `s3_key` | construct: `raw/{patient_id}/{doc_id}.pdf` |
| `document_date` | `document_date` | cast `::DATE` |
| `uploaded_at` | `uploaded_at` | cast `::TIMESTAMP_NTZ` |
| — | `processing_status` | hardcode `'completed'` |

## Quick load script for ALL CSVs

```sql
-- 1. Create internal stage
CREATE STAGE IF NOT EXISTS nhs_data_stage 
  FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"');

-- 2. Upload local files
-- Run from snowsql CLI:
-- PUT file:///path/to/nhs_data/*.csv @nhs_data_stage;

-- 3. Load patient table
COPY INTO patient FROM @nhs_data_stage/patients.csv;

-- 4. Load entity table (from 3 CSVs)
INSERT INTO entity (entity_id, patient_id, entity_type, entity_value, 
                    code, code_system, event_date, negated, confidence)
SELECT condition_id, patient_id, 'diagnosis', description, 
       icd10_code, 'ICD10', start_date::DATE, FALSE, 1.0
FROM @nhs_data_stage/conditions.csv;

INSERT INTO entity (entity_id, patient_id, entity_type, entity_value,
                    code, code_system, dose, event_date, negated, confidence)
SELECT medication_id, patient_id, 'medication', drug_name,
       bnf_code, 'BNF', dose, start_date::DATE, FALSE, 1.0
FROM @nhs_data_stage/medications.csv;

INSERT INTO entity (entity_id, patient_id, entity_type, entity_value,
                    value, unit, event_date, negated, confidence)
SELECT observation_id, patient_id, 'observation', observation_name,
       value, unit, date::DATE, FALSE, 1.0
FROM @nhs_data_stage/observations.csv;

-- 5. Load documents
COPY INTO document (doc_id, patient_id, filename, doc_type, document_date, uploaded_at)
FROM @nhs_data_stage/documents.csv;

-- 6. Load flags
COPY INTO flag FROM @nhs_data_stage/flags.csv;

-- 7. Load contradictions
COPY INTO contradiction FROM @nhs_data_stage/contradictions.csv;

-- 8. Verify
SELECT 'patient' AS table_name, COUNT(*) AS rows FROM patient
UNION ALL SELECT 'entity', COUNT(*) FROM entity
UNION ALL SELECT 'document', COUNT(*) FROM document
UNION ALL SELECT 'flag', COUNT(*) FROM flag
UNION ALL SELECT 'contradiction', COUNT(*) FROM contradiction;
```

Expected output:
```
patient        | 50
entity         | ~840   (139 + 141 + 564)
document       | 180
flag           | 53
contradiction  | 15
```
