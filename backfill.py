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
    INSERT INTO clinical_db.core.document
        (document_id, patient_id, file_name, doc_type, source,
         document_date, s3_key, status)
    SELECT
        document_id, patient_id, file_name, doc_type, source,
        document_date, s3_key, 'processed'
    FROM clinical_db.raw.raw_documents
    WHERE patient_id = 'pat_test_01'
      AND document_id NOT IN (SELECT document_id FROM clinical_db.core.document)
""")
print("Backfilled rows:", cur.rowcount)
conn.commit()
conn.close()
