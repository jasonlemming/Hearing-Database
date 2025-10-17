#!/usr/bin/env python3
"""Check if Policy Library schema exists"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv('BROOKINGS_DATABASE_URL') or os.getenv('DATABASE_URL')
print(f"Connecting to: {database_url[:50]}...")

conn = psycopg2.connect(database_url)
cur = conn.cursor()

# Check if Policy Library tables already exist
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('sources', 'documents', 'authors', 'subjects', 'document_authors', 'document_subjects')
    ORDER BY table_name
""")

existing_tables = [row[0] for row in cur.fetchall()]
print(f"\nPolicy Library tables found: {existing_tables}")

if len(existing_tables) >= 4:
    print("\n✓ Policy Library core tables already exist!")

    # Check if CRS source exists
    cur.execute("SELECT * FROM sources WHERE source_code = 'CRS'")
    crs_source = cur.fetchone()
    if crs_source:
        print("✓ CRS source exists in Policy Library")
    else:
        print("⚠ CRS source needs to be added")
else:
    print(f"\n⚠ Missing tables: {set(['sources', 'documents', 'authors', 'subjects']) - set(existing_tables)}")
    print("  Run: python cli.py brookings init")

cur.close()
conn.close()
