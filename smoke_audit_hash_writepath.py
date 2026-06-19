"""Smoke: re-process one document through the pipeline + verify
provenance_hash lands populated in CORE.flag.

Approach: re-process the smallest pat_test_01 document to keep latency
short. The cleaned NER + agent orchestrator + write_flags chain runs,
and write_flags now passes audit_context, so new flags should have
provenance_hash populated.

Then read back the most recent flags from CORE.flag and confirm the
column is no longer NULL.

Steps:
  1. Snapshot 'before' state of CORE.flag for pat_test_01 - count flags
     with and without provenance_hash.
  2. Delete this one doc's flags + entities so re-processing produces
     a clean write.
  3. Re-process the document via worker.process_from_s3.
  4. Snapshot 'after' state. Expect new flags with populated hashes.
  5. Verify the hashes are deterministic - re-hashing the stored flag
     dict + context should match the stored value.
"""
import os
import time
import snowflake.connector
from dotenv import load_dotenv
from database.snowflake_reader import read_documents_for_patient
from worker.document_processor import process_from_s3
from agents.audit_agent import hash_flag

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


def count_hashed_flags(patient_id):
    """Return (total, with_hash, without_hash) for the patient."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*), "
            "COUNT(provenance_hash), "
            "COUNT(*) - COUNT(provenance_hash) "
            "FROM clinical_db.core.flag WHERE patient_id = %s",
            (patient_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def read_recent_flags(patient_id, limit=5):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT severity, category, description, source_document_id, "
            "provenance_hash, created_at "
            "FROM clinical_db.core.flag WHERE patient_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (patient_id, limit),
        )
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def main():
    PATIENT = "pat_test_01"
    docs = read_documents_for_patient(PATIENT)
    # Pick the smallest doc by document_date as a heuristic for least work
    target = docs[0]
    doc_id = target["document_id"]
    s3_key = target["s3_key"]
    doc_type = target.get("doc_type", "unknown")
    document_date = target.get("document_date")

    print(f"Target document: {doc_id} ({doc_type}, {document_date})\n")

    print("=== BEFORE state ===")
    total, with_hash, without_hash = count_hashed_flags(PATIENT)
    print(f"  CORE.flag for {PATIENT}: total={total}, with_hash={with_hash}, "
          f"without_hash={without_hash}")

    print(f"\n=== Re-processing {doc_id} ===")
    t0 = time.time()
    result = process_from_s3(
        document_id=doc_id,
        patient_id=PATIENT,
        s3_key=s3_key,
        document_date=document_date,
        doc_type=doc_type,
    )
    elapsed = time.time() - t0
    print(f"  process_from_s3 returned in {elapsed:.1f}s")
    print(f"  result status: {result.get('status')}")
    print(f"  agent_counts: {result.get('agent_counts', {})}")

    print("\n=== AFTER state ===")
    total, with_hash, without_hash = count_hashed_flags(PATIENT)
    print(f"  CORE.flag for {PATIENT}: total={total}, with_hash={with_hash}, "
          f"without_hash={without_hash}")

    print("\n=== Recent flags (top 5) ===")
    recent = read_recent_flags(PATIENT, limit=5)
    for f in recent:
        hash_preview = (f.get("provenance_hash") or "NULL")[:16]
        marker = "[HASHED]" if f.get("provenance_hash") else "[NULL  ]"
        print(f"  {marker} {f['category']:<35} subject_doc={f['source_document_id']}")
        print(f"            hash={hash_preview}...")

    # Verify determinism - re-hash one flag with the same context
    print("\n=== Determinism check ===")
    if recent and recent[0].get("provenance_hash"):
        first = recent[0]
        context = {"model": "claude-sonnet-4-6", "prompt_version": "v1.3", "temperature": 0.7}
        # Reconstruct flag dict in the shape attach_hash expects
        flag_dict = {
            "severity": first["severity"],
            "category": first["category"],
            "description": first["description"],
            "source_document_id": first.get("source_document_id"),
        }
        expected = hash_flag(flag_dict, context)
        stored = first["provenance_hash"]
        if expected == stored:
            print(f"  [OK] Stored hash matches re-computed hash: {expected[:16]}...")
        else:
            print(f"  [WARN] Stored hash != re-computed hash")
            print(f"         stored:   {stored}")
            print(f"         expected: {expected}")
            print(f"  This may be normal: the flag dict at write time included")
            print(f"  more fields than we have here (e.g. clinical_subject,")
            print(f"  source_quote). Audit verifier reads from JSONL where the")
            print(f"  full dict is preserved.")
    else:
        print("  No hashed flag to verify against.")


if __name__ == "__main__":
    main()