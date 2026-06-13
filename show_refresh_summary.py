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
    SELECT GET_DDL('PROCEDURE', 'clinical_db.mart.SP_REFRESH_SUMMARY(VARCHAR)')
""")
row = cur.fetchone()
print(row[0] if row else "Not found")
conn.close()
