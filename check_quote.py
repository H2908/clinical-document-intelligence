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
cur.execute("SELECT extracted_text FROM clinical_db.core.document WHERE document_id = 'doc_bf78e73c'")
row = cur.fetchone()
text = row[0] if row else ""

q1 = "Repeat echocardiogram in 6 months"
q2 = "Refer to heart failure nurse for medication titration within 2 weeks"

print(f"q1 verbatim: {q1 in text}")
print(f"q2 verbatim: {q2 in text}")
conn.close()
