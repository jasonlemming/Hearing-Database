#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL (Neon)
"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv
from typing import List, Tuple
import sys

load_dotenv()

# Connection strings
SQLITE_DB = os.getenv('DATABASE_PATH', 'database.db')
POSTGRES_URL = os.getenv('POSTGRES_URL')

# Table migration order (respects foreign key dependencies)
TABLE_ORDER = [
    # Independent tables (no dependencies)
    'committees',
    'members',
    'policy_areas',
    'hearings',
    'bills',
    'witnesses',
    'scheduled_tasks',

    # Dependent tables (have foreign keys)
    'member_leadership_positions',
    'committee_jurisdictions',
    'committee_memberships',
    'hearing_committees',
    'hearing_bills',
    'witness_appearances',
    'hearing_transcripts',
    'witness_documents',
    'supporting_documents',
    'sync_tracking',
    'import_errors',
    'update_logs',
    'schedule_execution_logs',
]


def get_table_columns(sqlite_cursor, table_name: str) -> List[str]:
    """Get column names for a table from SQLite"""
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in sqlite_cursor.fetchall()]
    return columns


def migrate_table(sqlite_conn, postgres_conn, table_name: str) -> Tuple[int, int]:
    """
    Migrate all data from SQLite table to PostgreSQL table

    Returns:
        Tuple of (rows_read, rows_inserted)
    """
    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    # Get column names
    columns = get_table_columns(sqlite_cursor, table_name)

    # Skip auto-increment ID columns for PostgreSQL SERIAL
    if columns[0].endswith('_id'):
        # For tables with SERIAL primary keys, we need to handle differently
        id_column = columns[0]
        data_columns = columns[1:]  # Skip the ID column
    else:
        id_column = None
        data_columns = columns

    # Special handling for committees table (self-referential foreign key)
    if table_name == 'committees':
        # Order by parent_committee_id so parents are inserted first
        sqlite_cursor.execute(f"SELECT * FROM {table_name} ORDER BY CASE WHEN parent_committee_id IS NULL THEN 0 ELSE 1 END, committee_id")
        rows = sqlite_cursor.fetchall()
    else:
        # Read all data from SQLite
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"  ⚠️  {table_name}: No data to migrate")
        return 0, 0

    # Prepare INSERT statement for PostgreSQL
    if id_column:
        # Include ID column in insert to preserve IDs
        all_columns = columns
        placeholders = ', '.join(['%s'] * len(all_columns))
        column_names = ', '.join(all_columns)

        insert_sql = f"""
            INSERT INTO {table_name} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """
    else:
        # No ID column (junction tables)
        placeholders = ', '.join(['%s'] * len(data_columns))
        column_names = ', '.join(data_columns)

        insert_sql = f"""
            INSERT INTO {table_name} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """

    # For tables with self-referential FKs, disable FK checks temporarily
    if table_name == 'committees':
        postgres_cursor.execute("SET CONSTRAINTS ALL DEFERRED")

    # Insert data - for committees, insert one at a time to handle dependencies
    batch_size = 1 if table_name == 'committees' else 1000
    rows_inserted = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]

        # Convert boolean values (SQLite uses 0/1, PostgreSQL uses true/false)
        converted_batch = []
        for row in batch:
            converted_row = []
            for j, value in enumerate(row):
                column_name = columns[j]
                # Convert boolean fields
                if isinstance(value, int) and any(bool_col in column_name for bool_col in
                    ['is_', 'current_member', 'success']):
                    converted_row.append(bool(value))
                else:
                    converted_row.append(value)
            converted_batch.append(tuple(converted_row))

        try:
            if batch_size == 1:
                # Insert one by one for committees
                for row in converted_batch:
                    try:
                        postgres_cursor.execute(insert_sql, row)
                        rows_inserted += 1
                    except Exception as row_error:
                        # Skip duplicates silently
                        if "duplicate key" not in str(row_error).lower():
                            print(f"    ⚠️  Skipping row: {row_error}")
            else:
                postgres_cursor.executemany(insert_sql, converted_batch)
                rows_inserted += len(batch)
        except Exception as e:
            print(f"    ⚠️  Error inserting batch: {e}")
            # Try inserting one by one to identify problematic rows
            for row in converted_batch:
                try:
                    postgres_cursor.execute(insert_sql, row)
                    rows_inserted += 1
                except Exception as row_error:
                    if "duplicate key" not in str(row_error).lower():
                        print(f"    ❌ Failed to insert row: {row_error}")
                    continue

    postgres_conn.commit()

    # Update sequence for SERIAL columns
    if id_column:
        try:
            postgres_cursor.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{id_column}'),
                    (SELECT MAX({id_column}) FROM {table_name})
                )
            """)
            postgres_conn.commit()
        except Exception as e:
            print(f"    ⚠️  Could not update sequence: {e}")

    return len(rows), rows_inserted


def verify_migration(sqlite_conn, postgres_conn, table_name: str) -> bool:
    """Verify row counts match between SQLite and PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    sqlite_count = sqlite_cursor.fetchone()[0]

    postgres_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    postgres_count = postgres_cursor.fetchone()[0]

    return sqlite_count == postgres_count


def main():
    """Main migration function"""
    print("=" * 70)
    print("SQLite to PostgreSQL Migration")
    print("=" * 70)
    print(f"Source: {SQLITE_DB}")
    print(f"Target: Neon PostgreSQL")
    print()

    # Connect to both databases
    print("Connecting to databases...")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        postgres_conn = psycopg2.connect(POSTGRES_URL)
        print("✅ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    print()
    print("Starting data migration...")
    print("-" * 70)

    total_rows_read = 0
    total_rows_inserted = 0
    failed_tables = []

    for i, table_name in enumerate(TABLE_ORDER, 1):
        print(f"{i}/{len(TABLE_ORDER)} Migrating {table_name}...", end=" ")

        try:
            rows_read, rows_inserted = migrate_table(sqlite_conn, postgres_conn, table_name)
            total_rows_read += rows_read
            total_rows_inserted += rows_inserted

            # Verify migration
            if verify_migration(sqlite_conn, postgres_conn, table_name):
                print(f"✅ {rows_inserted:,} rows")
            else:
                print(f"⚠️  Row count mismatch!")
                failed_tables.append(table_name)

        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed_tables.append(table_name)
            continue

    print("-" * 70)
    print()
    print("Migration Summary:")
    print(f"  Total rows read:     {total_rows_read:,}")
    print(f"  Total rows inserted: {total_rows_inserted:,}")
    print(f"  Success rate:        {(total_rows_inserted/total_rows_read*100) if total_rows_read > 0 else 0:.1f}%")

    if failed_tables:
        print()
        print(f"⚠️  Failed tables ({len(failed_tables)}):")
        for table in failed_tables:
            print(f"    - {table}")
    else:
        print()
        print("✅ All tables migrated successfully!")

    # Close connections
    sqlite_conn.close()
    postgres_conn.close()

    print()
    print("=" * 70)
    print("Migration complete!")
    print("=" * 70)

    return 0 if not failed_tables else 1


if __name__ == '__main__':
    sys.exit(main())
