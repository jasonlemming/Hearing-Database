#!/usr/bin/env python3
"""
Fast SQLite to PostgreSQL migration with deferred constraints
"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv
import sys

load_dotenv()

SQLITE_DB = os.getenv('DATABASE_PATH', 'database.db')
POSTGRES_URL = os.getenv('POSTGRES_URL')

# All tables in dependency order
TABLE_ORDER = [
    'committees', 'members', 'policy_areas', 'hearings', 'bills', 'witnesses', 'scheduled_tasks',
    'member_leadership_positions', 'committee_jurisdictions', 'committee_memberships',
    'hearing_committees', 'hearing_bills', 'witness_appearances', 'hearing_transcripts',
    'witness_documents', 'supporting_documents', 'sync_tracking', 'import_errors',
    'update_logs', 'schedule_execution_logs',
]

def get_columns(sqlite_cursor, table):
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in sqlite_cursor.fetchall()]

def migrate_table_fast(sqlite_conn, postgres_conn, table):
    """Fast migration with deferred constraints"""
    s_cur = sqlite_conn.cursor()
    p_cur = postgres_conn.cursor()

    cols = get_columns(s_cur, table)
    col_str = ', '.join(cols)
    placeholders = ', '.join(['%s'] * len(cols))

    # Read all rows
    s_cur.execute(f"SELECT * FROM {table}")
    rows = s_cur.fetchall()

    if not rows:
        return 0

    # Convert booleans
    converted = []
    for row in rows:
        converted_row = []
        for j, val in enumerate(row):
            if isinstance(val, int) and any(b in cols[j] for b in ['is_', 'current_member', 'success']):
                converted_row.append(bool(val))
            else:
                converted_row.append(val)
        converted.append(tuple(converted_row))

    # Batch insert
    insert_sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    p_cur.executemany(insert_sql, converted)

    # Update sequence
    id_col = cols[0]
    if id_col.endswith('_id'):
        try:
            p_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'), (SELECT MAX({id_col}) FROM {table}))")
        except:
            pass

    return len(rows)

def main():
    print("Fast PostgreSQL Migration")
    print("=" * 70)

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    postgres_conn = psycopg2.connect(POSTGRES_URL)
    p_cur = postgres_conn.cursor()

    # Defer all constraints
    print("Deferring constraints...")
    p_cur.execute("SET CONSTRAINTS ALL DEFERRED")

    print("\nMigrating tables...")
    total = 0
    for i, table in enumerate(TABLE_ORDER, 1):
        try:
            count = migrate_table_fast(sqlite_conn, postgres_conn, table)
            print(f"{i}/{len(TABLE_ORDER)} {table}: {count:,} rows")
            total += count
        except Exception as e:
            print(f"{i}/{len(TABLE_ORDER)} {table}: FAILED - {e}")

    postgres_conn.commit()

    print("\n" + "=" * 70)
    print(f"Total rows migrated: {total:,}")
    print("✅ Migration complete!")

    sqlite_conn.close()
    postgres_conn.close()

if __name__ == '__main__':
    main()
