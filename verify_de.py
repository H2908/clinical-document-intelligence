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

print("=== Procedures in CORE ===")
cur.execute("SHOW PROCEDURES IN SCHEMA clinical_db.core")
for r in cur.fetchall():
    print(" ", r[1])

print()
print("=== Tables in MART ===")
cur.execute("SHOW TABLES IN SCHEMA clinical_db.mart")
for r in cur.fetchall():
    print(" ", r[1])

conn.close()
