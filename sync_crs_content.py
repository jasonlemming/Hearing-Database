#!/usr/bin/env python3
"""
Sync CRS HTML content from CRS database to Policy Library

This syncs the full HTML content stored in product_versions (with R2 blob URLs)
to the Policy Library's document_versions table.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()

def sync_crs_content_batch(batch_size=100):
    """Sync CRS HTML content in batches"""

    crs_url = os.getenv('CRS_DATABASE_URL')
    policy_url = os.getenv('DATABASE_URL')

    # Connect to both databases
    crs_conn = psycopg2.connect(crs_url, cursor_factory=RealDictCursor)
    policy_conn = psycopg2.connect(policy_url)
    policy_conn.autocommit = False

    crs_cur = crs_conn.cursor()
    policy_cur = policy_conn.cursor()

    # Get CRS source_id from Policy Library
    policy_cur.execute("SELECT source_id FROM sources WHERE source_code = 'CRS'")
    source_row = policy_cur.fetchone()
    if not source_row:
        print("Error: CRS source not found in Policy Library")
        return
    crs_source_id = source_row[0]

    # Get all current versions from CRS database with HTML content
    crs_cur.execute("""
        SELECT pv.product_id, pv.version_number, pv.word_count,
               pv.blob_url, pv.structure_json, pv.content_hash,
               pv.html_url, pv.ingested_at
        FROM product_versions pv
        WHERE pv.is_current = TRUE AND pv.blob_url IS NOT NULL
        ORDER BY pv.product_id
    """)

    versions = crs_cur.fetchall()
    total = len(versions)
    print(f"Found {total} CRS product versions with HTML content to sync\n")

    synced = 0
    skipped = 0
    errors = 0

    for i, version in enumerate(versions, 1):
        product_id = version['product_id']

        try:
            # Get the document_id from Policy Library for this product
            policy_cur.execute("""
                SELECT document_id, word_count
                FROM documents
                WHERE source_id = %s AND document_identifier = %s
            """, (crs_source_id, product_id))

            doc_row = policy_cur.fetchone()
            if not doc_row:
                skipped += 1
                if i % 100 == 0:
                    print(f"[{i}/{total}] Skipped {product_id} (not in Policy Library)")
                continue

            document_id, current_word_count = doc_row

            # Update the document with word count if not set
            if not current_word_count and version['word_count']:
                policy_cur.execute("""
                    UPDATE documents
                    SET word_count = %s
                    WHERE document_id = %s
                """, (version['word_count'], document_id))

            # Check if version already exists
            policy_cur.execute("""
                SELECT version_id FROM document_versions
                WHERE document_id = %s AND version_number = %s
            """, (document_id, version['version_number']))

            existing = policy_cur.fetchone()

            # Prepare structure JSON
            structure_json_str = json.dumps(version['structure_json']) if version['structure_json'] else None

            if existing:
                # Update existing version
                policy_cur.execute("""
                    UPDATE document_versions
                    SET structure_json = %s,
                        content_hash = %s,
                        word_count = %s,
                        is_current = TRUE
                    WHERE version_id = %s
                """, (structure_json_str, version['content_hash'],
                      version['word_count'], existing[0]))
            else:
                # Create new version with reference to R2 blob URL
                # Store blob_url in structure_json for now
                structure_data = version['structure_json'] or {}
                structure_data['blob_url'] = version['blob_url']
                structure_data['html_url'] = version['html_url']
                structure_json_str = json.dumps(structure_data)

                policy_cur.execute("""
                    INSERT INTO document_versions
                    (document_id, version_number, structure_json, content_hash,
                     word_count, is_current, ingested_at)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                """, (document_id, version['version_number'], structure_json_str,
                      version['content_hash'], version['word_count'],
                      datetime.now()))

            policy_conn.commit()
            synced += 1

            if i % 100 == 0:
                print(f"[{i}/{total}] Synced: {synced}, Skipped: {skipped}, Errors: {errors}")

        except Exception as e:
            policy_conn.rollback()
            errors += 1
            print(f"Error syncing {product_id}: {e}")
            continue

    crs_cur.close()
    policy_cur.close()
    crs_conn.close()
    policy_conn.close()

    print(f"\n✓ Content sync complete!")
    print(f"  Total versions: {total}")
    print(f"  Synced: {synced}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

if __name__ == '__main__':
    sync_crs_content_batch()
