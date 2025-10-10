#!/usr/bin/env python3
"""
Migrate CRS HTML content from SQLite to Cloudflare R2 Storage

This script:
1. Reads all HTML content from product_versions table
2. Uploads each HTML file to Cloudflare R2
3. Stores the blob URL back in the database
4. Shows progress with tqdm

Usage:
    # Test on 5 products
    python scripts/migrate_crs_to_blob.py --limit 5

    # Migrate all products
    python scripts/migrate_crs_to_blob.py

Environment Variables Required:
    R2_ACCESS_KEY_ID     - Cloudflare R2 Access Key ID
    R2_SECRET_ACCESS_KEY - Cloudflare R2 Secret Access Key
    R2_ACCOUNT_ID        - Cloudflare Account ID
    R2_BUCKET_NAME       - R2 Bucket Name (e.g., 'crs-content')
    R2_PUBLIC_URL        - R2 Public URL (e.g., 'https://pub-xxxxx.r2.dev')
"""

import os
import sys
import sqlite3
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import argparse
from tqdm import tqdm

# Database path
DB_PATH = 'crs_products.db'

def get_r2_client():
    """
    Create and return boto3 S3 client configured for Cloudflare R2

    Returns:
        tuple: (s3_client, bucket_name, public_url)
    """
    # Get required environment variables
    access_key = os.getenv('R2_ACCESS_KEY_ID')
    secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
    account_id = os.getenv('R2_ACCOUNT_ID')
    bucket_name = os.getenv('R2_BUCKET_NAME')
    public_url = os.getenv('R2_PUBLIC_URL')

    # Validate all required variables are present
    missing = []
    if not access_key:
        missing.append('R2_ACCESS_KEY_ID')
    if not secret_key:
        missing.append('R2_SECRET_ACCESS_KEY')
    if not account_id:
        missing.append('R2_ACCOUNT_ID')
    if not bucket_name:
        missing.append('R2_BUCKET_NAME')
    if not public_url:
        missing.append('R2_PUBLIC_URL')

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("\nTo get your R2 credentials:")
        print("1. Go to https://dash.cloudflare.com/")
        print("2. Select your account > R2")
        print("3. Create a bucket if you haven't")
        print("4. Go to 'Manage R2 API Tokens'")
        print("5. Create an API token with 'Edit' permissions")
        print("6. Enable 'Public Development URL' in bucket settings")
        print("\nThen run:")
        print("  export R2_ACCESS_KEY_ID='your-access-key'")
        print("  export R2_SECRET_ACCESS_KEY='your-secret-key'")
        print("  export R2_ACCOUNT_ID='your-account-id'")
        print("  export R2_BUCKET_NAME='your-bucket-name'")
        print("  export R2_PUBLIC_URL='https://pub-xxxxx.r2.dev'")
        print("  python scripts/migrate_crs_to_blob.py")
        sys.exit(1)

    # Remove trailing slash from public_url if present
    public_url = public_url.rstrip('/')

    # Create S3 client with R2 endpoint
    endpoint_url = f'https://{account_id}.r2.cloudflarestorage.com'

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='auto'  # R2 uses 'auto' for region
    )

    return s3_client, bucket_name, public_url


def upload_to_r2(product_id, version_number, html_content, s3_client, bucket_name, public_url):
    """
    Upload HTML content to Cloudflare R2

    Args:
        product_id: CRS product ID
        version_number: Version number
        html_content: HTML content to upload
        s3_client: boto3 S3 client configured for R2
        bucket_name: R2 bucket name
        public_url: R2 public URL base (e.g., 'https://pub-xxxxx.r2.dev')

    Returns:
        blob_url: Public URL of uploaded blob
    """
    # Construct filename - use flat structure
    filename = f"crs-{product_id}-v{version_number}.html"

    try:
        # Upload to R2 using boto3 S3 client
        s3_client.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=html_content.encode('utf-8'),
            ContentType='text/html; charset=utf-8'
        )

        # Construct public URL for R2 object
        # Format: https://pub-xxxxx.r2.dev/<filename>
        blob_url = f"{public_url}/{filename}"

        return blob_url

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print(f"\nERROR uploading {product_id}: [{error_code}] {error_msg}")
        return None
    except Exception as e:
        print(f"\nERROR uploading {product_id}: {e}")
        return None


def migrate_content(limit=None, skip_existing=True):
    """
    Migrate HTML content from database to Cloudflare R2

    Args:
        limit: Number of products to migrate (None = all)
        skip_existing: Skip products that already have blob_url
    """
    # Get R2 client and configuration
    s3_client, bucket_name, public_url = get_r2_client()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get products to migrate
    if skip_existing:
        query = """
            SELECT version_id, product_id, version_number, html_content
            FROM product_versions
            WHERE is_current = 1
              AND html_content IS NOT NULL
              AND blob_url IS NULL
        """
    else:
        query = """
            SELECT version_id, product_id, version_number, html_content
            FROM product_versions
            WHERE is_current = 1
              AND html_content IS NOT NULL
        """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    versions = cursor.fetchall()

    total = len(versions)
    if total == 0:
        print("No products to migrate!")
        conn.close()
        return

    print(f"Migrating {total} products to Cloudflare R2 ({bucket_name})...")
    print()

    # Statistics
    uploaded = 0
    failed = 0

    # Progress bar
    with tqdm(total=total, desc="Uploading", unit="file") as pbar:
        for version in versions:
            version_id = version['version_id']
            product_id = version['product_id']
            version_number = version['version_number']
            html_content = version['html_content']

            # Upload to R2
            blob_url = upload_to_r2(product_id, version_number, html_content,
                                    s3_client, bucket_name, public_url)

            if blob_url:
                # Update database with blob URL
                cursor.execute("""
                    UPDATE product_versions
                    SET blob_url = ?
                    WHERE version_id = ?
                """, (blob_url, version_id))
                conn.commit()
                uploaded += 1
            else:
                failed += 1

            pbar.update(1)

    conn.close()

    # Print summary
    print()
    print("=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"Total products: {total}")
    print(f"Uploaded successfully: {uploaded}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(uploaded/total*100):.1f}%")
    print("=" * 60)

    if failed > 0:
        print(f"\nWARNING: {failed} files failed to upload")
        print("Run the script again to retry failed uploads")
    else:
        print("\n✓ All content migrated successfully!")


def main():
    parser = argparse.ArgumentParser(description='Migrate CRS content to Cloudflare R2')
    parser.add_argument('--limit', type=int, help='Limit number of products to migrate (for testing)')
    parser.add_argument('--force', action='store_true', help='Re-upload even if blob_url exists')

    args = parser.parse_args()

    migrate_content(limit=args.limit, skip_existing=not args.force)


if __name__ == '__main__':
    main()
