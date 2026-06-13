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
cur.execute("""
    SELECT extracted_text
    FROM clinical_db.core.document
    WHERE document_id = 'doc_dfba3688'
""")
row = cur.fetchone()
print(row[0] if row else "no row")
conn.close()
