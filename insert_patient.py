from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os

conn = snowflake.connector.connect(
    account   = os.environ["SNOWFLAKE_ACCOUNT"],
    user      = os.environ["SNOWFLAKE_USER"],
    password  = os.environ["SNOWFLAKE_PASSWORD"],
    database  = "clinical_db",
    warehouse = "clinical_wh",
    role      = os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()
cur.execute("""
    INSERT INTO clinical_db.core.patient (patient_id, name, dob, nhs_number, sex)
    SELECT 'pat_test_01', 'Test Patient', DATE '1980-01-01', '000 000 0001', 'Other'
    WHERE NOT EXISTS (
        SELECT 1 FROM clinical_db.core.patient WHERE patient_id = 'pat_test_01'
    )
""")
print("Patient row inserted:", cur.rowcount)
conn.commit()
conn.close()
