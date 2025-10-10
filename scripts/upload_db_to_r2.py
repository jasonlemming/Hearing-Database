#!/usr/bin/env python3
"""
Upload CRS database to Cloudflare R2 storage
"""
import boto3
import os
import sys

def upload_database():
    """Upload compressed CRS database to R2"""

    # Check if database file exists
    db_file = 'crs_products.db.gz'
    if not os.path.exists(db_file):
        print(f"Error: {db_file} not found in current directory")
        print("Please run this script from the repository root")
        sys.exit(1)

    # Get file size for progress reporting
    file_size = os.path.getsize(db_file)
    file_size_mb = file_size / (1024 * 1024)
    print(f"Database file size: {file_size_mb:.2f} MB")

    # Initialize R2 client
    print("Initializing R2 client...")
    s3_client = boto3.client(
        's3',
        endpoint_url='https://91b9e5b1082e2a907534e03c8945f60c.r2.cloudflarestorage.com',
        aws_access_key_id='3e3c4b3c1f1e889e2d2f7dcea5d3cd39',
        aws_secret_access_key='a4969fc156ba736dcc120980774056d01064a8ce968905adce64ec566c2a61bd',
        region_name='auto'
    )

    # Upload database
    bucket_name = 'crs-project'
    object_key = 'databases/crs_products.db.gz'

    print(f"Uploading {db_file} to R2...")
    print(f"Bucket: {bucket_name}")
    print(f"Key: {object_key}")

    try:
        s3_client.upload_file(
            db_file,
            bucket_name,
            object_key
        )
        print("✅ Upload complete!")

        # Verify upload by checking object metadata
        response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        uploaded_size = response['ContentLength']
        uploaded_size_mb = uploaded_size / (1024 * 1024)
        print(f"Verified upload size: {uploaded_size_mb:.2f} MB")

        if uploaded_size == file_size:
            print("✅ Size verification passed")
        else:
            print(f"⚠️  Warning: Size mismatch (local: {file_size}, remote: {uploaded_size})")

        print(f"\nDatabase available at: databases/crs_products.db.gz")

    except Exception as e:
        print(f"❌ Error during upload: {e}")
        sys.exit(1)

if __name__ == '__main__':
    upload_database()
