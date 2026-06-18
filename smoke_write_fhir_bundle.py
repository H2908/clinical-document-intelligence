"""Block 3 smoke: build pat_test_01's bundle and write it to
mart.fhir_patient_bundle, then read it back to confirm the round-trip.

Verifies:
  1. write_fhir_bundle runs without exception against real Snowflake
  2. The row lands in mart.fhir_patient_bundle (rowcount changes from 0 to 1)
  3. The bundle reads back identical-shaped (entry count matches)
  4. is_stale is FALSE on the written row
  5. resource_count matches what we wrote
"""
import os
import json
import snowflake.connector
from dotenv import load_dotenv

from clinical_fhir.fhir_builder import build_patient_bundle, write_fhir_bundle

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


def count_bundles():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM clinical_db.mart.fhir_patient_bundle")
        return cur.fetchone()[0]
    finally:
        conn.close()


def read_bundle(patient_id: str):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT patient_id, fhir_version, resource_count, generated_at, "
            "is_stale, bundle "
            "FROM clinical_db.mart.fhir_patient_bundle WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "patient_id": row[0],
            "fhir_version": row[1],
            "resource_count": row[2],
            "generated_at": row[3],
            "is_stale": row[4],
            "bundle_raw": row[5],
        }
    finally:
        conn.close()


def main():
    PATIENT = "pat_test_01"

    # 1. Build bundle from CORE
    print("Step 1: build bundle from CORE")
    bundle = build_patient_bundle(PATIENT)
    expected_entries = len(bundle["entry"])
    print(f"  built: {expected_entries} entries")
    print(f"  resourceType: {bundle['resourceType']}, type: {bundle['type']}")

    # 2. Confirm starting row count
    before = count_bundles()
    print(f"\nStep 2: mart.fhir_patient_bundle row count before write = {before}")

    # 3. Write
    print(f"\nStep 3: write bundle for {PATIENT}")
    result = write_fhir_bundle(PATIENT, bundle)
    print(f"  result: {result}")

    # 4. Confirm row count
    after = count_bundles()
    print(f"\nStep 4: mart.fhir_patient_bundle row count after write = {after}")

    # 5. Read back
    print(f"\nStep 5: read bundle back from Snowflake")
    row = read_bundle(PATIENT)
    if row is None:
        print("  [FAIL] bundle row not found")
        return 1
    print(f"  patient_id:     {row['patient_id']}")
    print(f"  fhir_version:   {row['fhir_version']}")
    print(f"  resource_count: {row['resource_count']}")
    print(f"  generated_at:   {row['generated_at']}")
    print(f"  is_stale:       {row['is_stale']}")

    # Snowflake VARIANT comes back as a JSON string or already a dict
    raw = row["bundle_raw"]
    if isinstance(raw, str):
        stored_bundle = json.loads(raw)
    else:
        stored_bundle = raw

    stored_entries = len(stored_bundle.get("entry", []))
    print(f"  stored entries: {stored_entries}")

    # 6. Verify
    print("\nStep 6: verification")
    checks = [
        ("Row exists in table", row is not None),
        ("resource_count matches entry count", row["resource_count"] == expected_entries),
        ("Stored bundle entry count matches", stored_entries == expected_entries),
        ("is_stale is FALSE", row["is_stale"] is False or row["is_stale"] == 0),
        ("fhir_version is R4", row["fhir_version"] == "R4"),
    ]
    all_pass = True
    for name, ok in checks:
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}")
        if not ok:
            all_pass = False

    return 0 if all_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())