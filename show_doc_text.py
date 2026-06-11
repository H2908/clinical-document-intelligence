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

for doc_id in ("doc_719a82d6", "doc_bf78e73c"):
    cur.execute(f"SELECT extracted_text FROM clinical_db.core.document WHERE document_id = '{doc_id}'")
    row = cur.fetchone()
    if row:
        print(f"=== {doc_id} ===")
        print(row[0])
        print()
conn.close()