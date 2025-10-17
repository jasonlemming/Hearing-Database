#!/usr/bin/env python3
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Check what's actually in the documents table with source_id = 1 (CRS)
cur.execute("""
    SELECT COUNT(*)
    FROM documents
    WHERE source_id = 1
""")
crs_doc_count = cur.fetchone()[0]
print(f"CRS documents in documents table: {crs_doc_count}")

# Check a sample
cur.execute("""
    SELECT document_id, document_identifier, title
    FROM documents
    WHERE source_id = 1
    LIMIT 5
""")
print("\nSample CRS documents:")
for row in cur.fetchall():
    print(f"  {row[1]}: {row[2][:60]}...")

# Check total documents by source
cur.execute("""
    SELECT s.source_code, COUNT(d.document_id) as count
    FROM sources s
    LEFT JOIN documents d ON s.source_id = d.source_id
    GROUP BY s.source_code, s.source_id
    ORDER BY s.source_code
""")
print("\nDocuments by source:")
for row in cur.fetchall():
    print(f"  {row[0]:15} {row[1]:>5} documents")

# Check if there's a separate CRS database we should be looking at
print(f"\nCRS_DATABASE_URL env var: {os.getenv('CRS_DATABASE_URL', 'Not set')[:50]}...")
print(f"DATABASE_URL env var: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")

cur.close()
conn.close()
