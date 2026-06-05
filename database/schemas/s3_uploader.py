"""
s3_uploader.py — clinical-intelligence
Uploads documents to S3.

Fixed signature (from API_CONTRACT.md):
    upload(file, key) -> s3_url

Called by the upload endpoint in api/routes/documents.py.
"""

import os
import boto3
from botocore.exceptions import ClientError


def _get_client():
    return boto3.client(
        "s3",
        aws_access_key_id     = os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name           = os.environ["AWS_REGION"],
    )


def upload(file: bytes, key: str) -> str:
    bucket = os.environ["S3_BUCKET"]
    client = _get_client()
    try:
        client.put_object(Bucket=bucket, Key=key, Body=file)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed for key '{key}': {e}") from e
    return f"s3://{bucket}/{key}"


def build_key(patient_id: str, document_id: str, filename: str) -> str:
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    return f"{prefix}{patient_id}/{document_id}/{filename}"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    key = build_key("pat_test", "doc_test", "test_upload.txt")
    print(f"Uploading to key: {key}")
    url = upload(b"Clinical Intelligence S3 upload test.", key)
    print(f"Success: {url}")

    client = _get_client()
    bucket = os.environ["S3_BUCKET"]
    response = client.list_objects_v2(Bucket=bucket, Prefix=key)
    if response.get("Contents"):
        print(f"Confirmed in S3: {response['Contents'][0]['Key']}")
    else:
        print("WARNING: file not found in S3 after upload")
        