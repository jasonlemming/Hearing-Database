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
        db_gz_path = '/tmp/crs_products.db.gz'
        db_path = '/tmp/crs_products.db'
    else:
        # Local development - use repo root
        db_gz_path = 'crs_products.db.gz'
        db_path = 'crs_products.db'

    # If decompressed database already exists, return it
    if os.path.exists(db_path):
        print(f"Using existing database at {db_path}")
        return db_path

    # If compressed database exists locally, decompress it
    if os.path.exists(db_gz_path):
        print(f"Decompressing local {db_gz_path} to {db_path}...")
        _decompress_database(db_gz_path, db_path)
        return db_path

    # Need to download from R2
    print(f"Downloading database from R2 to {db_gz_path}...")
    _download_from_r2(db_gz_path)

    # Decompress the downloaded file
    print(f"Decompressing {db_gz_path} to {db_path}...")
    _decompress_database(db_gz_path, db_path)

    # Clean up compressed file to save space (especially on Vercel)
    if os.environ.get('VERCEL'):
        try:
            os.remove(db_gz_path)
            print(f"Cleaned up compressed file {db_gz_path}")
        except Exception as e:
            print(f"Warning: Could not remove compressed file: {e}")

    return db_path


def _download_from_r2(target_path):
    """Download compressed database from R2"""
    try:
        s3_client = get_r2_client()
        bucket_name = os.environ.get('R2_BUCKET_NAME', 'crs-project')
        object_key = 'databases/crs_products.db.gz'

        # Ensure directory exists
        os.makedirs(os.path.dirname(target_path) or '.', exist_ok=True)

        # Download file
        s3_client.download_file(bucket_name, object_key, target_path)

        # Verify download
        file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
        print(f"✅ Downloaded database: {file_size_mb:.2f} MB")

    except Exception as e:
        raise Exception(f"Failed to download database from R2: {e}")


def _decompress_database(gz_path, output_path):
    """Decompress gzipped database file"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        with gzip.open(gz_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Decompressed database: {file_size_mb:.2f} MB")

    except Exception as e:
        # Clean up partial file on error
        if os.path.exists(output_path):
            os.remove(output_path)
        raise Exception(f"Failed to decompress database: {e}")


if __name__ == '__main__':
    # Test the download and decompression
    db_path = get_database_path()
    print(f"\nDatabase ready at: {db_path}")
