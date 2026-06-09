from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()

print("=== Existing docs for pat_test_01 ===")
cur.execute("""
    SELECT document_id, doc_type, document_date,
           CASE WHEN extracted_text IS NULL THEN NULL
                ELSE LENGTH(extracted_text) END AS text_length,
           SUBSTR(extracted_text, 1, 80) AS preview
    FROM clinical_db.core.document
    WHERE patient_id = 'pat_test_01'
    ORDER BY created_at DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]}  type={row[1]}  date={row[2]}  text_len={row[3]}")
    if row[4]:
        print(f"    preview: {row[4][:80]!r}")

conn.close()