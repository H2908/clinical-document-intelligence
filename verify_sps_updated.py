"""Check if SP_WRITE_FLAGS and SP_WRITE_ENTITIES were updated to bind the
new columns.

We can't easily diff the proc bodies, but we can write a row with the new
field set and check if it persists. If the SP binds it, we'll see the
value back. If the SP doesn't bind it, the column stays NULL.

Test:
  1. Insert a flag with provenance_hash = 'TEST_HASH_xxxxxx'
  2. Read it back, check if provenance_hash column has the value
  3. Clean up the test row
"""
import os
import json
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

TEST_PATIENT = "_test_sp_verify"  # unlikely to collide with real data
TEST_HASH = "TEST_HASH_" + "a" * 54  # 64 chars total

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

    # Clean any stale test data from a prior run
    cur.execute("DELETE FROM clinical_db.core.flag WHERE patient_id = %s",
                (TEST_PATIENT,))
    conn.commit()

    # SP_WRITE_FLAGS test
    print("=== Test 1: SP_WRITE_FLAGS binds provenance_hash? ===")
    test_flag = [{
        "severity": "MEDIUM",
        "category": "TEST_SP_VERIFY",
        "description": "SP verification flag - will be deleted",
        "source_document_id": "doc_sp_verify",
        "clinical_subject": "sp_verify_test",
        "provenance_hash": TEST_HASH,
    }]
    flags_json = json.dumps(test_flag)
    sql = ("CALL clinical_db.core.SP_WRITE_FLAGS("
           f"'{TEST_PATIENT}', PARSE_JSON($${flags_json}$$))")
    cur.execute(sql)
    result = cur.fetchone()
    print(f"  SP_WRITE_FLAGS returned: {result}")

    cur.execute(
        "SELECT provenance_hash FROM clinical_db.core.flag WHERE patient_id = %s",
        (TEST_PATIENT,),
    )
    row = cur.fetchone()
    if row is None:
        print("  [FAIL] Flag did not land in CORE.flag at all")
    else:
        stored_hash = row[0]
        if stored_hash == TEST_HASH:
            print(f"  [OK]   provenance_hash bound correctly: {stored_hash[:16]}...")
        else:
            print(f"  [FAIL] Flag landed but provenance_hash is {stored_hash!r} "
                  f"(expected {TEST_HASH[:16]}...)")
            print("         SP_WRITE_FLAGS does not bind the field. "
                  "Partner needs to update the proc.")

    # Clean up
    cur.execute("DELETE FROM clinical_db.core.flag WHERE patient_id = %s",
                (TEST_PATIENT,))
    conn.commit()

    # SP_WRITE_ENTITIES test - need to call SP_WRITE_ENTITIES with a Drug
    # entity carrying bnf_code, then read it back
    print()
    print("=== Test 2: SP_WRITE_ENTITIES binds bnf_code? ===")
    # First clean any stale test data
    cur.execute("DELETE FROM clinical_db.core.entity WHERE document_id = %s",
                ("doc_sp_verify",))
    conn.commit()

    test_entity = [{
        "entity_type": "Drug",
        "text": "test_drug 5 mg",
        "start_offset": 0,
        "end_offset": 13,
        "negated": False,
        "icd10_code": None,
        "bnf_code": "TEST_BNF_001",
        "normalised_value": "test_drug",
    }]
    entities_json = json.dumps(test_entity)
    sql = ("CALL clinical_db.core.SP_WRITE_ENTITIES("
           f"'doc_sp_verify', '{TEST_PATIENT}', PARSE_JSON($${entities_json}$$))")
    cur.execute(sql)
    result = cur.fetchone()
    print(f"  SP_WRITE_ENTITIES returned: {result}")

    cur.execute(
        "SELECT bnf_code FROM clinical_db.core.entity WHERE document_id = %s",
        ("doc_sp_verify",),
    )
    row = cur.fetchone()
    if row is None:
        print("  [FAIL] Entity did not land in CORE.entity at all")
    else:
        stored_bnf = row[0]
        if stored_bnf == "TEST_BNF_001":
            print(f"  [OK]   bnf_code bound correctly: {stored_bnf}")
        else:
            print(f"  [FAIL] Entity landed but bnf_code is {stored_bnf!r} "
                  "(expected 'TEST_BNF_001')")
            print("         SP_WRITE_ENTITIES does not bind the field. "
                  "Partner needs to update the proc.")

    # Clean up
    cur.execute("DELETE FROM clinical_db.core.entity WHERE document_id = %s",
                ("doc_sp_verify",))
    conn.commit()

finally:
    conn.close()