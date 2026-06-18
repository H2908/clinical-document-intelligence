"""List pat_test_01's documents with S3 keys, for the Block 2.5 cleanup."""
from database.snowflake_reader import read_documents_for_patient

docs = read_documents_for_patient("pat_test_01")
print(f"{len(docs)} documents for pat_test_01\n")
for d in docs:
    print(f"  doc_id={d['document_id']}")
    print(f"    doc_type={d.get('doc_type', '?')}")
    print(f"    s3_key={d.get('s3_key', '?')}")
    print(f"    document_date={d.get('document_date', '?')}")
    print()