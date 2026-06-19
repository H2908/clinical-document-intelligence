"""Smoke test the permanent fix: process one document and confirm
flag/contradiction row counts do NOT inflate.

The orchestrator now calls write_flags(... replace_existing=True) which
deletes patient-scoped rows before insert. So one re-process should:
  - Keep flag rowcount roughly stable (or change by the patient-level
    flag delta from this doc, which is small)
  - Keep contradiction rowcount roughly stable

Before this fix: row counts would multiply because of append-only writes.

Verifies the fix end-to-end through real Snowflake.
"""
import os
import time
import snowflake.connector
from dotenv import load_dotenv
from database.snowflake_reader import read_documents_for_patient
from worker.document_processor import process_from_s3

load_dotenv()


def _conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="clinical_db",
        warehouse="clinical_wh",
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def counts():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.flag WHERE patient_id = 'pat_test_01'"
        )
        flags = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.contradiction WHERE patient_id = 'pat_test_01'"
        )
        contras = cur.fetchone()[0]
        return flags, contras
    finally:
        conn.close()


def main():
    PATIENT = "pat_test_01"
    docs = read_documents_for_patient(PATIENT)
    target = docs[0]
    doc_id = target["document_id"]
    s3_key = target["s3_key"]
    doc_type = target.get("doc_type", "unknown")
    document_date = target.get("document_date")

    print(f"Smoke target: {doc_id} ({doc_type})\n")

    before_f, before_c = counts()
    print(f"BEFORE: flags={before_f}, contradictions={before_c}")

    print(f"\nRe-processing {doc_id}...")
    t0 = time.time()
    result = process_from_s3(
        document_id=doc_id,
        patient_id=PATIENT,
        s3_key=s3_key,
        document_date=document_date,
        doc_type=doc_type,
    )
    elapsed = time.time() - t0
    print(f"  process_from_s3 in {elapsed:.1f}s, status={result.get('status')}")

    after_f, after_c = counts()
    print(f"\nAFTER:  flags={after_f}, contradictions={after_c}")

    print()
    print("=== Verdict ===")
    # Pass criterion: row counts should be on the order of pre-fix distinct
    # counts (36 flags, 12 contradictions), not inflated. Allow some delta
    # since the agent run could produce slightly different output.
    flag_inflated = after_f > before_f * 1.5
    contra_inflated = after_c > before_c * 1.5

    if not flag_inflated and not contra_inflated:
        print(f"  [OK] No inflation. Permanent fix is working.")
        print(f"       Flag delta:          {after_f - before_f:+d}")
        print(f"       Contradiction delta: {after_c - before_c:+d}")
    else:
        if flag_inflated:
            print(f"  [FAIL] Flag count inflated {before_f} -> {after_f}")
        if contra_inflated:
            print(f"  [FAIL] Contradiction count inflated {before_c} -> {after_c}")


if __name__ == "__main__":
    main()