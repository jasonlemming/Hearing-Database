"""
R2 Database Manager - Download and cache CRS database from R2 storage
"""
import boto3
import os
import gzip
import shutil
from pathlib import Path


def get_r2_client():
    """Initialize R2 client with credentials from environment or hardcoded defaults"""
    return boto3.client(
        's3',
        endpoint_url=f'https://{os.environ.get("R2_ACCOUNT_ID", "91b9e5b1082e2a907534e03c8945f60c")}.r2.cloudflarestorage.com',
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID', '3e3c4b3c1f1e889e2d2f7dcea5d3cd39'),
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY', 'a4969fc156ba736dcc120980774056d01064a8ce968905adce64ec566c2a61bd'),
        region_name='auto'
    )


def get_database_path():
    """
    Get or download the CRS database from R2 storage

    Returns:
        str: Path to the decompressed database file
    """
    # Determine paths based on environment
    if os.environ.get('VERCEL'):
        # On Vercel, use /tmp directory (writable)
        db_path = '/tmp/crs_products.db'
    else:
        # Local development - use repo root
        db_path = 'crs_products.db'

    # If decompressed database already exists, return it
    if os.path.exists(db_path):
        print(f"Using existing database at {db_path}")
        return db_path

    # Download and decompress directly from R2 (streaming to save space)
    print(f"Downloading and decompressing database from R2 to {db_path}...")
    _download_and_decompress_from_r2(db_path)

    return db_path


def _download_and_decompress_from_r2(output_path):
    """
    Download and decompress database from R2 in a streaming fashion.
    This avoids needing space for both compressed and uncompressed files.
    """
    try:
        s3_client = get_r2_client()
        bucket_name = os.environ.get('R2_BUCKET_NAME', 'crs-project')
        object_key = 'databases/crs_products.db.gz'

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        # Stream download and decompress on-the-fly
        print(f"Streaming download from R2...")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)

        # Decompress streaming data directly to output file
        with gzip.GzipFile(fileobj=response['Body']) as gz_stream:
            with open(output_path, 'wb') as f_out:
                # Copy in chunks to avoid memory issues
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = gz_stream.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        # Verify decompression
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Database ready: {file_size_mb:.2f} MB")

    except Exception as e:
        # Clean up partial file on error
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        raise Exception(f"Failed to download and decompress database: {e}")


if __name__ == '__main__':
    # Test the download and decompression
    db_path = get_database_path()
    print(f"\nDatabase ready at: {db_path}")
