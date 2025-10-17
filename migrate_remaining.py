#!/usr/bin/env python3
"""Migrate remaining junction tables"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_DB = 'database.db'
POSTGRES_URL = os.getenv('POSTGRES_URL')

# Only migrate these important tables
TABLES = ['hearing_committees', 'witness_appearances', 'update_logs']

def migrate_table(s_conn, p_conn, table):
    s_cur = s_conn.cursor()
    p_cur = p_conn.cursor()

    # Get columns
    s_cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in s_cur.fetchall()]

    # Read all data
    s_cur.execute(f"SELECT * FROM {table}")
    rows = s_cur.fetchall()

    if not rows:
        print(f"{table}: 0 rows (skipping)")
        return 0

    # Prepare insert
    col_str = ', '.join(cols)
    placeholders = ', '.join(['%s'] * len(cols))
    insert_sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    # Convert booleans
    converted = []
    for row in rows:
        conv_row = []
        for j, val in enumerate(row):
            if isinstance(val, int) and any(b in cols[j] for b in ['is_', 'success']):
                conv_row.append(bool(val))
            else:
                conv_row.append(val)
        converted.append(tuple(conv_row))

    # Insert in batches of 100
    batch_size = 100
    inserted = 0
    for i in range(0, len(converted), batch_size):
        batch = converted[i:i+batch_size]
        p_cur.executemany(insert_sql, batch)
        p_conn.commit()
        inserted += len(batch)
        print(f"{table}: {inserted}/{len(converted)} rows inserted", end='\r')

    print(f"{table}: {inserted} rows ✅")
    return inserted

def main():
    print("Migrating remaining tables...")
    s_conn = sqlite3.connect(SQLITE_DB)
    p_conn = psycopg2.connect(POSTGRES_URL)

    total = 0
    for table in TABLES:
        count = migrate_table(s_conn, p_conn, table)
        total += count

    print(f"\nTotal: {total} rows migrated ✅")

    s_conn.close()
    p_conn.close()

if __name__ == '__main__':
    main()
