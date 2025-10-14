#!/usr/bin/env python3
"""
Complete the PostgreSQL migration - migrate remaining tables with progress tracking
"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv
import sys
import time

load_dotenv()

SQLITE_DB = 'database.db'
POSTGRES_URL = os.getenv('POSTGRES_URL')

# Remaining tables to migrate in order
TABLES_TO_MIGRATE = [
    'hearing_committees',      # 1340 rows (500 already done = 840 remaining)
    'witness_appearances',      # 2425 rows
    'update_logs',             # 29 rows
    'committee_memberships',   # Unknown
    'hearing_bills',           # Unknown
    'hearing_transcripts',     # Unknown
    'witness_documents',       # Unknown
    'supporting_documents',    # Unknown
]

def get_columns(sqlite_cursor, table):
    """Get column names from SQLite"""
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in sqlite_cursor.fetchall()]

def get_existing_count(postgres_cursor, table):
    """Get current row count in PostgreSQL"""
    try:
        postgres_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return postgres_cursor.fetchone()[0]
    except:
        return 0

def migrate_table_incremental(sqlite_conn, postgres_conn, table, start_row=0):
    """
    Migrate a table incrementally with small batches and progress updates

    Args:
        start_row: Skip this many rows (for resuming partial migrations)
    """
    s_cur = sqlite_conn.cursor()
    p_cur = postgres_conn.cursor()

    # Get columns
    cols = get_columns(s_cur, table)
    col_str = ', '.join(cols)
    placeholders = ', '.join(['%s'] * len(cols))

    # Count total rows needed
    s_cur.execute(f"SELECT COUNT(*) FROM {table}")
    total_rows = s_cur.fetchone()[0]

    if total_rows == 0:
        print(f"{table}: No data to migrate")
        return 0

    # Check existing rows
    existing = get_existing_count(p_cur, table)
    if existing > 0:
        print(f"{table}: {existing} rows already exist")

    if existing >= total_rows:
        print(f"{table}: ✅ Already complete ({existing}/{total_rows})")
        return 0

    print(f"{table}: Migrating {total_rows - existing} rows...")

    # Read all data
    s_cur.execute(f"SELECT * FROM {table}")
    all_rows = s_cur.fetchall()

    # Skip already migrated rows
    rows_to_migrate = all_rows[existing:]

    # Prepare insert statement with ON CONFLICT
    insert_sql = f"""
        INSERT INTO {table} ({col_str})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    # Migrate in very small batches with frequent commits
    batch_size = 50  # Small batches to avoid timeouts
    inserted = 0
    failed = 0

    for i in range(0, len(rows_to_migrate), batch_size):
        batch = rows_to_migrate[i:i+batch_size]

        # Convert booleans for this batch
        converted_batch = []
        for row in batch:
            conv_row = []
            for j, val in enumerate(row):
                col_name = cols[j]
                # Convert SQLite integers to PostgreSQL booleans
                if isinstance(val, int) and any(b in col_name for b in
                    ['is_', 'current_member', 'success', '_active']):
                    conv_row.append(bool(val))
                else:
                    conv_row.append(val)
            converted_batch.append(tuple(conv_row))

        # Try batch insert
        try:
            p_cur.executemany(insert_sql, converted_batch)
            postgres_conn.commit()
            inserted += len(batch)

            # Progress update
            progress = existing + inserted
            percent = (progress / total_rows) * 100
            print(f"  {table}: {progress}/{total_rows} ({percent:.1f}%) - batch #{(i//batch_size)+1}", flush=True)

        except Exception as e:
            # If batch fails, try one by one
            print(f"  Batch failed: {e}, trying individually...")
            for row in converted_batch:
                try:
                    p_cur.execute(insert_sql, row)
                    postgres_conn.commit()
                    inserted += 1
                except Exception as row_error:
                    # Skip duplicates silently
                    if "duplicate" not in str(row_error).lower() and "unique" not in str(row_error).lower():
                        failed += 1
                        if failed < 5:  # Only print first few errors
                            print(f"    Row error: {row_error}")

        # Brief pause between batches to avoid overwhelming the connection
        time.sleep(0.1)

    final_count = get_existing_count(p_cur, table)
    print(f"  {table}: ✅ Complete - {final_count} total rows (inserted {inserted}, failed {failed})")
    return inserted

def main():
    """Main migration completion function"""
    print("=" * 80)
    print("COMPLETING POSTGRESQL MIGRATION")
    print("=" * 80)
    print()

    # Connect to databases
    print("Connecting to databases...")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        postgres_conn = psycopg2.connect(POSTGRES_URL)
        print("✅ Connected\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Migrate each table
    total_migrated = 0
    start_time = time.time()

    for i, table in enumerate(TABLES_TO_MIGRATE, 1):
        print(f"\n[{i}/{len(TABLES_TO_MIGRATE)}] Processing {table}...")
        print("-" * 80)

        try:
            count = migrate_table_incremental(sqlite_conn, postgres_conn, table)
            total_migrated += count
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Final summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total rows migrated: {total_migrated:,}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print()

    # Verify all tables
    print("Final table counts:")
    p_cur = postgres_conn.cursor()

    all_tables = [
        'committees', 'members', 'hearings', 'witnesses', 'bills',
        'hearing_committees', 'witness_appearances', 'update_logs',
        'committee_memberships', 'hearing_bills'
    ]

    for table in all_tables:
        try:
            p_cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = p_cur.fetchone()[0]
            status = "✅" if count > 0 else "⚠️ "
            print(f"  {status} {table}: {count:,} rows")
        except Exception as e:
            print(f"  ❌ {table}: Error - {e}")

    sqlite_conn.close()
    postgres_conn.close()

    print()
    print("=" * 80)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 80)

if __name__ == '__main__':
    main()
