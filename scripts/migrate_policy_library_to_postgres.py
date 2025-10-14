#!/usr/bin/env python3
"""
Migrate Policy Library from SQLite to PostgreSQL on Neon

This script migrates data from the compressed SQLite database (brookings_products.db.gz)
to the PostgreSQL database specified by BROOKINGS_DATABASE_URL environment variable.

Usage:
    export BROOKINGS_DATABASE_URL='postgresql://user:pass@host/db'
    python scripts/migrate_policy_library_to_postgres.py
"""
import os
import sys
import gzip
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import sqlite3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class PolicyLibraryMigration:
    def __init__(self, sqlite_gz_path, postgres_url):
        self.sqlite_gz_path = sqlite_gz_path
        self.postgres_url = postgres_url
        self.sqlite_path = None
        self.stats = {
            'sources': 0,
            'organizations': 0,
            'authors': 0,
            'subjects': 0,
            'documents': 0,
            'document_authors': 0,
            'document_subjects': 0,
            'document_versions': 0,
            'document_files': 0,
            'ingestion_logs': 0,
            'ingestion_errors': 0
        }

    def decompress_sqlite(self):
        """Decompress SQLite database to temporary file"""
        print("📦 Decompressing SQLite database...")
        temp_dir = tempfile.mkdtemp()
        self.sqlite_path = os.path.join(temp_dir, 'brookings_products.db')

        with gzip.open(self.sqlite_gz_path, 'rb') as f_in:
            with open(self.sqlite_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        print(f"✅ Decompressed to: {self.sqlite_path}")
        return self.sqlite_path

    def apply_schema(self, pg_conn):
        """Apply PostgreSQL schema"""
        print("\n🏗️  Applying PostgreSQL schema...")

        # Check if tables already exist
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'documents'")
            table_exists = cur.fetchone()[0] > 0

        if table_exists:
            print("⚠️  Schema already exists, skipping schema application")
            print("   (Tables will be truncated before data migration)")
            return

        schema_path = Path(__file__).parent.parent / 'database' / 'migrations' / 'policy_library_001_initial_schema.sql'

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        with pg_conn.cursor() as cur:
            cur.execute(schema_sql)
            pg_conn.commit()

        print("✅ Schema applied successfully")

    def convert_row(self, row, boolean_cols=None):
        """Convert SQLite data types to PostgreSQL compatible types"""
        if not boolean_cols:
            return row

        converted = list(row)
        for idx in boolean_cols:
            if converted[idx] is not None:
                # Convert SQLite integer (0/1) to Python bool
                converted[idx] = bool(converted[idx])
        return tuple(converted)

    def migrate_table(self, sqlite_conn, pg_conn, table_name, columns, order_by=None, boolean_cols=None):
        """Generic table migration"""
        print(f"  Migrating {table_name}...", end=' ')

        # Read from SQLite
        sqlite_cur = sqlite_conn.cursor()
        query = f"SELECT {', '.join(columns)} FROM {table_name}"
        if order_by:
            query += f" ORDER BY {order_by}"
        sqlite_cur.execute(query)
        rows = sqlite_cur.fetchall()

        if not rows:
            print("⚠️  No data")
            return

        # Convert data types if needed
        if boolean_cols:
            rows = [self.convert_row(row, boolean_cols) for row in rows]

        # Write to PostgreSQL using execute_values with template
        pg_cur = pg_conn.cursor()
        cols_str = ', '.join(columns)
        # Use template parameter instead of building query with %s
        execute_values(
            pg_cur,
            f"INSERT INTO {table_name} ({cols_str}) VALUES %s",
            rows,
            template=f"({', '.join(['%s'] * len(columns))})",
            page_size=100
        )
        pg_conn.commit()

        self.stats[table_name] = len(rows)
        print(f"✅ {len(rows)} rows")

    def migrate_sources(self, sqlite_conn, pg_conn):
        """Migrate sources table"""
        # First, truncate to avoid conflicts (preserves table structure)
        pg_cur = pg_conn.cursor()
        pg_cur.execute("TRUNCATE TABLE sources CASCADE")
        pg_conn.commit()

        self.migrate_table(
            sqlite_conn, pg_conn, 'sources',
            ['source_id', 'source_code', 'name', 'short_name', 'description', 'url', 'is_active', 'created_at'],
            order_by='source_id',
            boolean_cols=[6]  # is_active is at index 6
        )

    def migrate_organizations(self, sqlite_conn, pg_conn):
        """Migrate organizations table"""
        # Truncate to avoid conflicts
        pg_cur = pg_conn.cursor()
        pg_cur.execute("TRUNCATE TABLE organizations CASCADE")
        pg_conn.commit()

        self.migrate_table(
            sqlite_conn, pg_conn, 'organizations',
            ['organization_id', 'name', 'short_name', 'organization_type', 'url', 'created_at'],
            order_by='organization_id'
        )

    def migrate_authors(self, sqlite_conn, pg_conn):
        """Migrate authors table"""
        # Truncate to avoid conflicts
        pg_cur = pg_conn.cursor()
        pg_cur.execute("TRUNCATE TABLE authors CASCADE")
        pg_conn.commit()

        self.migrate_table(
            sqlite_conn, pg_conn, 'authors',
            ['author_id', 'full_name', 'first_name', 'last_name', 'organization_id', 'email', 'orcid', 'bio', 'created_at'],
            order_by='author_id'
        )

    def migrate_subjects(self, sqlite_conn, pg_conn):
        """Migrate subjects table"""
        # Truncate to avoid conflicts
        pg_cur = pg_conn.cursor()
        pg_cur.execute("TRUNCATE TABLE subjects CASCADE")
        pg_conn.commit()

        self.migrate_table(
            sqlite_conn, pg_conn, 'subjects',
            ['subject_id', 'name', 'parent_subject_id', 'description', 'source_vocabulary', 'created_at'],
            order_by='subject_id'
        )

    def migrate_documents(self, sqlite_conn, pg_conn):
        """Migrate documents table"""
        self.migrate_table(
            sqlite_conn, pg_conn, 'documents',
            ['document_id', 'source_id', 'document_identifier', 'title', 'document_type', 'status',
             'publication_date', 'summary', 'full_text', 'url', 'pdf_url', 'page_count', 'word_count',
             'checksum', 'metadata_json', 'created_at', 'updated_at'],
            order_by='document_id'
        )

    def migrate_document_authors(self, sqlite_conn, pg_conn):
        """Migrate document_authors junction table"""
        self.migrate_table(
            sqlite_conn, pg_conn, 'document_authors',
            ['document_id', 'author_id', 'author_order', 'role'],
            order_by='document_id, author_id'
        )

    def migrate_document_subjects(self, sqlite_conn, pg_conn):
        """Migrate document_subjects junction table"""
        self.migrate_table(
            sqlite_conn, pg_conn, 'document_subjects',
            ['document_id', 'subject_id', 'relevance_score'],
            order_by='document_id, subject_id'
        )

    def migrate_document_versions(self, sqlite_conn, pg_conn):
        """Migrate document_versions table"""
        # Check if table exists and has data
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT COUNT(*) FROM document_versions")
        count = sqlite_cur.fetchone()[0]

        if count == 0:
            print("  Migrating document_versions... ⚠️  No data")
            return

        self.migrate_table(
            sqlite_conn, pg_conn, 'document_versions',
            ['version_id', 'document_id', 'version_number', 'html_content', 'text_content',
             'structure_json', 'content_hash', 'word_count', 'page_count', 'ingested_at',
             'is_current', 'notes'],
            order_by='version_id',
            boolean_cols=[10]  # is_current is at index 10
        )

    def migrate_document_files(self, sqlite_conn, pg_conn):
        """Migrate document_files table"""
        # Check if table exists and has data
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT COUNT(*) FROM document_files")
        count = sqlite_cur.fetchone()[0]

        if count == 0:
            print("  Migrating document_files... ⚠️  No data")
            return

        self.migrate_table(
            sqlite_conn, pg_conn, 'document_files',
            ['file_id', 'document_id', 'file_type', 'file_path', 'file_size',
             'mime_type', 'checksum', 'downloaded_at'],
            order_by='file_id'
        )

    def migrate_ingestion_logs(self, sqlite_conn, pg_conn):
        """Migrate ingestion_logs table"""
        # Check if table exists and has data
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT COUNT(*) FROM ingestion_logs")
        count = sqlite_cur.fetchone()[0]

        if count == 0:
            print("  Migrating ingestion_logs... ⚠️  No data")
            return

        self.migrate_table(
            sqlite_conn, pg_conn, 'ingestion_logs',
            ['log_id', 'source_id', 'run_type', 'started_at', 'completed_at',
             'documents_checked', 'documents_fetched', 'documents_updated',
             'documents_skipped', 'errors_count', 'status', 'error_details',
             'total_size_bytes', 'avg_fetch_time_ms', 'total_duration_seconds'],
            order_by='log_id'
        )

    def migrate_ingestion_errors(self, sqlite_conn, pg_conn):
        """Migrate ingestion_errors table"""
        # Check if table exists and has data
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT COUNT(*) FROM ingestion_errors")
        count = sqlite_cur.fetchone()[0]

        if count == 0:
            print("  Migrating ingestion_errors... ⚠️  No data")
            return

        self.migrate_table(
            sqlite_conn, pg_conn, 'ingestion_errors',
            ['error_id', 'log_id', 'document_identifier', 'url', 'error_type',
             'error_message', 'stack_trace', 'retry_count', 'created_at'],
            order_by='error_id'
        )

    def reset_sequences(self, pg_conn):
        """Reset PostgreSQL sequences to max ID values"""
        print("\n🔢 Resetting PostgreSQL sequences...")

        sequences = [
            ('sources', 'source_id'),
            ('organizations', 'organization_id'),
            ('authors', 'author_id'),
            ('subjects', 'subject_id'),
            ('documents', 'document_id'),
            ('document_versions', 'version_id'),
            ('document_files', 'file_id'),
            ('ingestion_logs', 'log_id'),
            ('ingestion_errors', 'error_id')
        ]

        pg_cur = pg_conn.cursor()
        for table, id_col in sequences:
            pg_cur.execute(f"SELECT MAX({id_col}) FROM {table}")
            max_id = pg_cur.fetchone()[0]
            if max_id:
                pg_cur.execute(f"SELECT setval('{table}_{id_col}_seq', {max_id})")
                print(f"  {table}: Set sequence to {max_id}")

        pg_conn.commit()
        print("✅ Sequences reset")

    def validate_migration(self, sqlite_conn, pg_conn):
        """Validate row counts match"""
        print("\n🔍 Validating migration...")

        all_valid = True
        tables = [
            'sources', 'organizations', 'authors', 'subjects', 'documents',
            'document_authors', 'document_subjects', 'document_versions',
            'document_files', 'ingestion_logs', 'ingestion_errors'
        ]

        for table in tables:
            # SQLite count
            sqlite_cur = sqlite_conn.cursor()
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]

            # PostgreSQL count
            pg_cur = pg_conn.cursor()
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()[0]

            if sqlite_count == pg_count:
                print(f"  ✅ {table}: {pg_count} rows")
            else:
                print(f"  ❌ {table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
                all_valid = False

        return all_valid

    def run(self):
        """Execute full migration"""
        start_time = datetime.now()
        print("=" * 70)
        print("🚀 Policy Library Migration: SQLite → PostgreSQL")
        print("=" * 70)

        try:
            # Decompress SQLite
            self.decompress_sqlite()

            # Connect to databases
            print("\n🔌 Connecting to databases...")
            sqlite_conn = sqlite3.connect(self.sqlite_path)
            pg_conn = psycopg2.connect(self.postgres_url)
            print("✅ Connected")

            # Apply schema
            self.apply_schema(pg_conn)

            # Migrate data in order (respecting foreign keys)
            print("\n📊 Migrating data...")
            self.migrate_sources(sqlite_conn, pg_conn)
            self.migrate_organizations(sqlite_conn, pg_conn)
            self.migrate_authors(sqlite_conn, pg_conn)
            self.migrate_subjects(sqlite_conn, pg_conn)
            self.migrate_documents(sqlite_conn, pg_conn)
            self.migrate_document_authors(sqlite_conn, pg_conn)
            self.migrate_document_subjects(sqlite_conn, pg_conn)
            self.migrate_document_versions(sqlite_conn, pg_conn)
            self.migrate_document_files(sqlite_conn, pg_conn)
            self.migrate_ingestion_logs(sqlite_conn, pg_conn)
            self.migrate_ingestion_errors(sqlite_conn, pg_conn)

            # Reset sequences
            self.reset_sequences(pg_conn)

            # Validate
            validation_passed = self.validate_migration(sqlite_conn, pg_conn)

            # Clean up
            sqlite_conn.close()
            pg_conn.close()

            # Summary
            duration = (datetime.now() - start_time).total_seconds()
            print("\n" + "=" * 70)
            print("📈 Migration Summary")
            print("=" * 70)
            for table, count in self.stats.items():
                if count > 0:
                    print(f"  {table}: {count:,} rows")
            print(f"\n⏱️  Duration: {duration:.2f} seconds")

            if validation_passed:
                print("\n✅ Migration completed successfully!")
                print("\n🎯 Next steps:")
                print("  1. Set BROOKINGS_DATABASE_URL in Vercel environment variables")
                print("  2. Update application code to use PostgreSQL")
                print("  3. Test the policy library in production")
                return 0
            else:
                print("\n❌ Migration validation failed! Please check the errors above.")
                return 1

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            # Clean up temp file
            if self.sqlite_path and os.path.exists(self.sqlite_path):
                os.remove(self.sqlite_path)
                print(f"\n🧹 Cleaned up temporary file: {self.sqlite_path}")


def main():
    """Main entry point"""
    # Get PostgreSQL URL from environment
    postgres_url = os.environ.get('BROOKINGS_DATABASE_URL')
    if not postgres_url:
        print("❌ Error: BROOKINGS_DATABASE_URL environment variable not set")
        print("\nUsage:")
        print("  export BROOKINGS_DATABASE_URL='postgresql://user:pass@host/db'")
        print("  python scripts/migrate_policy_library_to_postgres.py")
        return 1

    # Find SQLite database
    sqlite_gz_path = 'brookings_products.db.gz'
    if not os.path.exists(sqlite_gz_path):
        print(f"❌ Error: SQLite database not found: {sqlite_gz_path}")
        return 1

    # Run migration
    migration = PolicyLibraryMigration(sqlite_gz_path, postgres_url)
    return migration.run()


if __name__ == '__main__':
    sys.exit(main())
