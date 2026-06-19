"""Smoke the orchestrator fix end-to-end.

Runs the full agent pipeline on pat_test_01 (mirrors what the
post-delete background task does), then verifies CORE.flag no longer
contains references to deleted documents.

Expected outcome:
  - Orchestrator runs without errors
  - CORE.flag rowcount drops to whatever the 3 remaining docs produce
  - source_document_id values in CORE.flag are exactly the 3 remaining
    doc IDs (no orphans from doc_bf78e73c, doc_7f61d513, doc_2b441e2c)
"""
import os
import snowflake.connector
from dotenv import load_dotenv
from agents.orchestrator import run_agents

load_dotenv()
PATIENT = "pat_test_01"


def _conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def show_state(label):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.document WHERE patient_id = %s",
            (PATIENT,),
        )
        doc_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*), COUNT(DISTINCT source_document_id) "
            "FROM clinical_db.core.flag WHERE patient_id = %s",
            (PATIENT,),
        )
        f_rows, f_docs = cur.fetchone()

        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.contradiction WHERE patient_id = %s",
            (PATIENT,),
        )
        c_rows = cur.fetchone()[0]

        cur.execute(
            "SELECT DISTINCT source_document_id "
            "FROM clinical_db.core.flag WHERE patient_id = %s "
            "ORDER BY source_document_id",
            (PATIENT,),
        )
        sources = [r[0] for r in cur.fetchall()]

        print(f"\n=== {label} ===")
        print(f"  CORE.document rows:                       {doc_count}")
        print(f"  CORE.flag rows:                           {f_rows}")
        print(f"  CORE.flag distinct source_document_ids:   {f_docs}")
        print(f"  CORE.contradiction rows:                  {c_rows}")
        print(f"  source_document_ids in CORE.flag:")
        for s in sources:
            print(f"    {s}")
        return sources
    finally:
        conn.close()


def main():
    # 1. Snapshot before
    sources_before = show_state("BEFORE orchestrator regen")

    # 2. Get the actual remaining doc IDs so we can verify orphans are killed
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT document_id FROM clinical_db.core.document WHERE patient_id = %s",
            (PATIENT,),
        )
        remaining_docs = {r[0] for r in cur.fetchall()}
        print(f"\nRemaining doc IDs in CORE.document: {sorted(remaining_docs)}")
    finally:
        conn.close()

    # 3. Run the orchestrator (mirrors post-delete regen)
    print("\nRunning orchestrator (mirrors post-delete regen)...")
    state = run_agents(patient_id=PATIENT, document_id="")
    print(f"  Orchestrator output: flags={len(state['flags'])}, "
          f"contradictions={len(state['contradictions'])}, "
          f"briefing={'present' if state['briefing'] else 'missing'}")
    if state['errors']:
        print(f"  Errors: {state['errors']}")

    # 4. Snapshot after
    sources_after = show_state("AFTER orchestrator regen")

    # 5. Verdict
    print("\n=== VERDICT ===")
    orphans = set(sources_after) - remaining_docs
    if orphans:
        print(f"  [FAIL] flags still reference deleted docs: {orphans}")
    else:
        print(f"  [OK] All flag source_document_ids reference existing documents.")
        if not sources_after:
            print("       (Or no flags emitted, which is also valid.)")


if __name__ == "__main__":
    main()