"""Block 2.5: clean up pat_test_01's CORE.entity rows and re-process.

WHY: The 9 documents were processed before yesterday's NER classifier
fix (efbfa09). They carry false-positive 'Diagnosis' entities for
addresses, place names, and document structure noise - some with
spurious ICD-10 codes from the UK-postcode/ICD-10 collision (M14, B12).
The FHIR bundle assembled today exposed this: 102 Conditions, most
garbage.

WHAT: For each of the 9 documents:
  1. DELETE rows from CORE.entity WHERE document_id = doc
  2. Re-run worker.document_processor.process_from_s3 with the cleaned
     NER (which now rejects addresses, place names, section headers,
     and postcode-shape ICD-10 matches).
  3. Smoke check entity counts before/after.

NOT IN SCOPE:
  - bnf_code persistence (SP_WRITE_ENTITIES has no bnf_code column;
    partner-side migration required separately)
  - timeline/flag/contradiction regeneration (process_from_s3 already
    re-runs the agent orchestrator after entity writes)

Safety:
  - DELETE limited to specific document_ids belonging to pat_test_01
  - No CORE.entity FKs from anything else (verified against 03_core.sql)
  - Idempotent: running twice produces the same end state
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


def count_entities(document_id: str) -> int:
    """Count entities currently in CORE.entity for one document."""
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


def delete_entities_for_document(document_id: str) -> int:
    """DELETE entity rows for one document. Returns rows deleted."""
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


def delete_observations_for_document(document_id: str) -> int:
    """DELETE observation rows for one document. Returns rows deleted.

    Needed because process_from_s3 re-extracts observations via lab_parser
    and appends without dedup; without explicit delete, duplicates compound
    on every cleanup run.
    """
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
    PATIENT_ID = "pat_test_01"
    docs = read_documents_for_patient(PATIENT_ID)
    print(f"Found {len(docs)} documents for {PATIENT_ID}\n")

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
        print(f"  Before: {before} entities in CORE.entity")

        # 1. DELETE existing entity + observation rows for this doc
        deleted_e = delete_entities_for_document(doc_id)
        deleted_o = delete_observations_for_document(doc_id)
        print(f"  Deleted: {deleted_e} entity rows, {deleted_o} observation rows")

        # 2. Re-process via worker (re-parses PDF, re-runs NER, writes back)
        t0 = time.time()
        try:
            result = process_from_s3(
                document_id=doc_id,
                patient_id=PATIENT_ID,
                s3_key=s3_key,
                document_date=document_date,
                doc_type=doc_type,
            )
            entity_count = len(result.get("entities", []))
            elapsed = time.time() - t0
            print(f"  Re-processed in {elapsed:.1f}s: {entity_count} entities written")
        except Exception as e:
            print(f"  [FAIL] re-processing failed: {type(e).__name__}: {e}")
            summary.append((doc_id, before, None, str(e)))
            continue

        # 3. Confirm
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
    print(f"{'Document':<20} {'Before':>8} {'After':>8} {'Delta':>8}")
    print("-" * 60)
    for doc_id, before, after, err in summary:
        if err is not None:
            print(f"{doc_id:<20} {before:>8} {'FAIL':>8}    {err[:30]}")
        else:
            delta = after - before
            sign = "+" if delta >= 0 else ""
            print(f"{doc_id:<20} {before:>8} {after:>8} {sign}{delta:>7}")
    print("-" * 60)
    grand_delta = after_total - before_total
    sign = "+" if grand_delta >= 0 else ""
    print(f"{'TOTAL':<20} {before_total:>8} {after_total:>8} {sign}{grand_delta:>7}")


if __name__ == "__main__":
    main()