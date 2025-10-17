#!/usr/bin/env python3
"""Add missing columns to document_versions table for CRS content"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# SQL to add missing columns
migration_sql = """
-- Add blob_url column for R2/S3 storage
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS blob_url TEXT;

-- Add html_url column for source URL
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS html_url VARCHAR(500);

-- Create index on blob_url for faster lookups
CREATE INDEX IF NOT EXISTS idx_document_versions_blob ON document_versions(blob_url) WHERE blob_url IS NOT NULL;

-- Update product_versions view to include new columns
CREATE OR REPLACE VIEW product_versions AS
SELECT
    version_id,
    document_id AS product_id,
    version_number,
    html_content,
    text_content,
    structure_json,
    content_hash,
    word_count,
    page_count,
    ingested_at,
    is_current,
    notes,
    blob_url,
    html_url
FROM document_versions;
"""

# Connect and execute
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute(migration_sql)
    print("✓ Migration completed successfully:")
    print("  - Added blob_url column to document_versions")
    print("  - Added html_url column to document_versions")
    print("  - Updated product_versions view")
except Exception as e:
    print(f"✗ Migration error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
