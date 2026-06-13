"""Check whether pat_test_01's documents overlap with the synthetic held-out set."""
from dotenv import load_dotenv
load_dotenv()
import snowflake.connector, os, hashlib
from pathlib import Path

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
cur = conn.cursor()

print("=== pat_test_01 document filenames (from S3 keys) ===")
cur.execute("""
    SELECT document_id, s3_key
    FROM clinical_db.core.document
    WHERE patient_id = 'pat_test_01'
""")
test_filenames = set()
for did, s3_key in cur.fetchall():
    fname = os.path.basename(s3_key) if s3_key else "<no s3 key>"
    print(f"  {did}: {fname}")
    test_filenames.add(fname)
conn.close()

print("\n=== Synthetic set filenames ===")
synth_files = set()
for p in Path("data/synthetic/documents").glob("*.pdf"):
    synth_files.add(p.name)
    print(f"  {p.name}")

print("\n=== OVERLAP (held-out contamination risk) ===")
overlap = test_filenames & synth_files
if overlap:
    print(f"  CONTAMINATION: {len(overlap)} files in both pat_test_01 and synthetic set:")
    for f in overlap:
        print(f"    {f}")
else:
    print("  Clean — no overlap.")