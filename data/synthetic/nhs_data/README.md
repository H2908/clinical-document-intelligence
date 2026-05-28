# NHS-Style Synthetic Clinical Dataset

50 fully synthetic patients with realistic UK clinical data. 100% safe to use — no real patient data.

## What's included

| File | Rows | Description |
|------|------|-------------|
| `patients.csv` | 50 | Patient demographics (NHS numbers, UK addresses) |
| `conditions.csv` | ~140 | Diagnoses with ICD-10 codes |
| `medications.csv` | ~140 | Prescriptions with BNF codes |
| `observations.csv` | ~560 | Lab results (HbA1c, eGFR, BP, etc) |
| `encounters.csv` | ~260 | Doctor visits |
| `allergies.csv` | 50 | Allergy records |
| `documents.csv` | ~180 | Document metadata |
| `flags.csv` | ~50 | Risk flags (HIGH/MEDIUM/LOW) |
| `contradictions.csv` | 15 | Pre-built contradictions for testing |
| `pdfs/` | 17 | Sample clinical PDFs |

## Quick start

### Load in Python

```python
import pandas as pd

patients = pd.read_csv('patients.csv')
conditions = pd.read_csv('conditions.csv')
medications = pd.read_csv('medications.csv')

print(f"Patients: {len(patients)}")
print(patients.head())
```

### Load into Snowflake

```sql
-- Stage upload
PUT file:///path/to/nhs_data/*.csv @your_stage;

-- Load each table
COPY INTO patient FROM @your_stage/patients.csv 
FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1);

COPY INTO entity 
FROM (
  SELECT 
    condition_id, patient_id, 'diagnosis' as entity_type,
    description as entity_value, icd10_code as code, 
    start_date::DATE as event_date
  FROM @your_stage/conditions.csv
)
FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1);
```

### Load into PostgreSQL

```bash
psql -d clinical -c "\\copy patient FROM 'patients.csv' CSV HEADER"
```

## Sample data preview

### Patient
```
patient_id: p001
name: Mohammed Hughes
nhs_number: 181 960 0133
dob: 1986-02-07
sex: M
city: Liverpool
gp_practice: Croydon Health Centre
```

### Condition
```
icd10_code: E11.9
description: Type 2 diabetes mellitus
start_date: 2022-03-15
```

### Medication
```
bnf_code: 06.01.02.02
drug_name: Metformin 1 g
dose: 1 g BD
```

### Flag (pre-built for testing)
```
severity: HIGH
category: ALLERGY CONFLICT
description: Allergy status conflicts between GP letter and cardiology letter
```

## Testing scenarios included

The data includes **deliberate contradictions** for testing your AI detection:

1. **Allergy conflicts** — GP records NKDA, cardiology records penicillin allergy
2. **Dose discrepancies** — Different doses recorded across documents
3. **Metformin + low eGFR** — Drug safety flag scenario
4. **Overdue referrals** — Heart failure nurse follow-up missing

## PDF documents

The `pdfs/` folder contains 17 realistic clinical letters:
- GP referral letters
- Cardiology clinic letters (with intentional contradictions)
- Diabetes review notes (with drug safety scenarios)

Use these to test your PDF parsing pipeline (PyMuPDF, OCR).

## Data is reproducible

Random seed set to 42. Re-run `generate_nhs_data.py` to get identical data.

## Customization

To generate more patients, edit `generate_nhs_data.py`:
```python
for i in range(50):  # Change to 100, 500, 1000...
```

## License

Data is fully synthetic. Free to use for any purpose including commercial.

## Credits

Generated as starter data for clinical document intelligence projects.
Inspired by [Synthea](https://github.com/synthetichealth/synthea) but custom-built for UK/NHS context.
