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

print("=== CORE.observation table ===")
try:
    cur.execute("DESCRIBE TABLE clinical_db.core.observation")
    for row in cur.fetchall():
        print(f"  {row[0]:25s}  {row[1]}")
except Exception as e:
    print(f"  NOT FOUND: {e}")

print()
print("=== SP_WRITE_OBSERVATIONS procedure ===")
cur.execute("SHOW PROCEDURES LIKE 'SP_WRITE_OBSERVATIONS' IN SCHEMA clinical_db.core")
results = cur.fetchall()
if results:
    for r in results:
        print(f"  FOUND: {r[1]}")
else:
    print("  NOT DEPLOYED")

conn.close()
