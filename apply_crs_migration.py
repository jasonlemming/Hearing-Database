#!/usr/bin/env python3
"""Apply CRS PostgreSQL schema migration"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Read migration file
with open('database/migrations/postgres_001_initial_schema.sql', 'r') as f:
    migration_sql = f.read()

# Connect and execute
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute(migration_sql)
    print("✓ CRS schema migration applied successfully")
except Exception as e:
    print(f"✗ Migration error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
