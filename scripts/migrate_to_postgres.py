#!/usr/bin/env python3
"""
Migrate CRS data from SQLite to PostgreSQL
Handles products, product_versions, and content_ingestion_logs tables
"""
import sqlite3
import sys
import os
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.postgres_config import get_connection


def migrate_products(sqlite_db='crs_products.db', batch_size=500):
    """Migrate products table from SQLite to PostgreSQL"""
    print("\n" + "="*70)
    print("MIGRATING PRODUCTS TABLE")
    print("="*70)

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Get total count
    sqlite_cursor.execute("SELECT COUNT(*) FROM products")
    total = sqlite_cursor.fetchone()[0]
    print(f"Total products to migrate: {total}")

    # Fetch all products
    sqlite_cursor.execute("""
        SELECT product_id, title, product_type, status, publication_date,
               summary, authors, topics, url_html, url_pdf, raw_json,
               created_at, updated_at
        FROM products
        ORDER BY product_id
    """)

    # Connect to PostgreSQL
    with get_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        migrated = 0
        batch = []

        for row in sqlite_cursor:
            # Prepare data
            data = {
                'product_id': row['product_id'],
                'title': row['title'],
                'product_type': row['product_type'],
                'status': row['status'],
                'publication_date': row['publication_date'],
                'summary': row['summary'],
                'authors': row['authors'],  # Already JSON string
                'topics': row['topics'],  # Already JSON string
                'url_html': row['url_html'],
                'url_pdf': row['url_pdf'],
                'raw_json': row['raw_json'],  # Already JSON string
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

            batch.append(data)

            # Insert batch when full
            if len(batch) >= batch_size:
                insert_product_batch(pg_cursor, batch)
                migrated += len(batch)
                print(f"  Migrated {migrated}/{total} products ({migrated/total*100:.1f}%)")
                batch = []

        # Insert remaining batch
        if batch:
            insert_product_batch(pg_cursor, batch)
            migrated += len(batch)
            print(f"  Migrated {migrated}/{total} products (100.0%)")

    sqlite_conn.close()
    print(f"✅ Products migration complete: {migrated} products")
    return migrated


def insert_product_batch(cursor, batch):
    """Insert a batch of products into PostgreSQL"""
    for product in batch:
        cursor.execute("""
            INSERT INTO products (
                product_id, title, product_type, status, publication_date,
                summary, authors, topics, url_html, url_pdf, raw_json,
                created_at, updated_at
            ) VALUES (
                %(product_id)s, %(title)s, %(product_type)s, %(status)s, %(publication_date)s,
                %(summary)s, %(authors)s::jsonb, %(topics)s::jsonb, %(url_html)s, %(url_pdf)s,
                %(raw_json)s::jsonb, %(created_at)s, %(updated_at)s
            )
            ON CONFLICT (product_id) DO UPDATE SET
                title = EXCLUDED.title,
                product_type = EXCLUDED.product_type,
                status = EXCLUDED.status,
                publication_date = EXCLUDED.publication_date,
                summary = EXCLUDED.summary,
                authors = EXCLUDED.authors,
                topics = EXCLUDED.topics,
                url_html = EXCLUDED.url_html,
                url_pdf = EXCLUDED.url_pdf,
                raw_json = EXCLUDED.raw_json,
                updated_at = EXCLUDED.updated_at
        """, product)


def migrate_product_versions(sqlite_db='crs_products.db', batch_size=500):
    """Migrate product_versions table from SQLite to PostgreSQL"""
    print("\n" + "="*70)
    print("MIGRATING PRODUCT_VERSIONS TABLE")
    print("="*70)

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Get total count
    sqlite_cursor.execute("SELECT COUNT(*) FROM product_versions")
    total = sqlite_cursor.fetchone()[0]
    print(f"Total product versions to migrate: {total}")

    # Fetch all versions
    sqlite_cursor.execute("""
        SELECT product_id, version_number, structure_json, blob_url,
               html_url, content_hash, word_count, ingested_at, is_current
        FROM product_versions
        ORDER BY product_id, version_number
    """)

    # Connect to PostgreSQL
    with get_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        migrated = 0
        batch = []

        for row in sqlite_cursor:
            data = {
                'product_id': row['product_id'],
                'version_number': row['version_number'],
                'structure_json': row['structure_json'],
                'blob_url': row['blob_url'],
                'html_url': row['html_url'],
                'content_hash': row['content_hash'],
                'word_count': row['word_count'],
                'ingested_at': row['ingested_at'],
                'is_current': bool(row['is_current']) if row['is_current'] is not None else False
            }

            batch.append(data)

            # Insert batch when full
            if len(batch) >= batch_size:
                insert_version_batch(pg_cursor, batch)
                migrated += len(batch)
                print(f"  Migrated {migrated}/{total} versions ({migrated/total*100:.1f}%)")
                batch = []

        # Insert remaining batch
        if batch:
            insert_version_batch(pg_cursor, batch)
            migrated += len(batch)
            print(f"  Migrated {migrated}/{total} versions (100.0%)")

    sqlite_conn.close()
    print(f"✅ Product versions migration complete: {migrated} versions")
    return migrated


def insert_version_batch(cursor, batch):
    """Insert a batch of product versions into PostgreSQL"""
    for version in batch:
        cursor.execute("""
            INSERT INTO product_versions (
                product_id, version_number, structure_json, blob_url,
                html_url, content_hash, word_count, ingested_at, is_current
            ) VALUES (
                %(product_id)s, %(version_number)s, %(structure_json)s::jsonb, %(blob_url)s,
                %(html_url)s, %(content_hash)s, %(word_count)s, %(ingested_at)s, %(is_current)s
            )
            ON CONFLICT (product_id, version_number) DO UPDATE SET
                structure_json = EXCLUDED.structure_json,
                blob_url = EXCLUDED.blob_url,
                html_url = EXCLUDED.html_url,
                content_hash = EXCLUDED.content_hash,
                word_count = EXCLUDED.word_count,
                ingested_at = EXCLUDED.ingested_at,
                is_current = EXCLUDED.is_current
        """, version)


def migrate_ingestion_logs(sqlite_db='crs_products.db'):
    """Migrate content_ingestion_logs table from SQLite to PostgreSQL"""
    print("\n" + "="*70)
    print("MIGRATING CONTENT_INGESTION_LOGS TABLE")
    print("="*70)

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Check if table exists
    sqlite_cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='content_ingestion_logs'
    """)
    if not sqlite_cursor.fetchone():
        print("  Table does not exist in SQLite, skipping...")
        sqlite_conn.close()
        return 0

    # Get total count
    sqlite_cursor.execute("SELECT COUNT(*) FROM content_ingestion_logs")
    total = sqlite_cursor.fetchone()[0]
    print(f"Total ingestion logs to migrate: {total}")

    if total == 0:
        sqlite_conn.close()
        return 0

    # Fetch all logs
    sqlite_cursor.execute("""
        SELECT run_type, started_at, completed_at, products_checked,
               content_fetched, content_updated, content_skipped, errors_count,
               status, error_details, total_size_bytes, avg_fetch_time_ms,
               total_duration_seconds
        FROM content_ingestion_logs
    """)

    # Connect to PostgreSQL
    with get_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        migrated = 0
        for row in sqlite_cursor:
            pg_cursor.execute("""
                INSERT INTO content_ingestion_logs (
                    run_type, started_at, completed_at, products_checked,
                    content_fetched, content_updated, content_skipped, errors_count,
                    status, error_details, total_size_bytes, avg_fetch_time_ms,
                    total_duration_seconds
                ) VALUES (
                    %(run_type)s, %(started_at)s, %(completed_at)s, %(products_checked)s,
                    %(content_fetched)s, %(content_updated)s, %(content_skipped)s, %(errors_count)s,
                    %(status)s, %(error_details)s::jsonb, %(total_size_bytes)s, %(avg_fetch_time_ms)s,
                    %(total_duration_seconds)s
                )
            """, dict(row))
            migrated += 1

        print(f"  Migrated {migrated}/{total} logs (100.0%)")

    sqlite_conn.close()
    print(f"✅ Ingestion logs migration complete: {migrated} logs")
    return migrated


def verify_migration(sqlite_db='crs_products.db'):
    """Verify migration by comparing counts"""
    print("\n" + "="*70)
    print("VERIFYING MIGRATION")
    print("="*70)

    # Get SQLite counts
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_cursor = sqlite_conn.cursor()

    sqlite_cursor.execute("SELECT COUNT(*) FROM products")
    sqlite_products = sqlite_cursor.fetchone()[0]

    sqlite_cursor.execute("SELECT COUNT(*) FROM product_versions")
    sqlite_versions = sqlite_cursor.fetchone()[0]

    sqlite_conn.close()

    # Get PostgreSQL counts
    with get_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        pg_cursor.execute("SELECT COUNT(*) FROM products")
        pg_products = pg_cursor.fetchone()[0]

        pg_cursor.execute("SELECT COUNT(*) FROM product_versions")
        pg_versions = pg_cursor.fetchone()[0]

    # Compare
    print(f"\nProducts:         SQLite: {sqlite_products:6d}  |  PostgreSQL: {pg_products:6d}  |  Match: {'✅' if sqlite_products == pg_products else '❌'}")
    print(f"Product Versions: SQLite: {sqlite_versions:6d}  |  PostgreSQL: {pg_versions:6d}  |  Match: {'✅' if sqlite_versions == pg_versions else '❌'}")

    if sqlite_products == pg_products and sqlite_versions == pg_versions:
        print("\n✅ MIGRATION VERIFIED SUCCESSFULLY!")
        return True
    else:
        print("\n❌ MIGRATION VERIFICATION FAILED - Row counts don't match")
        return False


def main():
    """Run complete migration"""
    print("\n" + "="*70)
    print("CRS DATABASE MIGRATION: SQLite → PostgreSQL")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Migrate tables
        migrate_products()
        migrate_product_versions()
        migrate_ingestion_logs()

        # Verify migration
        if verify_migration():
            print("\n" + "="*70)
            print("✅ MIGRATION COMPLETE!")
            print("="*70)
            print("\nNext steps:")
            print("1. Test locally: python3 cli.py web serve")
            print("2. Verify search functionality works")
            print("3. Deploy to Vercel with DATABASE_URL environment variable")
        else:
            print("\n❌ Migration completed with errors - please review")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
