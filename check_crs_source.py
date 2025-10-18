#!/usr/bin/env python3
"""Check what the CRS source_code actually is in the database"""
import psycopg2

DATABASE_URL = 'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require'

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get all sources
cur.execute('SELECT source_id, source_code, name FROM sources ORDER BY source_id')
sources = cur.fetchall()

print("All sources in Policy Library database:")
print("=" * 80)
for source_id, source_code, name in sources:
    print(f"  {source_id:3d} | {source_code:20s} | {name}")

print("\n" + "=" * 80)

# Check document 307 specifically
cur.execute('''
    SELECT d.document_id, d.document_identifier, s.source_id, s.source_code, s.name
    FROM documents d
    LEFT JOIN sources s ON d.source_id = s.source_id
    WHERE d.document_id = 307
''')

result = cur.fetchone()
if result:
    doc_id, identifier, source_id, source_code, source_name = result
    print(f"\nDocument 307 ({identifier}):")
    print(f"  source_id: {source_id}")
    print(f"  source_code: '{source_code}'")
    print(f"  source_name: {source_name}")

    print(f"\nIn policy_library.py, the check is:")
    print(f"  if document.source.source_code == 'CRS':")
    print(f"\nActual source_code: '{source_code}'")
    print(f"Match: {source_code == 'CRS'}")

    if source_code != 'CRS':
        print(f"\n✗✗✗ MISMATCH FOUND! ✗✗✗")
        print(f"  The code checks for 'CRS' but the database has '{source_code}'")
        print(f"  This is why the CRS rendering logic is NOT executing!")

cur.close()
conn.close()
