#!/usr/bin/env python3
"""Verify CRS products synced to Policy Library"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Policy Library database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Count CRS documents
cur.execute("""
    SELECT COUNT(*)
    FROM documents d
    JOIN sources s ON d.source_id = s.source_id
    WHERE s.source_code = 'CRS'
""")
crs_count = cur.fetchone()[0]
print(f"CRS documents in Policy Library: {crs_count}")

# Show sample CRS documents
cur.execute("""
    SELECT d.document_id, d.document_identifier, d.title, d.publication_date
    FROM documents d
    JOIN sources s ON d.source_id = s.source_id
    WHERE s.source_code = 'CRS'
    ORDER BY d.document_id DESC
    LIMIT 10
""")
print(f"\nMost recent CRS documents:")
for row in cur.fetchall():
    doc_id, identifier, title, pub_date = row
    print(f"  [{doc_id}] {identifier} - {title[:60]}... ({pub_date})")

# Check authors
cur.execute("""
    SELECT COUNT(DISTINCT a.author_id)
    FROM authors a
    JOIN document_authors da ON a.author_id = da.author_id
    JOIN documents d ON da.document_id = d.document_id
    JOIN sources s ON d.source_id = s.source_id
    WHERE s.source_code = 'CRS'
""")
author_count = cur.fetchone()[0]
print(f"\nCRS authors: {author_count}")

# Check subjects
cur.execute("""
    SELECT COUNT(DISTINCT sb.subject_id)
    FROM subjects sb
    JOIN document_subjects ds ON sb.subject_id = ds.subject_id
    JOIN documents d ON ds.document_id = d.document_id
    JOIN sources s ON d.source_id = s.source_id
    WHERE s.source_code = 'CRS'
""")
subject_count = cur.fetchone()[0]
print(f"CRS subjects: {subject_count}")

cur.close()
conn.close()
