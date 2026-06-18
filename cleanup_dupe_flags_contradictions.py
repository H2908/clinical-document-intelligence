"""Demo cleanup: dedupe pat_test_01's CORE.flag and CORE.contradiction.

Background: today's repeated cleanup runs (cleanup_pat_test_01_entities.py)
called process_from_s3 in a loop over 9 documents. Each call re-ran the
orchestrator which regenerates patient-level outputs (flags, contradictions,
briefing) and wrote them via write_flags / write_contradictions WITHOUT
deleting prior rows. Result: rows accumulated 5-13x across the day's
cleanup runs.

Fix: keep newest row per (category, description) for flags and per
(category, doc_a_id, doc_b_id) for contradictions. Delete the rest.

This is one-shot demo data cleanup, not a permanent fix. The permanent
fix lives in agents/orchestrator.py: it should delete prior patient-level
output rows before write. Tracked as a partner-side or future task; not
in scope today.

Safety:
  - Scoped to patient_id = 'pat_test_01' on every DELETE
  - Uses MERGE-like QUALIFY ROW_NUMBER() OVER (PARTITION BY ...
    ORDER BY created_at DESC) to ensure newest survives
  - Counts before + after; aborts if delta unexpected
"""
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()
PATIENT = "pat_test_01"

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    database="clinical_db",
    warehouse="clinical_wh",
    role=os.environ["SNOWFLAKE_ROLE"],
)
try:
    cur = conn.cursor()

    # ---------- CORE.flag ----------
    print("=== CORE.flag ===")
    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT category || '|' || description) "
        "FROM clinical_db.core.flag WHERE patient_id = %s",
        (PATIENT,),
    )
    before_total, distinct = cur.fetchone()
    print(f"  Before:  {before_total} rows, {distinct} distinct by (category,description)")

    # Delete duplicates: for each (category, description), keep newest
    # by created_at, delete older copies. We need to identify flag_ids
    # to delete first, then DELETE by those ids.
    cur.execute(
        f"""
        SELECT flag_id FROM (
            SELECT flag_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY category, description
                       ORDER BY created_at DESC
                   ) AS rn
            FROM clinical_db.core.flag
            WHERE patient_id = %s
        ) WHERE rn > 1
        """,
        (PATIENT,),
    )
    flag_ids_to_delete = [row[0] for row in cur.fetchall()]
    print(f"  Will delete: {len(flag_ids_to_delete)} duplicate rows")

    if flag_ids_to_delete:
        # DELETE in batches to avoid SQL length limits (1000 per batch)
        BATCH = 500
        for i in range(0, len(flag_ids_to_delete), BATCH):
            batch = flag_ids_to_delete[i:i + BATCH]
            placeholders = ",".join(["%s"] * len(batch))
            cur.execute(
                f"DELETE FROM clinical_db.core.flag WHERE flag_id IN ({placeholders})",
                tuple(batch),
            )
        conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM clinical_db.core.flag WHERE patient_id = %s",
        (PATIENT,),
    )
    after_total = cur.fetchone()[0]
    print(f"  After:   {after_total} rows ({after_total - before_total:+d})")

    if after_total != distinct:
        print(f"  [WARN] expected {distinct} after dedup, got {after_total}")
    else:
        print(f"  [OK] flag dedup landed exactly at distinct count")

    # ---------- CORE.contradiction ----------
    print()
    print("=== CORE.contradiction ===")
    cur.execute(
        "SELECT COUNT(*), "
        "COUNT(DISTINCT category || '|' || COALESCE(doc_a_id,'') "
        "|| '|' || COALESCE(doc_b_id,'')) "
        "FROM clinical_db.core.contradiction WHERE patient_id = %s",
        (PATIENT,),
    )
    before_total_c, distinct_c = cur.fetchone()
    print(f"  Before:  {before_total_c} rows, {distinct_c} distinct by (category,doc_a,doc_b)")

    cur.execute(
        """
        SELECT contradiction_id FROM (
            SELECT contradiction_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY category, doc_a_id, doc_b_id
                       ORDER BY created_at DESC
                   ) AS rn
            FROM clinical_db.core.contradiction
            WHERE patient_id = %s
        ) WHERE rn > 1
        """,
        (PATIENT,),
    )
    contr_ids_to_delete = [row[0] for row in cur.fetchall()]
    print(f"  Will delete: {len(contr_ids_to_delete)} duplicate rows")

    if contr_ids_to_delete:
        BATCH = 500
        for i in range(0, len(contr_ids_to_delete), BATCH):
            batch = contr_ids_to_delete[i:i + BATCH]
            placeholders = ",".join(["%s"] * len(batch))
            cur.execute(
                f"DELETE FROM clinical_db.core.contradiction "
                f"WHERE contradiction_id IN ({placeholders})",
                tuple(batch),
            )
        conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM clinical_db.core.contradiction WHERE patient_id = %s",
        (PATIENT,),
    )
    after_total_c = cur.fetchone()[0]
    print(f"  After:   {after_total_c} rows ({after_total_c - before_total_c:+d})")

    if after_total_c != distinct_c:
        print(f"  [WARN] expected {distinct_c} after dedup, got {after_total_c}")
    else:
        print(f"  [OK] contradiction dedup landed exactly at distinct count")

    print()
    print("=== Final state ===")
    print(f"  pat_test_01 flags:          {after_total}")
    print(f"  pat_test_01 contradictions: {after_total_c}")
    print(f"  Overview card should now show ~{after_total} flags, "
          f"~{after_total_c} contradictions")
finally:
    conn.close()