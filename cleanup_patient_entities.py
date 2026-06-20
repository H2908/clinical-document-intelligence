"""Cleanup script: re-process all of a patient's documents through the
current NER + orchestrator pipeline.

Use this when:
  - NER rules change (substring fix, new stopwords, etc.) and existing
    entity rows need to be re-extracted
  - Briefing demographic logic changes and MART needs refreshing
  - Stale agent outputs need a wholesale rebuild

The cleanup is two-phase per document:
  1. DELETE the document's existing entities + observations
  2. process_from_s3 re-extracts entities + runs the full agent pipeline

write_flags / write_contradictions use replace_existing=True
internally, so patient-level outputs (flags, contradictions, briefing)
self-clean rather than accumulating.

Usage:
    python cleanup_patient_entities.py pat_fa9fb06f
    python cleanup_patient_entities.py pat_test_01
"""
import os
import sys
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


def count_entities(document_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM clinical_db.core.entity WHERE document_id = %s",
            (document_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def delete_entities_for_document(document_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.entity WHERE document_id = %s",
            (document_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def delete_observations_for_document(document_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM clinical_db.core.observation WHERE source_document_id = %s",
            (document_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python cleanup_patient_entities.py <patient_id>")
        sys.exit(1)

    patient_id = sys.argv[1]
    docs = read_documents_for_patient(patient_id)
    print(f"Found {len(docs)} documents for {patient_id}\n")

    if not docs:
        print("No documents to process. Exiting.")
        return

    before_total = 0
    after_total = 0
    summary = []

    for i, doc in enumerate(docs, 1):
        doc_id = doc["document_id"]
        s3_key = doc["s3_key"]
        doc_type = doc.get("doc_type", "unknown")
        document_date = doc.get("document_date")

        before = count_entities(doc_id)
        before_total += before
        print(f"[{i}/{len(docs)}] {doc_id} ({doc_type}, {document_date})")
        print(f"  Before: {before} entities")

        deleted_e = delete_entities_for_document(doc_id)
        deleted_o = delete_observations_for_document(doc_id)
        print(f"  Deleted: {deleted_e} entity rows, {deleted_o} observation rows")

        t0 = time.time()
        try:
            result = process_from_s3(
                document_id=doc_id,
                patient_id=patient_id,
                s3_key=s3_key,
                document_date=document_date,
                doc_type=doc_type,
            )
            elapsed = time.time() - t0
            print(f"  Re-processed in {elapsed:.1f}s, status={result.get('status')}")
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            summary.append((doc_id, before, None, str(e)))
            continue

        after = count_entities(doc_id)
        after_total += after
        delta = after - before
        sign = "+" if delta >= 0 else ""
        print(f"  After:  {after} entities ({sign}{delta})")
        print()
        summary.append((doc_id, before, after, None))

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'Document':<22} {'Before':>8} {'After':>8} {'Delta':>8}")
    print("-" * 60)
    for doc_id, before, after, err in summary:
        if err is not None:
            print(f"{doc_id:<22} {before:>8} {'FAIL':>8}    {err[:30]}")
        else:
            delta = after - before
            sign = "+" if delta >= 0 else ""
            print(f"{doc_id:<22} {before:>8} {after:>8} {sign}{delta:>7}")
    print("-" * 60)
    grand_delta = after_total - before_total
    sign = "+" if grand_delta >= 0 else ""
    print(f"{'TOTAL':<22} {before_total:>8} {after_total:>8} {sign}{grand_delta:>7}")


if __name__ == "__main__":
    main()